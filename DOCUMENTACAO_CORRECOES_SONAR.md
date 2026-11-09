# Diário de Correções e Manutenção de Código (SonarCloud)

**Projeto:** `Manutencao-mBank`  
**Objetivo:** Registrar o histórico de melhorias, refatorações e correções de segurança recomendadas pelo SonarCloud, documentando o estado anterior (**Antes**), a alteração realizada (**Depois**) e a justificativa técnica (**Por que foi corrigido**).

---

## Índice de Correções

- [Lote 1: Correções Rápidas (Limpeza, Tags HTML & ARIA)](#lote-1-correções-rápidas-limpeza-tags-html--aria)
  - [1.1. Remoção de Papel ARIA Redundante em Formulário (`Web:S6822`)](#11-remoção-de-papel-aria-redundante-em-formulário-webs6822)
  - [1.2. Inclusão de `<title>` na Página de Redirecionamento Swagger (`Web:PageWithoutTitleCheck`)](#12-inclusão-de-title-na-página-de-redirecionamento-swagger-webpagewithouttitlecheck)
  - [1.3. Ocultação de SVG Decorativo para Tecnologias Assistivas (`Web:ImgWithoutAltCheck`)](#13-ocultação-de-svg-decorativo-para-tecnologias-assistivas-webimgwithoutaltcheck)
  - [1.4. Remoção de Código Comentado Inativo (`python:S125`)](#14-remoção-de-código-comentado-inativo-pythons125)
- [Lote 2: Backend e Boas Práticas Python / Django](#lote-2-backend-e-boas-práticas-python--django) *(Próximo)*
- [Lote 3: Segurança e Variáveis de Ambiente](#lote-3-segurança-e-variáveis-de-ambiente) *(Planejado)*
- [Lote 4: Acessibilidade Completa dos Templates Web](#lote-4-acessibilidade-completa-dos-templates-web) *(Planejado)*

---

## Lote 1: Correções Rápidas (Limpeza, Tags HTML & ARIA)

### 1.1. Remoção de Papel ARIA Redundante em Formulário (`Web:S6822`)
* **Severidade:** MAJOR (Code Smell)
* **Arquivo:** [`Manutencao-mBank-main/dbank_project/dbank/templates/account/account_form.html`](file:///c:/Users/Mateus/Downloads/Manutencao-mBank-main%20(1)/Manutencao-mBank-main/dbank_project/dbank/templates/account/account_form.html)

#### 🔍 Diagnóstico e Justificativa Técnica
De acordo com os padrões da W3C (HTML5 / WAI-ARIA), elementos nativos já possuem papéis semânticos implícitos. O elemento `<form>` já tem, por definição, o papel `role="form"`. Declarar `role="form"` explicitamente gera código redundante e desnecessário, sendo apontado pelo SonarCloud como má prática de acessibilidade.

#### 🔴 Antes
```html
<form action="" method="post" role="form">
    {% csrf_token %}
    {{ form.as_p }}
    <input type="submit" value="Create" />
</form>
```

#### 🟢 Depois
```html
<form action="" method="post">
    {% csrf_token %}
    {{ form.as_p }}
    <input type="submit" value="Create" />
</form>
```

---

### 1.2. Inclusão de `<title>` na Página de Redirecionamento Swagger (`Web:PageWithoutTitleCheck`)
* **Severidade:** MAJOR (Bug)
* **Arquivo:** [`Manutencao-mBank-main/dbank_project/docs/swagger/oauth2-redirect.html`](file:///c:/Users/Mateus/Downloads/Manutencao-mBank-main%20(1)/Manutencao-mBank-main/dbank_project/docs/swagger/oauth2-redirect.html)

#### 🔍 Diagnóstico e Justificativa Técnica
A regra de acessibilidade WCAG 2.1 (Critério 2.4.2 - Page Titled) e os padrões HTML5 exigem que todo documento web possua um elemento `<title>` no `<head>`. Isso permite que usuários que utilizam navegadores e leitores de tela identifiquem a finalidade da página assim que ela é aberta.

#### 🔴 Antes
```html
<!doctype html>
<html lang="en-US">
<body onload="run()">
</body>
</html>
```

#### 🟢 Depois
```html
<!doctype html>
<html lang="en-US">
<head>
    <meta charset="utf-8">
    <title>Swagger UI: OAuth2 Redirect</title>
</head>
<body onload="run()">
</body>
</html>
```

---

### 1.3. Ocultação de SVG Decorativo para Tecnologias Assistivas (`Web:ImgWithoutAltCheck`)
* **Severidade:** MINOR (Code Smell)
* **Arquivo:** [`Manutencao-mBank-main/dbank_project/docs/swagger/index.html`](file:///c:/Users/Mateus/Downloads/Manutencao-mBank-main%20(1)/Manutencao-mBank-main/dbank_project/docs/swagger/index.html)

#### 🔍 Diagnóstico e Justificativa Técnica
O SonarCloud exige que imagens e vetores gráficos forneçam uma descrição textual acessível (`title`, `aria-label` ou `aria-labelledby`) ou, caso sejam elementos utilitários/decorativos que não transmitem conteúdo direto ao usuário, sejam marcados explicitamente com `aria-hidden="true"`. O bloco `<svg>` em questão contém apenas definições internas (`<defs>` e `<symbol>`) invisíveis na tela inicial do Swagger.

#### 🔴 Antes
```html
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" style="position:absolute;width:0;height:0">
  <defs>
    <symbol viewBox="0 0 20 20" id="unlocked">
```

#### 🟢 Depois
```html
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" aria-hidden="true" style="position:absolute;width:0;height:0">
  <defs>
    <symbol viewBox="0 0 20 20" id="unlocked">
```

---

### 1.4. Remoção de Código Comentado Inativo (`python:S125`)
* **Severidade:** MAJOR (Code Smell)
* **Arquivos Afetados:**
  1. `dbank_project/dbank/account/admin.py`
  2. `dbank_project/dbank/account/models.py`
  3. `dbank_project/dbank/account/urls.py`
  4. `dbank_project/dbank/account/views.py`

#### 🔍 Diagnóstico e Justificativa Técnica
Código comentado que não está em uso reduz a legibilidade, gera confusão para novos desenvolvedores (dúvida se o código está desativado temporariamente ou se foi esquecido) e polui a base de código (*Clean Code*). Como o projeto está sob controle de versão com Git, qualquer implementação legada ou protótipo pode ser resgatado no histórico de commits.

#### A) `admin.py`
* **🔴 Antes:**
```python
class AdminAccout(admin.ModelAdmin):
    list_display = ('iban', 'created', 'balance', 'get_owner_name', 'is_open', 'nr_of_transactions')
    ordering = ('-created',)
    search_fields = ('iban', 'owner__name')
    # list_filter = ('owner',)
    # exclude = ('closed', 'balance',)

    def get_owner_name(self, obj):
```
* **🟢 Depois:**
```python
class AdminAccout(admin.ModelAdmin):
    list_display = ('iban', 'created', 'balance', 'get_owner_name', 'is_open', 'nr_of_transactions')
    ordering = ('-created',)
    search_fields = ('iban', 'owner__name')

    def get_owner_name(self, obj):
```

#### B) `models.py`
* **🔴 Antes:**
```python
    def __str__(self):
        return '{} ({}) {}'.format(self.iban, self.owner.name, self.balance)

    # def get_absolute_url(self):
    #     # from django.urls import reverse
    #     return reverse('account.views.details', args=[str(self.id)])


class Transaction(models.Model):
```
* **🟢 Depois:**
```python
    def __str__(self):
        return '{} ({}) {}'.format(self.iban, self.owner.name, self.balance)


class Transaction(models.Model):
```

#### C) `urls.py`
* **🔴 Antes:**
```python
urlpatterns = transaction_router.urls + account_router.urls

urlpatterns += [
    # path('', HomePage.as_view(), name='home'),
    # path('api/accounts/', AccountListAPIView.as_view(), name='account_list_api'),
    # path('api/transactions/', TransactionListAPIView.as_view(), name='transaction_list_api'),

    path('clients/', ClientListView.as_view(), name='clients_list'),
```
* **🟢 Depois:**
```python
urlpatterns = transaction_router.urls + account_router.urls

urlpatterns += [
    path('clients/', ClientListView.as_view(), name='clients_list'),
```

#### D) `views.py`
* **🔴 Antes:**
```python
        return HttpResponseRedirect(self.success_url)


# class AccountListAPIView(generics.ListCreateAPIView):
#     serializer_class = AccountSerializer
#
#     def get_queryset(self):
#         return Account.objects.filter(owner=self.request.user)


# class TransactionListAPIView(generics.ListCreateAPIView):
#     # queryset = Transaction.objects.all()
#     serializer_class = TransactionSerializer
#
#     def get_queryset(self):
#         q1 = Transaction.objects.filter(src__owner=self.request.user)
#         q2 = Transaction.objects.filter(dest__owner=self.request.user)
#         return q1 | q2


class TransactionViewSet(viewsets.ViewSet):
```
* **🟢 Depois:**
```python
        return HttpResponseRedirect(self.success_url)


class TransactionViewSet(viewsets.ViewSet):
```
