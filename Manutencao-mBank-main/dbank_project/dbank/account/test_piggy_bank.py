from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.db import IntegrityError, connections, transaction
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import Account, Client, PiggyBankMovement


class PiggyBankTests(TransactionTestCase):
    url = '/bank/api/cofrinhos/'

    def setUp(self):
        self.user = Client.objects.create_user(username='titular')
        self.account = Account.objects.create(owner=self.user, iban='BR100', balance=100)
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        response = self.api.post(self.url, {'name': 'Viagem', 'goal_amount': '100.00'})
        self.assertEqual(response.status_code, 201)
        self.detail = self.url + str(response.data['id']) + '/'

    def move(self, action, amount, key, client=None):
        return (client or self.api).post(self.detail + action + '/', {'amount': amount, 'idempotency_key': key})

    def test_reserve_replay_web_debit_and_history(self):
        first = self.move('guardar', 70, 'one')
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.data['available_balance'], '30.00')
        self.assertEqual(first.data['piggy_bank']['progress_percent'], 70)
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, 100)
        self.client.force_login(self.user)
        response = self.client.post('/bank/transactions/create', {'src': self.account.pk, 'amount': '31'})
        self.assertContains(response, 'Insufficient available balance')
        dest = Account.objects.create(owner=self.user, iban='BR200')
        with self.assertRaises(ValueError):
            self.account.transfer(dest, 31)
        self.assertEqual(self.api.post(self.detail + 'arquivar/').status_code, 409)
        self.assertEqual(self.move('resgatar', 20, 'two').data['available_balance'], '50.00')
        self.assertEqual(self.move('guardar', 70, 'one').data, first.data)
        self.assertEqual(self.move('guardar', 71, 'one').status_code, 409)
        self.assertEqual(self.api.get(self.detail + 'extrato/').data['count'], 2)
        self.assertEqual(self.api.get(self.url + 'extrato/?type=WITHDRAW').data['count'], 1)
        self.assertEqual(self.move('resgatar', 51, 'three').status_code, 409)
        self.assertEqual(self.move('guardar', '-1', 'four').status_code, 400)

    def test_close_archive_permissions_and_metadata(self):
        self.move('guardar', 5, 'one')
        with self.assertRaises(IntegrityError), transaction.atomic():
            Account.objects.filter(pk=self.account.pk).update(closed=timezone.now())
        edit = self.api.patch(self.detail, {'name': 'Reserva', 'goal_amount': 4, 'current_balance': 1})
        self.assertEqual(edit.data['current_balance'], '5.00')
        self.assertTrue(edit.data['goal_reached'])
        self.move('resgatar', 5, 'two')
        self.assertEqual(self.api.post(self.detail + 'arquivar/').status_code, 200)
        self.assertEqual(self.api.get(self.url).data, [])
        self.assertEqual(self.move('guardar', 5, 'three').status_code, 409)
        self.assertEqual(self.api.get(self.detail + 'extrato/').data['count'], 2)
        self.api.force_authenticate(Client.objects.create_user(username='other'))
        for url in [self.detail, self.detail + 'extrato/']:
            self.assertEqual(self.api.get(url).status_code, 404)
        self.assertEqual(self.move('resgatar', 1, 'four').status_code, 404)
        self.assertEqual(self.api.get(self.url + 'extrato/').data['count'], 0)

    def test_movement_failure_rolls_back_both_balances(self):
        with patch.object(PiggyBankMovement.objects, 'create', side_effect=RuntimeError), self.assertRaises(RuntimeError):
            self.move('guardar', 70, 'one')
        self.account.refresh_from_db()
        self.assertEqual(self.account.available_balance, 100)
        self.assertEqual(self.account.piggy_banks.get().current_balance, 0)

    def test_concurrent_reserve_and_debit(self):
        ready = Barrier(2)
        def reserve():
            try:
                client = APIClient()
                client.force_authenticate(self.user)
                ready.wait(timeout=5)
                return self.move('guardar', 70, 'parallel', client).status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(1) as pool:
            future = pool.submit(reserve)
            ready.wait(timeout=5)
            try:
                self.account.withdraw(70)
                paid = True
            except ValueError:
                paid = False
            outcome = future.result()
        self.account.refresh_from_db()
        self.assertEqual(self.account.available_balance, 30)
        self.assertIn((paid, outcome), [(True, 409), (True, 503), (False, 200)])
        self.assertEqual(self.account.reserved_balance, self.account.piggy_banks.get().current_balance)
