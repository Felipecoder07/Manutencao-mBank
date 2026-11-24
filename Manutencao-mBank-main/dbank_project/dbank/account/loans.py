from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Account, CreditPolicy
from .services.loans import rates, simulate_loan


class PolicyUnavailable(APIException):
    status_code = 503
    default_detail = {'code': 'POLICY_UNAVAILABLE', 'detail': 'Política de crédito indisponível.'}


class SimulationInput(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    installments = serializers.IntegerField(min_value=1)
    account_id = serializers.IntegerField(min_value=1, required=False)


class LoanSimulationViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def terms(self, user):
        policy = CreditPolicy.objects.filter(is_active=True, effective_from__lte=timezone.now()).first()
        if policy is None:
            raise PolicyUnavailable()
        limit = user.preapproved_limit if user.preapproved_limit is not None else policy.default_preapproved_limit
        return policy, limit, Account.objects.filter(owner=user, closed=None).order_by('pk')

    @action(detail=False)
    def config(self, request):
        policy, limit, accounts = self.terms(request.user)
        return Response({'policy_version': policy.version, 'currency': 'BRL', **rates(policy),
                         'preapproved_limit_total': format(limit, '.2f'), 'preapproved_limit_available': format(limit, '.2f'),
                         'min_amount': str(policy.min_amount), 'max_amount': str(policy.max_amount),
                         'min_installments': policy.min_installments, 'max_installments': policy.max_installments,
                         'quick_installments': policy.quick_installments, 'accounts': list(accounts.values('id', 'iban'))})

    @action(detail=False, methods=['post'])
    def simular(self, request):
        form = SimulationInput(data=request.data)
        form.is_valid(raise_exception=True)
        data = form.validated_data
        policy, limit, accounts = self.terms(request.user)
        if 'account_id' in data:
            account = get_object_or_404(accounts, pk=data['account_id'])
        else:
            options = list(accounts[:2])
            if len(options) != 1:
                raise ValidationError({'account_id': 'Selecione uma conta aberta de sua titularidade.'})
            account = options[0]
        try:
            result = simulate_loan(policy, data['amount'], data['installments'], timezone.localdate())
        except ValueError as exc:
            raise ValidationError({'code': 'INVALID_SIMULATION', 'detail': str(exc)}) from exc
        result.update(account_id=account.pk, can_contract=data['amount'] <= limit,
                      preapproved_limit_available=format(limit, '.2f'))
        if not result['can_contract']:
            result['exceeds_limit_message'] = 'O valor solicitado supera o limite pré-aprovado disponível.'
        return Response(result)
