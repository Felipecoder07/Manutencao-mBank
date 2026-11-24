from rest_framework import serializers

from .models import Account, Transaction


class AccountSerializer(serializers.ModelSerializer):
    available_balance = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = Account
        fields = ('id', 'iban', 'owner', 'balance', 'reserved_balance', 'available_balance')
        read_only_fields = ('owner', 'balance', 'reserved_balance')


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ('id', 'src', 'dest', 'amount', 'timestamp', 'transaction_type')
