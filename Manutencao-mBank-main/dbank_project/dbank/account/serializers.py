from rest_framework import serializers

from .models import Account, Transaction


class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = ('id', 'iban', 'owner')
        read_only_fields = ('owner',)


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ('id', 'src', 'dest', 'amount', 'timestamp')
