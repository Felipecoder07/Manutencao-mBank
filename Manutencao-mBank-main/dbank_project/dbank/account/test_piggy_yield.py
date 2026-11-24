import json
from datetime import date, datetime, timezone
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Account, Client, PiggyBank, PiggyBankMovement, Transaction, YieldSettings


class YieldTests(TestCase):
    day = '2025-02-03'
    base = '/bank/api/cofrinhos/'

    def setUp(self):
        self.user = Client.objects.create_user(username='customer')
        self.account = Account.objects.create(owner=self.user, iban='BR123', balance=2000)
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        for goal, amount in [(1250, 850), (1000, 400)]:
            response = self.api.post(self.base, {'name': 'Meta', 'goal_amount': goal})
            pk = response.data['id']
            self.api.post(f'{self.base}{pk}/guardar/', {'amount': amount, 'idempotency_key': str(pk)})
        stamp = datetime(2025, 2, 3, 12, tzinfo=timezone.utc)
        PiggyBank.objects.update(created_at=stamp)
        PiggyBankMovement.objects.update(created_at=stamp)
        self.policy = YieldSettings.objects.create(effective_from=self.day, cdi_annual_rate=Decimal('0.1065'))
        self.staff = Client.objects.create_user(username='staff', is_staff=True)

    def run_command(self, **options):
        out = StringIO()
        call_command('apply_piggybank_yield', stdout=out, **options)
        return json.loads(out.getvalue())

    def test_summary_owner_filter_and_credit(self):
        with patch('account.piggy_banks.timezone.localdate', return_value=date(2025, 2, 5)):
            summary = self.api.get(self.base + 'dashboard/').data
            self.assertEqual((summary['active_count'], summary['total_saved']), (2, '1250.00'))
            self.assertEqual([obj['progress_percent'] for obj in summary['objectives']], [68, 40])
            self.assertEqual(summary['available_balance'], '750.00')
            self.assertEqual(self.api.post(self.base+'aplicar-rendimento/', {'date':self.day}).status_code, 403)
            self.api.force_authenticate(self.staff)
            self.assertEqual(self.api.get(self.base+'dashboard/', {'account_id':self.account.pk}).status_code, 404)
            self.assertEqual(self.api.get(self.base+'dashboard/').data['total_saved'], '0.00')
            preview = self.api.post(self.base+'aplicar-rendimento/', {'date':self.day, 'preview':True})
            self.assertEqual(preview.data['total'], '0.50')
            self.assertFalse(Transaction.objects.filter(transaction_type='PIGGY_YIELD').exists())
            self.assertEqual(self.run_command(date=self.day)['credits'], 2)
            self.assertEqual(self.run_command(date=self.day)['credits'], 0)
            self.account.refresh_from_db()
            self.assertEqual((self.account.balance, self.account.reserved_balance, self.account.available_balance),
                             (Decimal('2000.50'), Decimal('1250.50'), Decimal('750.00')))
            self.api.force_authenticate(self.user)
            summary = self.api.get(self.base+'dashboard/').data
            self.assertEqual(summary['monthly_yield_total'], '0.50')
            self.assertEqual(self.api.get(self.base+'extrato/?type=YIELD').data['count'], 2)
            bank = PiggyBank.objects.first()
            self.assertEqual(self.api.get(f'{self.base}{bank.pk}/').data['total_yield'], '0.34')
            response = self.api.post(f'{self.base}{bank.pk}/resgatar/', {'amount':'0.34','idempotency_key':'redeem'})
            self.assertEqual(response.data['available_balance'], '750.34')

    def test_monthly_batch_replays_days_and_uses_historical_balance(self):
        bank = PiggyBank.objects.first()
        self.api.post(f'{self.base}{bank.pk}/guardar/', {'amount':100, 'idempotency_key':'later'})
        self.run_command(date=self.day)
        self.assertEqual(bank.movements.get(movement_type='YIELD').receipt['movement']['principal'], '850.00')
        simulated = self.run_command(month='2025-02', dry_run=True)
        result = self.run_command(month='2025-02')
        self.assertEqual(result['total'], simulated['total'])
        self.assertEqual(result['credits'], 38)
        self.assertEqual(self.run_command(month='2025-02')['credits'], 0)
        self.assertEqual(self.run_command(date='2025-02-08')['credits'], 0)

    def test_missing_policy_and_failed_history_leave_money_unchanged(self):
        self.api.force_authenticate(self.staff)
        response = self.api.post(self.base+'aplicar-rendimento/', {'date':'2025-01-31'})
        self.assertEqual(response.status_code, 400)
        with patch.object(PiggyBankMovement.objects, 'create', side_effect=RuntimeError), self.assertRaises(RuntimeError):
            self.run_command(date=self.day)
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, 2000)
        self.assertEqual(self.account.reserved_balance, 1250)
        self.assertFalse(Transaction.objects.exists())
