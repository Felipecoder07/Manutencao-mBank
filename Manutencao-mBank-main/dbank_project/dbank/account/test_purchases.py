from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.db import connections
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from .models import Account, Client, PurchaseEvent, PurchaseIntent, Transaction


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class PurchaseTests(TransactionTestCase):
    url = '/bank/api/compras/'

    def setUp(self):
        self.customer = Client.objects.create_user(username='customer', password='local-payment-test')
        self.seller = Client.objects.create_user(username='seller', name='Loja')
        self.seller.user_permissions.add(Permission.objects.get(codename='issue_purchase'))
        self.customer_account = Account.objects.create(owner=self.customer, iban='BR100', balance=100)
        self.seller_account = Account.objects.create(owner=self.seller, iban='BR200')
        self.api = APIClient()
        self.order_data = {'payer_iban':'BR100', 'recipient_account_id': self.seller_account.pk,
                           'amount':'30.00', 'order_reference':'order-1'}
        self.order = self.issue()
        self.api.force_authenticate(self.customer)

    def issue(self, **overrides):
        self.api.force_authenticate(self.seller)
        response = self.api.post(self.url, {**self.order_data, **overrides}, format='json', secure=True)
        self.assertEqual(response.status_code, 201)
        return self.url + response.data['reference'] + '/'

    def confirm(self, order=None, client=None, **overrides):
        return (client or self.api).post((order or self.order)+'confirmar/',
            {'password':'local-payment-test', 'idempotency_key':'key', **overrides}, format='json', secure=True)

    def test_review_payment_and_replay(self):
        review = self.api.get(self.order, secure=True).data
        self.assertEqual((review['status'], review['amount'], review['merchant_name']), ('PENDING','30.00','Loja'))
        self.assertTrue(review['payer_account'].startswith('****'))
        self.assertEqual(self.confirm(amount='0.01').status_code,400)
        paid = self.confirm()
        self.assertEqual(paid.data['status'], 'PAID')
        self.assertEqual(self.confirm().data['receipt'], paid.data['receipt'])
        self.assertEqual(self.confirm(idempotency_key='new').data['receipt'], paid.data['receipt'])
        self.assertEqual(self.api.get(self.order, secure=True).data['receipt'],paid.data['receipt'])
        self.assertEqual(Transaction.objects.get().transaction_type, 'PURCHASE')
        self.customer_account.refresh_from_db()
        self.seller_account.refresh_from_db()
        self.assertEqual((self.customer_account.balance,self.seller_account.balance),(70,30))
        other = self.issue(order_reference='order-2')
        self.api.force_authenticate(self.customer)
        self.assertEqual(self.confirm(other).data['code'],'IDEMPOTENCY_CONFLICT')
        self.assertNotIn('local-payment-test',str(paid.data))

    def test_authority_expiry_and_cancellation(self):
        self.assertEqual(self.api.get(self.order).status_code,403)
        self.assertEqual(self.api.post(self.url,self.order_data,secure=True).status_code,403)
        self.api.force_authenticate(self.seller)
        self.assertEqual(self.api.get(self.order,secure=True).status_code,404)
        self.assertEqual(self.confirm().status_code,404)
        self.assertEqual(self.api.post(self.url,self.order_data,secure=True).status_code,200)
        self.assertEqual(self.api.post(self.url,{**self.order_data,'amount':5},secure=True).status_code,409)
        another = self.issue(order_reference='other')
        self.api.force_authenticate(self.customer)
        self.assertEqual(self.api.post(another+'cancelar/',secure=True).data['status'],'CANCELLED')
        self.assertEqual(self.confirm(another).status_code,409)
        PurchaseIntent.objects.filter(order_reference='order-1').update(expires_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(self.confirm().status_code,409)
        self.assertEqual(self.api.get(self.order,secure=True).data['status'],'EXPIRED')
        self.assertFalse(Transaction.objects.exists())

    @override_settings(PURCHASE_PASSWORD_MAX_ATTEMPTS=2)
    def test_password_block_persists_across_orders(self):
        another = self.issue(order_reference='other')
        self.api.force_authenticate(self.customer)
        self.assertEqual(self.confirm(password='wrong').data['code'],'INVALID_PASSWORD')
        blocked = self.confirm(another,password='wrong')
        self.assertEqual(blocked.status_code,429)
        self.assertIn('retry_at',blocked.data)
        self.assertEqual(self.confirm().status_code,429)
        self.assertFalse(Transaction.objects.exists())
        with patch('account.purchases.timezone.now',return_value=timezone.now()+timedelta(seconds=901)):
            PurchaseIntent.objects.update(expires_at=timezone.now()+timedelta(hours=1))
            self.assertEqual(self.confirm().data['status'],'PAID')

    def test_reserve_and_closed_receiver(self):
        bank = self.api.post('/bank/api/cofrinhos/', {'name':'Reserva'},secure=True).data
        self.api.post(f"/bank/api/cofrinhos/{bank['id']}/guardar/",{'amount':'75','idempotency_key':'reserve'},secure=True)
        self.assertEqual(self.confirm().data['code'],'INSUFFICIENT_AVAILABLE_BALANCE')
        self.api.post(f"/bank/api/cofrinhos/{bank['id']}/resgatar/",{'amount':'5','idempotency_key':'redeem'},secure=True)
        Account.objects.filter(pk=self.seller_account.pk).update(closed=timezone.now())
        self.assertEqual(self.confirm().data['code'],'ACCOUNT_CLOSED')
        Account.objects.filter(pk=self.seller_account.pk).update(closed=None)
        self.assertEqual(self.confirm().data['status'],'PAID')
        self.customer_account.refresh_from_db()
        self.assertEqual((self.customer_account.available_balance,self.customer_account.reserved_balance),(0,70))

    def test_failure_after_transfer_rolls_back(self):
        with patch.object(PurchaseEvent.objects,'create',side_effect=RuntimeError), self.assertRaises(RuntimeError):
            self.confirm()
        self.assertFalse(Transaction.objects.exists())
        self.customer_account.refresh_from_db()
        self.seller_account.refresh_from_db()
        self.assertEqual((self.customer_account.balance,self.seller_account.balance),(100,0))
        self.assertEqual(PurchaseIntent.objects.get().status,'PENDING')
        self.assertEqual(self.confirm().status_code,200)

    def test_concurrent_confirmation(self):
        ready = Barrier(2)
        def submit():
            try:
                api = APIClient()
                api.force_authenticate(self.customer)
                ready.wait(timeout=5)
                return self.confirm(client=api).status_code
            finally:
                connections.close_all()
        with ThreadPoolExecutor(2) as pool:
            futures = [pool.submit(submit) for _ in range(2)]
            codes = [future.result() for future in futures]
        self.assertIn(200,codes)
        self.assertTrue(set(codes) <= {200,503})
        self.assertEqual(self.confirm().status_code,200)
        self.assertEqual(Transaction.objects.count(),1)
