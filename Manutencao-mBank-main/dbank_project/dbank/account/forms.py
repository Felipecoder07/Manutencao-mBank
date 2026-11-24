import uuid
from django import forms
from django.forms import ModelForm

from account.models import Account, Transaction


class AccountForm(ModelForm):
    class Meta:
        model = Account
        fields = ['iban']

    def __init__(self, *args, **kwargs):
        owner = kwargs.pop('owner')
        self.owner = owner
        super(AccountForm, self).__init__(*args, **kwargs)


class TransactionForm(ModelForm):
    request_key = forms.UUIDField(initial=uuid.uuid4, widget=forms.HiddenInput, required=False)

    class Meta:
        model = Transaction
        fields = ['src', 'dest', 'amount']

    def __init__(self, *args, **kwargs):
        super(TransactionForm, self).__init__(*args, **kwargs)
        self.fields['src'] = kwargs['initial']['src']
        self.fields['dest'] = kwargs['initial']['dest']


