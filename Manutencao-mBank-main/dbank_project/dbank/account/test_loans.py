from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import Account, Client, CreditPolicy, Transaction


class LoanSimulationTests(TestCase):
    base = '/bank/api/emprestimos/'

    def setUp(self):
        self.policy = CreditPolicy.objects.get(is_active=True)
        self.user = Client.objects.create_user(username='borrower')
        self.account = Account.objects.create(owner=self.user, iban='BR123', balance=125)
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def simulate(self, **changes):
        body = {'amount': '3000.00', 'installments': 12, **changes}
        return self.api.post(self.base+'simular/', body, format='json')

    def test_config_and_full_schedule_without_financial_effects(self):
        config = self.api.get(self.base+'config/').data
        self.assertEqual(config['preapproved_limit_available'], '10000.00')
        self.assertEqual(config['quick_installments'], [6, 12, 24, 36])
        self.assertEqual(config['accounts'], [{'id': self.account.pk, 'iban': self.account.iban}])
        with patch('account.loans.timezone.localdate', return_value=date(2024, 1, 31)):
            result = self.simulate().data
            self.assertEqual(self.simulate(monthly_interest_rate='0', total_payable='1').data, result)
        rows = result['installments_schedule']
        self.assertEqual(len(rows), 12)
        self.assertEqual([r['due_date'] for r in rows[:2]], ['2024-02-29', '2024-03-31'])
        self.assertEqual(sum(Decimal(r['amortization_amount']) for r in rows), 3000)
        self.assertEqual(sum(Decimal(r['total_amount']) for r in rows), Decimal(result['total_payable']))
        self.assertEqual(rows[-1]['closing_balance'], '0.00')
        self.account.refresh_from_db()
        self.assertEqual(self.account.available_balance, 125)
        self.assertFalse(Transaction.objects.exists())
        self.assertEqual(self.api.get(self.base+'config/').data, config)

    def test_zero_rate_rounding_and_price_reference(self):
        CreditPolicy.objects.update(monthly_interest_rate=0)
        result = self.simulate(amount='100', installments=3).data
        self.assertEqual([r['total_amount'] for r in result['installments_schedule']], ['33.33','33.33','33.34'])
        self.assertTrue(result['has_last_installment_diff'])
        CreditPolicy.objects.update(monthly_interest_rate=Decimal('0.10'))
        result = self.simulate(amount='100', installments=2).data
        self.assertEqual(result['installment_amount'], '57.62')
        self.assertEqual(result['total_interest'], '15.24')
        self.assertEqual(result['total_payable'], '115.24')

    def test_limit_fees_and_invalid_inputs(self):
        self.user.preapproved_limit = 0
        self.user.save()
        CreditPolicy.objects.update(fixed_fee=5, iof_rate=Decimal('0.01'), monthly_interest_rate=0)
        result = self.simulate(amount='100', installments=1).data
        self.assertFalse(result['can_contract'])
        self.assertEqual(result['total_payable'], '106.00')
        self.assertEqual(result['total_fees'], '6.00')
        for invalid in [{'amount':'99.99'}, {'amount':'50000.01'}, {'amount':'100.001'}, {'installments':0},
                        {'installments':37}, {'installments':1.5}]:
            self.assertEqual(self.simulate(**invalid).status_code, 400)
        CreditPolicy.objects.update(is_active=False)
        self.assertEqual(self.simulate().status_code, 503)

    def test_select_open_account_and_require_authentication(self):
        foreign = Client.objects.create_user(username='other')
        other = Account.objects.create(owner=foreign, iban='BR999')
        self.assertEqual(self.simulate(account_id=other.pk).status_code, 404)
        second = Account.objects.create(owner=self.user, iban='BR456')
        self.assertEqual(self.simulate().status_code, 400)
        self.assertEqual(self.simulate(account_id=second.pk).status_code, 200)
        Account.objects.filter(owner=self.user).update(closed=timezone.now())
        self.assertEqual(self.simulate(account_id=second.pk).status_code, 404)
        self.assertEqual(self.simulate().status_code, 400)
        self.api.force_authenticate(None)
        self.assertIn(self.api.get(self.base+'config/').status_code, (401, 403))
        self.assertIn(self.simulate().status_code, (401, 403))
