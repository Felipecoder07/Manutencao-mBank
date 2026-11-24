from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import OperationalError, connection, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.views.decorators.debug import sensitive_post_parameters
from django.utils.decorators import method_decorator
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Account, PurchaseEvent, PurchaseIntent, PurchasePasswordCounter


class OrderInput(serializers.Serializer):
    payer_iban = serializers.CharField(max_length=10)
    recipient_account_id = serializers.IntegerField(min_value=1)
    order_reference = serializers.CharField(max_length=80)
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0.01'))


class ConfirmationInput(serializers.Serializer):
    password = serializers.CharField(trim_whitespace=False, write_only=True, max_length=4096)
    idempotency_key = serializers.CharField(max_length=128)


def state(order):
    if order.status == 'PENDING' and order.expires_at <= timezone.now():
        return 'EXPIRED'
    return order.status


def summary(order):
    return {'reference': str(order.reference), 'order_reference': order.order_reference,
            'merchant_name': order.merchant_name, 'payer_account': '****' + order.payer.iban[-4:],
            'recipient_account': '****' + order.recipient.iban[-4:], 'currency': 'BRL',
            'amount': format(order.amount, '.2f'), 'created_at': order.created_at, 'expires_at': order.expires_at,
            'status': state(order), 'receipt': order.receipt}


def record(order, outcome):
    PurchaseEvent.objects.create(purchase=order, outcome=outcome)


def error(code, detail, status=409, **extra):
    return Response({'code': code, 'detail': detail, **extra}, status=status)


def password_error(request, order, password):
    now = timezone.now()
    window = timedelta(seconds=settings.PURCHASE_PASSWORD_WINDOW_SECONDS)
    origin = salted_hmac('purchase-origin', request.META.get('REMOTE_ADDR', 'unknown')).hexdigest()
    counters = []
    for scope in [f'customer:{order.customer_id}', f'origin:{origin}']:
        counter, _ = PurchasePasswordCounter.objects.select_for_update().get_or_create(
            scope=scope, defaults={'window_start': now})
        counters.append(counter)
    until = max((counter.blocked_until for counter in counters if counter.blocked_until), default=None)
    if until and until > now:
        record(order, 'PASSWORD_BLOCKED')
        return error('PASSWORD_BLOCKED', 'Aguarde para tentar novamente.', 429, retry_at=until)
    if request.user.check_password(password):
        # Other clients sharing this IP retain their origin-wide limit.
        PurchasePasswordCounter.objects.filter(pk=counters[0].pk).delete()
        return None
    for counter in counters:
        if counter.blocked_until or counter.window_start + window <= now:
            counter.failures = 0
            counter.window_start = now
            counter.blocked_until = None
        counter.failures += 1
        if counter.failures >= settings.PURCHASE_PASSWORD_MAX_ATTEMPTS:
            counter.blocked_until = now + timedelta(seconds=settings.PURCHASE_PASSWORD_BLOCK_SECONDS)
        counter.save()
    record(order, 'INVALID_PASSWORD')
    if any(counter.blocked_until for counter in counters):
        return error('PASSWORD_BLOCKED', 'Aguarde para tentar novamente.', 429,
                     retry_at=max(c.blocked_until for c in counters if c.blocked_until))
    return error('INVALID_PASSWORD', 'Senha incorreta.', 400)


