from calendar import monthrange
from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal('0.01')


def cents(value):
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def rates(policy):
    rate = policy.monthly_interest_rate
    return {'monthly_interest_rate': format(rate, '.6f'),
            'annual_effective_rate': format((1 + rate) ** 12 - 1, '.6f')}


def simulate_loan(policy, principal, installments, reference_date):
    if not policy.min_amount <= principal <= policy.max_amount:
        raise ValueError('Valor fora da faixa da política de crédito.')
    if not policy.min_installments <= installments <= policy.max_installments:
        raise ValueError('Prazo fora da faixa da política de crédito.')

    rate = policy.monthly_interest_rate
    payment = cents(principal * rate / (1 - (1 + rate) ** -installments) if rate else principal / installments)
    balance = principal
    total_interest = Decimal('0.00')
    schedule = []
    for number in range(1, installments + 1):
        interest = cents(balance * rate)
        amortization = balance if number == installments else payment - interest
        if amortization <= 0 or (number < installments and amortization >= balance):
            raise ValueError('O valor e o prazo não permitem amortização em centavos em todas as parcelas.')
        month_index = reference_date.month - 1 + number
        year = reference_date.year + month_index // 12
        month = month_index % 12 + 1
        due = reference_date.replace(year=year, month=month, day=min(reference_date.day, monthrange(year, month)[1]))
        schedule.append({'number': number, 'due_date': due.isoformat(), 'opening_balance': str(balance),
                         'interest_amount': str(interest), 'amortization_amount': str(amortization),
                         'total_amount': str(amortization + interest), 'closing_balance': str(balance - amortization)})
        balance -= amortization
        total_interest += interest

    tax = cents(principal * policy.iof_rate)
    fees = tax + policy.fixed_fee
    return {'principal_amount': str(principal), 'installments': installments, **rates(policy),
            'installment_amount': schedule[0]['total_amount'], 'last_installment_amount': schedule[-1]['total_amount'],
            'has_last_installment_diff': schedule[0]['total_amount'] != schedule[-1]['total_amount'],
            'fixed_fee': str(policy.fixed_fee), 'iof_amount': str(tax), 'total_fees': str(fees),
            'total_interest': str(total_interest), 'total_payable': str(principal + total_interest + fees),
            'policy_version': policy.version, 'reference_date': reference_date.isoformat(), 'currency': 'BRL',
            'assumptions': ['Tabela Price com parcelas mensais.', 'Encargos pagos à parte na origem.',
                            'Vencimento no mesmo dia do mês ou no último dia quando necessário.'],
            'installments_schedule': schedule}
