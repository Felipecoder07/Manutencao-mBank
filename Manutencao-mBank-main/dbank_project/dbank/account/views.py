from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q

# Create your views here.
from django.forms import ModelChoiceField
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.views.generic import TemplateView, DetailView, ListView, CreateView
from rest_framework.response import Response

from .forms import TransactionForm
from .models import Client, Account, Transaction
from rest_framework import generics, viewsets, mixins, status

from .serializers import AccountSerializer, TransactionSerializer


class HomePage(TemplateView):
    template_name = 'homepage.html'


class ClientListView(LoginRequiredMixin, ListView):
    model = Client


class ClientDetailView(LoginRequiredMixin, DetailView):
    model = Client


class AccountListView(LoginRequiredMixin, ListView):
    model = Account

    def get_queryset(self):
        return Account.objects.filter(owner=self.request.user)


class TransactionListView(LoginRequiredMixin, ListView):
    model = Transaction
    ordering = ['-timestamp']

    def get_queryset(self):
        ordering = self.get_ordering()

        if 'account_id' in self.kwargs:
            account_id = self.kwargs.get('account_id')
            return Transaction.objects.filter(Q(src__id=account_id) | Q(dest__id=account_id)).order_by(*ordering)
        else:
            client = self.request.user
            return Transaction.objects.filter(Q(src__owner=client) | Q(dest__owner=client)).order_by(*ordering)


class AccountCreate(LoginRequiredMixin, CreateView):
    model = Account
    fields = ['iban']
    success_url = reverse_lazy('bank:accounts_list')

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


class TransactionCreate(LoginRequiredMixin, CreateView):
    model = Transaction
    success_url = reverse_lazy('bank:transactions_list')
    form_class = TransactionForm

    def get_initial(self):
        return {
            'src': ModelChoiceField(queryset=Account.objects.filter(owner=self.request.user, closed=None),
                                    empty_label='no account', required=False),
            'dest': ModelChoiceField(queryset=Account.objects.filter(closed=None), empty_label='no account',
                                     required=False),
        }

    def form_valid(self, form):
        transaction = form.instance
        src = transaction.src
        dest = transaction.dest
        amount = transaction.amount

        try:
            if src and dest:
                src.transfer(dest, amount)
            elif dest:
                dest.deposit(amount)
            elif src:
                src.withdraw(amount)
            else:
                form.add_error(None, 'Choose a source and/or a destination account.')
                return self.form_invalid(form)
        except ValueError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)

        return HttpResponseRedirect(self.success_url)


class TransactionViewSet(viewsets.ViewSet):
    queryset = Transaction.objects.all()

    def list(self, request, format='json'):
        q1 = Transaction.objects.filter(src__owner=self.request.user)
        q2 = Transaction.objects.filter(dest__owner=self.request.user)
        serializer = TransactionSerializer(q1 | q2, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        queryset = Transaction.objects.get(id=pk)
        serializer = TransactionSerializer(queryset)
        return Response(serializer.data)


class AccountViewSet(mixins.CreateModelMixin,
                     mixins.ListModelMixin,
                     viewsets.GenericViewSet):
    serializer_class = AccountSerializer
    queryset = Account.objects.all()

    def list(self, request):
        serializer = AccountSerializer(self.get_queryset(), many=True)
        return Response(serializer.data)

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(owner=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def get_queryset(self):
        return Account.objects.filter(owner=self.request.user)