@method_decorator(sensitive_post_parameters('password'), name='dispatch')
class PurchaseViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    lookup_value_regex = '[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'

    def initial(self, request, *args, **kwargs):
        if not request.is_secure():
            raise PermissionDenied('Use HTTPS para acessar compras.')
        super().initial(request, *args, **kwargs)

    def handle_exception(self, exc):
        if isinstance(exc, OperationalError) and connection.vendor == 'sqlite' and 'locked' in str(exc).lower():
            return error('ACCOUNT_BUSY', 'Tente novamente com a mesma referência e chave.', 503)
        return super().handle_exception(exc)

    def orders(self, request):
        return PurchaseIntent.objects.filter(customer=request.user, payer__owner=request.user).select_related('payer','recipient')

    def list(self, request):
        return Response([summary(order) for order in self.orders(request).order_by('-created_at')])

    def retrieve(self, request, pk=None):
        return Response(summary(get_object_or_404(self.orders(request), reference=pk)))

    @transaction.atomic
    def create(self, request):
        if not request.user.has_perm('account.issue_purchase'):
            raise PermissionDenied('Emissor de pedidos não autorizado.')
        form = OrderInput(data=request.data)
        form.is_valid(raise_exception=True)
        data = form.validated_data
        recipient = get_object_or_404(Account.objects.select_for_update(), owner=request.user,
                                      pk=data['recipient_account_id'], closed=None)
        payer = get_object_or_404(Account, iban=data['payer_iban'], closed=None)
        if payer.owner_id == recipient.owner_id:
            raise ValidationError({'payer_iban': 'Selecione a conta de um cliente.'})
        order, created = PurchaseIntent.objects.get_or_create(recipient=recipient, order_reference=data['order_reference'],
            defaults={'amount': data['amount'], 'payer': payer, 'customer_id': payer.owner_id,
                      'merchant_name': request.user.name or request.user.username,
                      'expires_at': timezone.now() + timedelta(seconds=settings.PURCHASE_TTL_SECONDS)})
        if (order.payer_id, order.amount) != (payer.pk, data['amount']):
            return error('ORDER_CONFLICT', 'Referência comercial já utilizada com outros dados.')
        if created:
            record(order, 'CREATED')
        return Response({'reference':str(order.reference), 'status':state(order)}, status=201 if created else 200)

    def locked_order(self, request, pk):
        order = get_object_or_404(self.orders(request).select_for_update(), reference=pk)
        if order.status != state(order):
            order.status = 'EXPIRED'
            order.save(update_fields=['status'])
            record(order, 'EXPIRED')
        return order

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def cancelar(self, request, pk=None):
        order = self.locked_order(request, pk)
        if order.status == 'PENDING':
            order.status = 'CANCELLED'
            order.save(update_fields=['status'])
            record(order, 'CANCELLED')
        if order.status != 'CANCELLED':
            return error('INVALID_STATE', 'Compra indisponível para cancelamento.')
        return Response(summary(order))

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def confirmar(self, request, pk=None):
        order = self.locked_order(request, pk)
        supplied = set(request.data) - {'password', 'idempotency_key'}
        if supplied:
            raise ValidationError({'detail': 'A confirmação aceita somente senha e chave.'})
        key = request.headers.get('Idempotency-Key', request.data.get('idempotency_key'))
        form = ConfirmationInput(data={'password':request.data.get('password'), 'idempotency_key':key})
        form.is_valid(raise_exception=True)
        key = form.validated_data['idempotency_key']
        if PurchaseIntent.objects.filter(customer=request.user, confirmation_key=key).exclude(pk=order.pk).exists():
            return error('IDEMPOTENCY_CONFLICT', 'Chave já usada em outra compra.')
        if order.status == 'PAID':
            return Response(summary(order))
        if order.status != 'PENDING':
            return error('INVALID_STATE', 'Compra cancelada ou expirada.')
        failure = password_error(request, order, form.validated_data['password'])
        if failure is not None:
            return failure
        if state(order) == 'EXPIRED':
            order.status = 'EXPIRED'
            order.save(update_fields=['status'])
            record(order, 'EXPIRED')
            return error('INVALID_STATE', 'Compra expirada.')
        try:
            entry = order.payer.transfer(order.recipient, order.amount, actor=request.user)
        except ValueError as exc:
            code = {'Insufficient available balance.':'INSUFFICIENT_AVAILABLE_BALANCE',
                    'Account is closed.':'ACCOUNT_CLOSED'}.get(str(exc), 'PAYMENT_UNAVAILABLE')
            record(order, code)
            return error(code, 'Pagamento recusado. Consulte a situação das contas e o saldo disponível.')
        entry.transaction_type = 'PURCHASE'
        entry.save(update_fields=['transaction_type'])
        order.payment = entry
        order.status = 'PAID'
        order.confirmation_key = key
        order.receipt = {'transaction_id':entry.pk, 'reference':str(order.reference),
                         'paid_at':entry.timestamp.isoformat(), 'amount':format(entry.amount,'.2f'),
                         'currency':'BRL', 'merchant_name':order.merchant_name, 'order_reference':order.order_reference}
        order.save(update_fields=['payment','status','confirmation_key','receipt'])
        record(order, 'PAID')
        return Response(summary(order))
