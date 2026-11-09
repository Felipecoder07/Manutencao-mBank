from django.urls import path, re_path
from rest_framework.routers import DefaultRouter

from .views import (
    ClientListView, ClientDetailView, AccountListView, 
    TransactionListView, AccountCreate, TransactionCreate, 
    TransactionViewSet, AccountViewSet
)

app_name = 'bank'

transaction_router = DefaultRouter()
transaction_router.register(r'api/transactions', TransactionViewSet)

account_router = DefaultRouter()
account_router.register(r'api/accounts', AccountViewSet)

urlpatterns = transaction_router.urls + account_router.urls

urlpatterns += [
    path('clients/', ClientListView.as_view(), name='clients_list'),
    re_path(r'^clients/(?P<pk>\d+)$', ClientDetailView.as_view(), name='clients_detail'),
    path('accounts/', AccountListView.as_view(), name='accounts_list'),
    path('accounts/create', AccountCreate.as_view(), name='accounts_create'),
    re_path(r'^accounts/(?P<account_id>\d+)/transactions$', TransactionListView.as_view(), name='account_transactions'),
    path('transactions/', TransactionListView.as_view(), name='transactions_list'),
    path('transactions/create', TransactionCreate.as_view(), name='transactions_create'),
]