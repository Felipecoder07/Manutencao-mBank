import json

from django.core.management.base import BaseCommand, CommandError

from account.services.piggy_yield import apply_yield, period_dates


class Command(BaseCommand):
    help = 'Credita competências encerradas de segunda a sexta. Sem data, processa ontem.'

    def add_arguments(self, parser):
        period = parser.add_mutually_exclusive_group()
        period.add_argument('--date')
        period.add_argument('--month')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        try:
            days = period_dates(options['date'], options['month'])
            return json.dumps(apply_yield(days, preview=options['dry_run']))
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
