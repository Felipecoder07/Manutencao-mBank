from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from django.db import transaction
from django.utils import timezone

from account.models import Account, PiggyBank, PiggyBankMovement, Transaction, YieldSettings
from .ledger import CENT, MAX_AMOUNT


def period_dates(day=None, month=None):
    if day and month:
        raise ValueError('Escolha uma data ou um mês.')
    today = timezone.localdate()
    try:
        if month:
            start = date.fromisoformat(f'{month}-01')
            end = start.replace(day=monthrange(start.year, start.month)[1])
        else:
            start = end = date.fromisoformat(day) if day else today - timedelta(days=1)
    except (TypeError, ValueError) as exc:
        raise ValueError('Data ou mês inválido.') from exc
    if end >= today:
        raise ValueError('A competência precisa estar encerrada.')
    return [start + timedelta(days=i) for i in range((end - start).days + 1)
            if (start + timedelta(days=i)).weekday() < 5]


def closing_principal(bank, day):
    # Effective date for interest is its competence, even for delayed posting.
    principal = Decimal(0)
    for kind, amount in bank.movements.filter(created_at__date__lte=day).exclude(
            movement_type='YIELD').values_list('movement_type', 'amount'):
        principal += -amount if kind == 'WITHDRAW' else amount
    for amount in bank.movements.filter(movement_type='YIELD', competence_date__lt=day).values_list('amount', flat=True):
        principal += amount
    return principal


@transaction.atomic
def apply_yield(days, preview=False):
    total = Decimal(0)
    count = 0
    for day in days:
        policy = YieldSettings.objects.filter(effective_from__lte=day).order_by('-effective_from').first()
        if policy is None:
            raise ValueError(f'Configure a política vigente para {day}.')
        daily_rate = ((1 + policy.cdi_annual_rate) ** (Decimal(1) / policy.business_days_per_year) - 1)
        daily_rate *= policy.cdi_percentage / 100
        banks = PiggyBank.objects.filter(archived_at__isnull=True, account__closed__isnull=True,
                                         created_at__date__lte=day).order_by('account_id', 'pk')
        for candidate in banks:
            account = Account.objects.select_for_update().get(pk=candidate.account_id)
            bank = PiggyBank.objects.select_for_update().get(pk=candidate.pk)
            if account.closed or bank.archived_at or bank.movements.filter(competence_date=day).exists():
                continue
            principal = closing_principal(bank, day)
            amount = (principal * daily_rate).quantize(CENT, rounding=ROUND_HALF_UP)
            if amount < CENT:
                continue
            if bank.movements.filter(competence_date__gt=day).exists():
                raise ValueError('Competência posterior já creditada. Reconcilie a ordem dos créditos.')
            if account.balance + amount > MAX_AMOUNT:
                raise ValueError('O rendimento excede o limite de saldo da conta.')
            account.balance += amount
            account.reserved_balance += amount
            bank.current_balance += amount
            account.save(update_fields=['balance', 'reserved_balance'])
            bank.save(update_fields=['current_balance'])
            entry = Transaction.objects.create(dest=account, amount=amount, transaction_type='PIGGY_YIELD')
            reference = uuid4()
            movement = {'reference_id': str(reference), 'movement_type': 'YIELD', 'status': 'AUTOMATIC',
                        'amount': format(amount, '.2f'), 'competence_date': day.isoformat(),
                        'transaction_id': entry.pk, 'principal': format(principal, '.2f'), 'policy_id': policy.pk}
            PiggyBankMovement.objects.create(reference_id=reference, requested_by_id=account.owner_id,
                                            piggy_bank=bank, competence_date=day, movement_type='YIELD',
                                            amount=amount, receipt={'movement': movement})
            total += amount
            count += 1
    if preview:
        transaction.set_rollback(True)
    return {'preview': preview, 'credits': count, 'total': format(total, '.2f')}
