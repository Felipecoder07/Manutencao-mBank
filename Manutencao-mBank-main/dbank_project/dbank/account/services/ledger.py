from time import sleep
from decimal import Decimal, InvalidOperation

from django.db import OperationalError, connection, transaction

from account.models import Account, Transaction


MAX_AMOUNT = Decimal('999999999999.99')
CENT = Decimal('0.01')


def post(src, dest, amount, *, actor=None, key=None):
    try:
        amount = Decimal(str(amount))
        if not amount.is_finite() or not 0 < amount <= MAX_AMOUNT or amount != amount.quantize(CENT):
            raise ValueError('Enter a positive amount with at most two decimal places.')
    except InvalidOperation as exc:
        raise ValueError('Invalid amount.') from exc

    accounts = [account for account in (src, dest) if account is not None]
    ids = [account.pk for account in accounts]
    if not ids or None in ids or len(set(ids)) != len(ids):
        raise ValueError('Choose distinct, saved accounts.')
    if key and actor is None:
        raise ValueError('An authenticated requester is required.')

    for attempt in range(4):
        try:
            return _record(src, dest, amount, actor, key, accounts, ids)
        except OperationalError as exc:
            if connection.vendor != 'sqlite' or 'locked' not in str(exc).lower():
                raise
            if attempt == 3:
                raise ValueError('Account busy. Retry the same request.') from exc
            sleep(0.025 * (attempt + 1))


def _record(src, dest, amount, actor, key, accounts, ids):
    with transaction.atomic():
        # SQLite acquires its write lock at BEGIN IMMEDIATE. Lock rows in
        # stable order on databases with row-level locking.
        locked = Account.objects.select_for_update().filter(pk__in=ids).order_by('pk')
        current = {account.pk: account for account in locked}
        if len(current) != len(ids):
            raise ValueError('Account unavailable.')
        if actor and src and current[src.pk].owner_id != actor.pk:
            raise ValueError('Source account unavailable.')
        if key:
            previous = Transaction.objects.filter(requested_by=actor, request_key=key).first()
            if previous:
                if (previous.src_id, previous.dest_id, previous.amount) != (
                    src.pk if src else None, dest.pk if dest else None, amount
                ):
                    raise ValueError('Request key already used for a different operation.')
                return previous
        if any(account.is_closed() for account in current.values()):
            raise ValueError('Account is closed.')
        if src:
            debit = current[src.pk]
            if amount > debit.available_balance:
                raise ValueError('Insufficient available balance.')
            debit.balance -= amount
            debit.save(update_fields=['balance'])
        if dest:
            credit = current[dest.pk]
            if credit.balance + amount > MAX_AMOUNT:
                raise ValueError('Balance limit exceeded.')
            credit.balance += amount
            credit.save(update_fields=['balance'])
        kind = 'TRANSFER' if src and dest else ('WITHDRAW' if src else 'DEPOSIT')
        entry = Transaction.objects.create(
            src=src, dest=dest, amount=amount, requested_by=actor, request_key=key,
            transaction_type=kind,
        )
    for account in accounts:
        account.balance = current[account.pk].balance
    return entry
