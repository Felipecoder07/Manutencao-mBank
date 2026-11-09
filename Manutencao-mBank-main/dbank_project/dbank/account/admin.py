from django.contrib import admin

# Register your models here.
from django.urls import reverse
from django.utils.html import format_html

from account.models import Client, Account, Transaction

CHANGE_URL_PATTERN = 'admin:{}_{}_change'
HTML_LINK_TEMPLATE = '<a href="{}">{}</a>'


class AdminAccout(admin.ModelAdmin):
    list_display = ('iban', 'created', 'balance', 'get_owner_name', 'is_open', 'nr_of_transactions')
    ordering = ('-created',)
    search_fields = ('iban', 'owner__name')

    def get_owner_name(self, obj):
        ct = obj.owner._meta  # content type
        url = reverse(CHANGE_URL_PATTERN.format(ct.app_label, ct.model_name), args=(obj.owner.pk,))
        return format_html(HTML_LINK_TEMPLATE, url, obj.owner.name)

    get_owner_name.short_description = 'owner'

    def nr_of_transactions(self, obj):
        transactions = Transaction.objects.extra(
            where=["src_id={0} OR dest_id={0}".format(obj.pk)]).values_list('id', flat=True)
        if transactions.count() == 0:
            return '0'
        url = '/admin/account/transaction/?pk__in={}'.format(str(list(transactions))[1:-1])
        return format_html(HTML_LINK_TEMPLATE, url, transactions.count())

    nr_of_transactions.short_description = 'Transactions'


class AdminTransaction(admin.ModelAdmin):
    list_display = ('get_type', 'timestamp', 'get_src', 'get_dest', 'amount')
    ordering = ('-timestamp',)
    list_display_links = None

    def get_type(self, obj):
        if obj.src is None:
            return 'deposit'
        elif obj.dest is None:
            return 'withdraw'
        else:
            return 'transaction'

    get_type.short_description = 'Type'

    def get_src(self, obj):
        if obj.src is None:
            return None
        ct = obj.src._meta  # content type
        url = reverse(CHANGE_URL_PATTERN.format(ct.app_label, ct.model_name), args=(obj.src.pk,))
        return format_html(HTML_LINK_TEMPLATE, url, obj.src.iban)

    get_src.short_description = 'Source'

    def get_dest(self, obj):
        if obj.dest is None:
            return None
        ct = obj.dest._meta  # content type
        url = reverse(CHANGE_URL_PATTERN.format(ct.app_label, ct.model_name), args=(obj.dest.pk,))
        return format_html(HTML_LINK_TEMPLATE, url, obj.dest.iban)

    get_dest.short_description = 'Destination'


class AdminClient(admin.ModelAdmin):
    list_display = ('name', 'list_accounts')

    def list_accounts(self, obj):
        accounts = obj.account_set.count()
        if accounts == 0:
            return '0'

        url = '/admin/account/account/?owner__id__exact={}'.format(obj.id)
        return format_html(HTML_LINK_TEMPLATE, url, accounts)

    list_accounts.short_description = 'Accounts'


admin.site.register(Account, AdminAccout)
admin.site.register(Transaction, AdminTransaction)
admin.site.register(Client, AdminClient)
