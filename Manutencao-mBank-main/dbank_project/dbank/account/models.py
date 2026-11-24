import re
import uuid
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models


# Create your models here.

class Client(AbstractUser):
    preapproved_limit = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                            validators=[MinValueValidator(0)])
    name = models.CharField('clients name', max_length=128, null=False)
    phone_number = models.CharField('phone number', max_length=64, blank=True)

    def __str__(self):
        return '{}: {}'.format(self.id, self.name)


def validate_iban(value):
    match = re.search(r'^[A-Z]{2}\d+$', value)
    if not match:
        raise ValidationError('IBAN has wrong format.')


class Account(models.Model):
    iban = models.CharField('iban', max_length=10, null=False, unique=True, validators=[validate_iban])
    created = models.DateTimeField('creation date', auto_now_add=True)
    closed = models.DateTimeField('closed date', default=None, null=True, blank=True)
    balance = models.DecimalField('current balance', max_digits=14, decimal_places=2, default=0, null=False, blank=True)
    owner = models.ForeignKey(Client, on_delete=models.CASCADE, null=False)

    reserved_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(reserved_balance__gte=0), name='nonnegative_reserve'),
            models.CheckConstraint(condition=models.Q(reserved_balance=0) | models.Q(
                reserved_balance__lte=models.F('balance'), closed__isnull=True), name='valid_account_reserve'),
        ]

    def clean(self):
        super().clean()
        if self.closed and self.reserved_balance:
            raise ValidationError({'closed': 'Resgate os cofrinhos antes de encerrar a conta.'})

    @property
    def available_balance(self):
        return self.balance - self.reserved_balance

    def deposit(self, amount, **request):
        from .services.ledger import post
        return post(None, self, amount, **request)

    def withdraw(self, amount, **request):
        from .services.ledger import post
        return post(self, None, amount, **request)

    def transfer(self, dest, amount, **request):
        from .services.ledger import post
        return post(self, dest, amount, **request)

    def is_open(self):
        return self.closed is None
    is_open.boolean = True

    def is_closed(self):
        return not self.is_open()

    def transactions(self):
        return self.transaction_set.all() | self.target.all()

    def __str__(self):
        return '{} ({}) {}'.format(self.iban, self.owner.name, self.balance)


class Transaction(models.Model):
    timestamp = models.DateTimeField('transaction timestamp', auto_now_add=True)
    src = models.ForeignKey('Account', default=None, null=True, on_delete=models.CASCADE)
    dest = models.ForeignKey('Account', default=None, related_name='target', null=True, on_delete=models.CASCADE)
    amount = models.DecimalField('transaction amount', max_digits=14, decimal_places=2, null=False)

    transaction_type = models.CharField(max_length=16, blank=True, default='', editable=False)
    requested_by = models.ForeignKey(Client, null=True, on_delete=models.PROTECT)
    request_key = models.UUIDField(null=True, editable=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['requested_by', 'request_key'], name='unique_ledger_request'),
        ]

    def get_type(self):
        if self.transaction_type == 'PURCHASE':
            return 'purchase'
        if self.transaction_type == 'PIGGY_YIELD':
            return 'piggy bank yield'
        if self.src is None:
            return 'deposit'
        elif self.dest is None:
            return 'withdraw'
        else:
            return 'transaction'

    def __str__(self):
        if self.src is None:
            return 'deposit to {} at {}: {}'.format(self.dest, self.timestamp, self.amount)
        elif self.dest is None:
            return 'withdraw from {} at {}: {}'.format(self.src, self.timestamp, self.amount)
        else:
            return 'transaction from {} to {} at {}: {}'.format(self.src, self.dest, self.timestamp, self.amount)

class PiggyBank(models.Model):
    account = models.ForeignKey(Account, related_name='piggy_banks', on_delete=models.PROTECT)
    name = models.CharField(max_length=60)
    category = models.CharField(max_length=30, default='Geral')
    icon = models.CharField(max_length=30, default='piggy')
    goal_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    current_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(current_balance__gte=0), name='nonnegative_piggy_balance'),
            models.CheckConstraint(condition=models.Q(archived_at__isnull=True) | models.Q(current_balance=0),
                                   name='archived_piggy_empty'),
        ]


