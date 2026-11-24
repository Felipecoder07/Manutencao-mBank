from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch

from django.db import connections
from django.test import TransactionTestCase
from django.urls import reverse

from .models import Account, Client, Transaction


class LedgerTests(TransactionTestCase):
    def setUp(self):
        self.owner = Client.objects.create_user(username='payer')
        self.src = Account.objects.create(owner=self.owner, iban='BR101', balance=100)
        self.dest = Account.objects.create(owner=self.owner, iban='BR102')
        self.client.force_login(self.owner)

    def test_web_replay_and_conflict(self):
        url = reverse('bank:transactions_create')
        page = self.client.get(url)
        data = dict(src=self.src.pk, dest=self.dest.pk, amount='12.34',
                    request_key=page.context['form']['request_key'].value())
        self.assertTrue(data['request_key'])
        for _ in range(2):
            self.assertEqual(self.client.post(url, data).status_code, 302)
        self.assertContains(self.client.post(url, dict(data, amount='1.00')), 'already used')
        self.src.refresh_from_db()
        self.dest.refresh_from_db()
        self.assertEqual(self.src.balance, Decimal('87.66'))
        self.assertEqual(self.dest.balance, Decimal('12.34'))
        self.assertEqual(Transaction.objects.get().transaction_type, 'TRANSFER')

    def test_centavos_and_invalid_debits(self):
        self.src.deposit('0.10')
        self.src.deposit('0.20')
        self.src.withdraw('0.30')
        for amount in ['0', '-1', '1.001', '100.01', 'NaN']:
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                self.src.withdraw(amount)
        self.src.refresh_from_db()
        self.assertEqual(self.src.available_balance, Decimal('100.00'))
        self.assertEqual(Transaction.objects.count(), 3)

    def test_rollback_on_ledger_failure(self):
        with patch.object(Transaction.objects, 'create', side_effect=RuntimeError), self.assertRaises(RuntimeError):
            self.src.transfer(self.dest, '70')
        self.src.refresh_from_db()
        self.dest.refresh_from_db()
        self.assertEqual((self.src.balance, self.dest.balance), (100, 0))
        self.assertFalse(Transaction.objects.exists())

    def test_two_connections_cannot_spend_same_balance(self):
        barrier = Barrier(2)
        def debit():
            try:
                account = Account.objects.get(pk=self.src.pk)
                barrier.wait(timeout=5)
                try:
                    account.withdraw(70)
                except ValueError as exc:
                    return str(exc)
                return 'paid'
            finally:
                connections.close_all()

        with ThreadPoolExecutor(2) as pool:
            results = [pool.submit(debit) for _ in range(2)]
            self.assertCountEqual([result.result() for result in results], ['paid', 'Insufficient available balance.'])
        self.src.refresh_from_db()
        self.assertEqual(self.src.balance, 30)
        self.assertEqual(Transaction.objects.count(), 1)

    def test_statement_and_api_detail_are_scoped_to_owner(self):
        entry = self.src.deposit('1.23')
        urls = [reverse('bank:account_transactions', args=[self.src.pk]),
                reverse('bank:transaction-detail', args=[entry.pk])]
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_login(Client.objects.create_user(username='other'))
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 404)


class FinancialMigrationTests(TransactionTestCase):
    def test_balances_and_history_reconcile_after_migration(self):
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor

        previous = [('account', '0002_normalize_phone_number')]
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        executor.migrate(previous)
        try:
            apps = executor.loader.project_state(previous).apps
            owner = apps.get_model('account', 'Client').objects.create(username='legacy')
            accounts = apps.get_model('account', 'Account').objects
            source = accounts.create(owner=owner, iban='BR201', balance=0.1 + 0.2)
            target = accounts.create(owner=owner, iban='BR202', balance=0.10)
            entries = apps.get_model('account', 'Transaction').objects
            entries.create(dest=source, amount=0.50)
            entries.create(src=source, amount=0.10)
            entries.create(src=source, dest=target, amount=0.10)
            MigrationExecutor(connection).migrate(latest)
            self.assertEqual(Account.objects.get(pk=source.pk).balance, Decimal('0.30'))
            self.assertEqual(Account.objects.get(pk=target.pk).balance, Decimal('0.10'))
            self.assertEqual(list(Transaction.objects.order_by('pk').values_list('transaction_type', 'amount')),
                             [('DEPOSIT', Decimal('0.50')), ('WITHDRAW', Decimal('0.10')),
                              ('TRANSFER', Decimal('0.10'))])
        finally:
            MigrationExecutor(connection).migrate(latest)
