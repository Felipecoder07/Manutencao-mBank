from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from django.db import OperationalError, connection, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from .models import Account, PiggyBank, PiggyBankMovement, YieldSettings
from .services.piggy_yield import apply_yield, period_dates


class Conflict(APIException):
    status_code = 409

    def __init__(self, code, message):
        super().__init__({'code': code, 'detail': message})


class Objective(serializers.ModelSerializer):
    goal_amount = serializers.DecimalField(max_digits=14, decimal_places=2, allow_null=True,
                                           required=False, min_value=Decimal('0.01'))
    progress_percent = serializers.SerializerMethodField()
    goal_reached = serializers.SerializerMethodField()

    def get_progress_percent(self, obj):
        if obj.goal_amount:
            return float(round(min(Decimal('999.99'), obj.current_balance * 100 / obj.goal_amount), 2))

    def get_goal_reached(self, obj):
        return bool(obj.goal_amount and obj.current_balance >= obj.goal_amount)

    class Meta:
        model = PiggyBank
        fields = ['id', 'account_id', 'name', 'category', 'icon', 'goal_amount', 'current_balance',
                  'progress_percent', 'goal_reached', 'created_at', 'archived_at']
        read_only_fields = ['account_id', 'current_balance', 'archived_at']


class MovementInput(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0.01'))
    idempotency_key = serializers.CharField(max_length=128)


class HistoryQuery(serializers.Serializer):
    days = serializers.IntegerField(min_value=1, max_value=36500, required=False)
    type = serializers.ChoiceField(choices=['DEPOSIT', 'WITHDRAW', 'YIELD'], required=False)
    piggy_bank_id = serializers.IntegerField(min_value=1, required=False)


def account_id(value):
    return serializers.IntegerField(min_value=1).run_validation(value)


class PiggyBankViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = Objective
    http_method_names = ['get', 'post', 'patch', 'head', 'options']
    lookup_value_regex = '[0-9]+'

    def handle_exception(self, exc):
        if isinstance(exc, OperationalError) and connection.vendor == 'sqlite' and 'locked' in str(exc).lower():
            return Response({'code': 'ACCOUNT_BUSY', 'detail': 'Tente novamente com a mesma chave.'},
                            status=503, headers={'Retry-After': '1'})
        return super().handle_exception(exc)

    def get_queryset(self):
        banks = PiggyBank.objects.filter(account__owner=self.request.user).order_by('pk')
        selected = self.request.query_params.get('account_id')
        if selected is not None:
            banks = banks.filter(account_id=account_id(selected))
        if self.action == 'list' and self.request.query_params.get('include_archived') != 'true':
            banks = banks.filter(archived_at__isnull=True)
        return banks

    @transaction.atomic
    def create(self, request):
        accounts = Account.objects.select_for_update().filter(owner=request.user)
        if 'account_id' in request.data:
            account = get_object_or_404(accounts, pk=account_id(request.data['account_id']))
        else:
            candidates = list(accounts.filter(closed=None)[:2])
            if len(candidates) != 1:
                raise ValidationError({'account_id': 'Selecione uma conta aberta.'})
            account = candidates[0]
        if account.closed:
            raise Conflict('ACCOUNT_CLOSED', 'Conta encerrada.')
        serializer = Objective(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(account=account)
        return Response(serializer.data, status=201)

    @action(detail=False)
    @transaction.atomic
    def dashboard(self, request):
        today = timezone.localdate()
        accounts = Account.objects.filter(owner=request.user)
        if 'account_id' in request.query_params:
            selected = get_object_or_404(accounts, pk=account_id(request.query_params['account_id']))
            accounts = accounts.filter(pk=selected.pk)
        banks = PiggyBank.objects.filter(account__in=accounts)
        history = PiggyBankMovement.objects.filter(piggy_bank__in=banks)
        objectives = list(banks.filter(archived_at__isnull=True).order_by('pk'))
        available = sum(account.available_balance for account in accounts if account.is_open())
        monthly = history.filter(movement_type='YIELD', competence_date__range=(today.replace(day=1), today))
        policy = YieldSettings.objects.filter(effective_from__lte=today).order_by('-effective_from').first()
        policy_data = None
        if policy:
            policy_data = {'effective_from': policy.effective_from, 'cdi_annual_rate': str(policy.cdi_annual_rate),
                           'cdi_percentage': str(policy.cdi_percentage), 'business_days_per_year': policy.business_days_per_year}
        return Response({'total_saved': format(sum(bank.current_balance for bank in objectives), '.2f'),
                         'active_count': len(objectives), 'available_balance': format(available, '.2f'),
                         'monthly_yield_total': format(sum(monthly.values_list('amount', flat=True)), '.2f'),
                         'yield_policy': policy_data, 'objectives': Objective(objectives, many=True).data,
                         'recent_history': self.history_rows(history.filter(
                             created_at__gte=timezone.now() - timedelta(days=30)).order_by('-created_at', '-pk'))})

    def retrieve(self, request, *args, **kwargs):
        bank = self.get_object()
        history = bank.movements.all()
        earned = sum(history.filter(movement_type='YIELD').values_list('amount', flat=True))
        return Response({**Objective(bank).data, 'total_yield': format(earned, '.2f'),
                         'recent_history': self.history_rows(history.filter(
                             created_at__gte=timezone.now() - timedelta(days=30)).order_by('-created_at', '-pk'))})

    @action(detail=False, methods=['post'], url_path='aplicar-rendimento', permission_classes=[IsAdminUser])
    def process_yield(self, request):
        preview = serializers.BooleanField().run_validation(request.data.get('preview', False))
        try:
            days = period_dates(request.data.get('date'), request.data.get('month'))
            return Response(apply_yield(days, preview=preview))
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)}) from exc

    def locked_pair(self, pk):
        bank = get_object_or_404(self.get_queryset(), pk=pk)
        account = get_object_or_404(Account.objects.select_for_update(), pk=bank.account_id,
                                    owner=self.request.user)
        return account, PiggyBank.objects.select_for_update().get(pk=bank.pk)

    def require_active(self, account, bank):
        if account.closed or bank.archived_at:
            raise Conflict('INACTIVE', 'Conta encerrada ou cofrinho arquivado.')

    @transaction.atomic
    def partial_update(self, request, pk=None):
        account, bank = self.locked_pair(pk)
        self.require_active(account, bank)
        serializer = Objective(bank, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def arquivar(self, request, pk=None):
        account, bank = self.locked_pair(pk)
        self.require_active(account, bank)
        if bank.current_balance:
            raise Conflict('PIGGY_BANK_NOT_EMPTY', 'Resgate o saldo antes de arquivar.')
        bank.archived_at = timezone.now()
        bank.save(update_fields=['archived_at'])
        return Response(Objective(bank).data)

    @transaction.atomic
    def move(self, request, pk, kind):
        data = MovementInput(data={'amount': request.data.get('amount'), 'idempotency_key':
            request.headers.get('Idempotency-Key', request.data.get('idempotency_key'))})
        data.is_valid(raise_exception=True)
        amount = data.validated_data['amount']
        key = data.validated_data['idempotency_key']
        account, bank = self.locked_pair(pk)
        previous = PiggyBankMovement.objects.filter(requested_by=request.user, idempotency_key=key).first()
        if previous:
            if (previous.piggy_bank_id, previous.movement_type, previous.amount) != (bank.pk, kind, amount):
                raise Conflict('IDEMPOTENCY_CONFLICT', 'Chave utilizada em outra operação.')
            return Response(previous.receipt)
        self.require_active(account, bank)
        if kind == 'DEPOSIT' and amount > account.available_balance:
            raise Conflict('INSUFFICIENT_AVAILABLE_BALANCE', 'Saldo disponível insuficiente.')
        if kind == 'WITHDRAW' and amount > bank.current_balance:
            raise Conflict('INSUFFICIENT_RESERVE', 'Saldo insuficiente neste cofrinho.')
        change = amount if kind == 'DEPOSIT' else -amount
        bank.current_balance += change
        account.reserved_balance += change
        bank.save(update_fields=['current_balance'])
        account.save(update_fields=['reserved_balance'])
        reference = uuid4()
        receipt = {'piggy_bank': Objective(bank).data, 'available_balance': format(account.available_balance, '.2f'),
                   'movement': {'reference_id': str(reference), 'movement_type': kind, 'amount': format(amount, '.2f')}}
        PiggyBankMovement.objects.create(reference_id=reference, piggy_bank=bank, requested_by=request.user,
                                         movement_type=kind, amount=amount, idempotency_key=key, receipt=receipt)
        return Response(receipt)

    @action(detail=True, methods=['post'])
    def guardar(self, request, pk=None):
        return self.move(request, pk, 'DEPOSIT')

    @action(detail=True, methods=['post'])
    def resgatar(self, request, pk=None):
        return self.move(request, pk, 'WITHDRAW')

    @action(detail=True, url_path='extrato')
    def history(self, request, pk=None):
        return self.statement(request, self.get_object().movements.all())

    @action(detail=False)
    def extrato(self, request):
        return self.statement(request, PiggyBankMovement.objects.filter(piggy_bank__in=self.get_queryset()))

    def statement(self, request, movements):
        query = HistoryQuery(data=request.query_params)
        query.is_valid(raise_exception=True)
        filters = query.validated_data
        if 'days' in filters:
            movements = movements.filter(created_at__gte=timezone.now() - timedelta(days=filters['days']))
        if 'type' in filters:
            movements = movements.filter(movement_type=filters['type'])
        if 'piggy_bank_id' in filters:
            movements = movements.filter(piggy_bank_id=filters['piggy_bank_id'])
        paginator = PageNumberPagination()
        paginator.page_size = 25
        page = paginator.paginate_queryset(movements.order_by('-created_at', '-pk'), request)
        return paginator.get_paginated_response(self.history_rows(page))

    @staticmethod
    def history_rows(rows):
        return [
            {**row.receipt['movement'], 'created_at': row.created_at, 'piggy_bank_id': row.piggy_bank_id}
            for row in rows
        ]