class PiggyBankMovement(models.Model):
    reference_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    piggy_bank = models.ForeignKey(PiggyBank, related_name='movements', on_delete=models.PROTECT)
    requested_by = models.ForeignKey(Client, on_delete=models.PROTECT)
    movement_type = models.CharField(max_length=10)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    competence_date = models.DateField(null=True, blank=True)
    idempotency_key = models.CharField(max_length=128, null=True)
    receipt = models.JSONField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['requested_by', 'idempotency_key'], name='unique_piggy_request'),
            models.CheckConstraint(condition=models.Q(amount__gt=0), name='positive_piggy_amount'),
            models.UniqueConstraint(fields=['piggy_bank', 'competence_date'], name='unique_piggy_yield_date'),

        ]

class YieldSettings(models.Model):
    effective_from = models.DateField(unique=True)
    cdi_annual_rate = models.DecimalField(max_digits=9, decimal_places=8)
    cdi_percentage = models.DecimalField(max_digits=6, decimal_places=2, default=100)
    business_days_per_year = models.PositiveSmallIntegerField(default=252)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(cdi_annual_rate__gte=0, cdi_percentage__gte=0,
                                                       business_days_per_year__gt=0), name='valid_yield_policy'),
        ]


def quick_installment_defaults():
    return [6, 12, 24, 36]


class CreditPolicy(models.Model):
    version = models.CharField(max_length=32, unique=True)
    monthly_interest_rate = models.DecimalField(max_digits=8, decimal_places=6, default='0.019900')
    min_amount = models.DecimalField(max_digits=14, decimal_places=2, default=100)
    max_amount = models.DecimalField(max_digits=14, decimal_places=2, default=50000)
    min_installments = models.PositiveSmallIntegerField(default=1)
    max_installments = models.PositiveSmallIntegerField(default=36, validators=[MaxValueValidator(600)])
    quick_installments = models.JSONField(default=quick_installment_defaults, blank=True)
    default_preapproved_limit = models.DecimalField(max_digits=14, decimal_places=2, default=10000)
    fixed_fee = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    iof_rate = models.DecimalField(max_digits=8, decimal_places=6, default=0)
    is_active = models.BooleanField(default=True)
    effective_from = models.DateTimeField(auto_now_add=True)

    def clean(self):
        super().clean()
        if not isinstance(self.quick_installments, list) or any(
                type(n) is not int or not self.min_installments <= n <= self.max_installments
                for n in self.quick_installments):
            raise ValidationError({'quick_installments': 'Escolha prazos inteiros dentro da faixa da política.'})

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['is_active'], condition=models.Q(is_active=True), name='one_active_credit_policy'),
            models.CheckConstraint(condition=models.Q(min_amount__gt=0, max_amount__gte=models.F('min_amount'),
                min_installments__gte=1, max_installments__gte=models.F('min_installments'), max_installments__lte=600,
                monthly_interest_rate__gte=0, fixed_fee__gte=0, iof_rate__gte=0, default_preapproved_limit__gte=0),
                name='valid_credit_policy'),
        ]


class PurchaseIntent(models.Model):
    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    payer = models.ForeignKey(Account, related_name='purchases', on_delete=models.PROTECT)
    recipient = models.ForeignKey(Account, related_name='merchant_orders', on_delete=models.PROTECT)
    customer = models.ForeignKey(Client, related_name='purchase_orders', on_delete=models.PROTECT)
    merchant_name = models.CharField(max_length=150)
    order_reference = models.CharField(max_length=80)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    status = models.CharField(max_length=12, default='PENDING')
    confirmation_key = models.CharField(max_length=128, null=True)
    payment = models.OneToOneField(Transaction, null=True, on_delete=models.PROTECT)
    receipt = models.JSONField(null=True)

    class Meta:
        permissions = [('issue_purchase', 'Pode emitir pedidos para suas contas recebedoras')]
        constraints = [
            models.UniqueConstraint(fields=['recipient', 'order_reference'], name='unique_merchant_order'),
            models.UniqueConstraint(fields=['customer', 'confirmation_key'], name='unique_customer_confirmation'),
            models.CheckConstraint(condition=models.Q(amount__gt=0), name='positive_purchase_amount'),
        ]


class PurchasePasswordCounter(models.Model):
    scope = models.CharField(max_length=100, unique=True)
    failures = models.PositiveIntegerField(default=0)
    window_start = models.DateTimeField()
    blocked_until = models.DateTimeField(null=True)


class PurchaseEvent(models.Model):
    purchase = models.ForeignKey(PurchaseIntent, related_name='events', on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    outcome = models.CharField(max_length=40)
