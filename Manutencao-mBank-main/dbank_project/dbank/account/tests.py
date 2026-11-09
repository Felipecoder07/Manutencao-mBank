from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from .models import Account, Client


class PageRegressionTests(TestCase):
    def setUp(self):
        self.user = Client.objects.create_user(username='maintenance', name='Maintenance')
        self.account = Account.objects.create(iban='BR123456', owner=self.user)
        self.client.force_login(self.user)

    def test_pages_render(self):
        pages = [
            ('home', []),
            ('bank:clients_list', []),
            ('bank:clients_detail', [self.user.pk]),
            ('bank:accounts_list', []),
            ('bank:accounts_create', []),
            ('bank:transactions_list', []),
            ('bank:account_transactions', [self.account.pk]),
            ('bank:transactions_create', []),
        ]
        for name, args in pages:
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 200)

    def test_client_without_phone_is_valid(self):
        self.user.full_clean()
        self.user.refresh_from_db()
        self.assertEqual(self.user.phone_number, '')


class PhoneNumberMigrationTests(TransactionTestCase):
    def test_existing_null_phone_is_normalized_and_numbers_are_preserved(self):
        previous = [('account', '0001_initial')]
        current = [('account', '0002_normalize_phone_number')]
        executor = MigrationExecutor(connection)
        executor.migrate(previous)
        try:
            old_client = executor.loader.project_state(previous).apps.get_model('account', 'Client')
            missing = old_client.objects.create(username='missing', name='Missing', phone_number=None)
            filled = old_client.objects.create(username='filled', name='Filled', phone_number='11999999999')
            executor = MigrationExecutor(connection)
            executor.migrate(current)
            new_client = executor.loader.project_state(current).apps.get_model('account', 'Client')
            self.assertEqual(new_client.objects.get(pk=missing.pk).phone_number, '')
            self.assertEqual(new_client.objects.get(pk=filled.pk).phone_number, '11999999999')
        finally:
            MigrationExecutor(connection).migrate(current)
