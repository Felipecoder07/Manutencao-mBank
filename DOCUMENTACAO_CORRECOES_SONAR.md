# Diário de Correções e Manutenção de Código (SonarCloud)

## Lote 4: Acessibilidade dos Templates Web

### 4.1. Estrutura explícita dos breadcrumbs

**Regra/severidade:** `Web:ItemTagNotWithinContainerTagCheck` — MINOR.
**Arquivos:** `templates/account/account_list.html`, `client_detail.html`,
`client_list.html` e `transaction_list.html`.

**Diagnóstico:** os `<li>` dos templates filhos já recebiam um `<ol>` de
`base.html`. O alerta nos fragmentos não demonstrava erro no HTML final. Adicionar
outra lista dentro do bloco antigo criaria aninhamento incorreto.

**🔴 Antes (contas):**
```html
{% block breadcrumbs %}
    <li><a href="{% url 'bank:accounts_list' %}">Accounts</a></li>
{% endblock %}
```

**🟢 Depois:**
```html
{% block breadcrumbs_container %}
    <nav aria-label="Breadcrumb">
        <ol class="breadcrumb">
            <li><a href="{% url 'home' %}">Home</a></li>
            <li><a href="{% url 'bank:accounts_list' %}" aria-current="page">Accounts</a></li>
        </ol>
    </nav>
{% endblock %}
```

**Justificativa:** substituir o contêiner inteiro torna a lista explícita nos quatro
arquivos sem duplicar o contêiner herdado. Preservados Home, os itens intermediários
e os destinos. Adicionados nome acessível e indicação da página atual. Na lista de
transações filtrada por conta, o link para todas as transações não recebe
`aria-current`, pois aponta para outra página.

### 4.2. Links com semântica nativa

**Regras/severidades:** `Web:S6819` — MAJOR;
`Web:MouseEventWithoutKeyboardEquivalentCheck` — MINOR.
**Arquivos:** `templates/homepage.html`, `templates/account/account_list.html`
e `templates/account/transaction_list.html`.

**Diagnóstico:** sete links de navegação eram anunciados como botões pelo atributo
`role="button"`, criando uma expectativa de interação diferente da de links.

**🔴 Antes:**
```html
<a class="btn btn-primary" href="{% url 'bank:transactions_create' %}" role="button">Make Transaction</a>
<a class="btn btn-default" href="#" role="button">View details &raquo;</a>
```

**🟢 Depois:**
```html
<a class="btn btn-primary" href="{% url 'bank:transactions_create' %}">Make Transaction</a>
<a class="btn btn-default" href="#">View details &raquo;</a>
```

**Justificativa:** links com `href` têm foco por Tab e ativação por Enter nativos.
Remover o papel incorreto preserva destinos e classes Bootstrap sem adicionar
handlers de teclado artificiais. Os quatro links demonstrativos da homepage
continuam com `href="#"`; esta correção não cria conteúdo ou novos destinos.

### 4.3. Navegação para ações de conta

**Regra/severidade:** `Web:S6819` — MAJOR.
**Arquivo:** `templates/account/account_list.html`.

**Diagnóstico:** links agrupados em `div` com `role="group"` e nome acessível
não descritivo (`...`).

**🔴 Antes:**
```html
<div class="btn-group" role="group" aria-label="...">
    <!-- Links de criação de conta e transação -->
</div>
```

**🟢 Depois:**
```html
<nav class="btn-group" aria-label="Account actions">
    <a class="btn btn-primary" href="{% url 'bank:accounts_create' %}">New Account</a>
    <a class="btn btn-primary" href="{% url 'bank:transactions_create' %}">Make Transaction</a>
</nav>
```

**Justificativa:** o conjunto leva a outras páginas e passa a usar navegação
semântica nativa com nome descritivo. Mantida a classe visual `btn-group`.

### Validação do lote 4

- Três testes aprovados, incluindo renderização de oito páginas; Django sem erros.
- Verificação dos cinco templates renderizados com `HTMLParser`: tags balanceadas,
  `<li>` com pai `<ol>` ou `<ul>`, um breadcrumb por página, sem listas de breadcrumb
  aninhadas e sem os papéis ARIA removidos.
- Confirmados os destinos dos links de criação de conta e transação.
- Reanálise SonarCloud e avaliação interativa com leitor de tela não realizadas;
  esta validação não representa uma auditoria completa de acessibilidade.

---

## Revisão de regressões após o lote 2

### Ambiente Python e resolução de imports no editor

**Diagnóstico:** nesta sessão, `python` resolvia para o alias de WindowsApps e não
executava. O Python funcional foi localizado por `uv python find`. Não foi possível
ler o painel Problemas do editor; portanto, não se atribuem todas as marcações das
pastas a essa causa. O projeto não tinha configuração de interpretador no workspace.

**Regra/severidade:** configuração do ambiente; sem regra Sonar associada.

**🔴 Antes:** workspace sem caminho explícito para o interpretador e para a raiz
dos módulos `account` e `dbank`.

**🟢 Depois:** criado o ambiente ignorado pelo Git
`Manutencao-mBank-main/dbank_project/.venv`, com as versões de `requirements.txt`;
adicionado `.vscode/settings.json`:

```json
{
    "python.defaultInterpreterPath": "${workspaceFolder}/Manutencao-mBank-main/dbank_project/.venv/Scripts/python.exe",
    "python.analysis.extraPaths": [
        "${workspaceFolder}/Manutencao-mBank-main/dbank_project/dbank"
    ]
}
```

**Justificativa:** permitir que o editor encontre as dependências e os módulos
locais sem desativar diagnósticos. Se o VS Code já tiver um interpretador selecionado,
usar `Python: Select Interpreter` para selecionar esse executável; o valor padrão
não substitui necessariamente uma seleção anterior. O ambiente virtual é local e
deve ser recriado em outra máquina a partir de `requirements.txt`.

### Migração complementar do telefone

**Regra/severidade:** complemento da correção `python:S6553` (MAJOR) do lote 2.

**Diagnóstico:** o modelo passou a usar `blank=True`, mas só existia a migração
inicial com `null=True`. Alterar o modelo não atualiza o esquema do banco.
Além disso, `blank` controla validação e `null` controla armazenamento; não são
opções equivalentes. A alteração também permite omitir o telefone nos formulários.

**🔴 Antes:**

```python
# models.py
phone_number = models.CharField('phone number', max_length=64, blank=True)
# Estado registrado em 0001_initial.py
('phone_number', models.CharField(max_length=64, null=True, verbose_name='phone number'))
```

**🟢 Depois:** nova migração `0002_normalize_phone_number.py` normaliza os dados
antes de executar `AlterField`:

```python
Client.objects.using(schema_editor.connection.alias).filter(
    phone_number__isnull=True
).update(phone_number='')
```

```python
migrations.AlterField(
    model_name='client',
    name='phone_number',
    field=models.CharField('phone number', max_length=64, blank=True),
)
```

**Justificativa:** preservar telefones preenchidos, converter valores ausentes e
sincronizar o esquema sem reescrever a migração inicial. Reverter a migração permite
novamente `NULL`, mas não reconstrói a distinção antiga entre `NULL` e string vazia.

### Validação de regressões

**Diagnóstico:** `account/tests.py` continha apenas o esqueleto padrão.

**🔴 Antes:**

```python
from django.test import TestCase

# Create your tests here.
```

**🟢 Depois:** testes de renderização de oito páginas, validação de cliente sem
telefone e migração de registros antigos (telefone nulo e preenchido).

**Justificativa:** verificar comportamento e preservação dos dados além da análise
estática. Os testes usam banco separado em memória.

**Resultados nesta sessão:** `manage.py check` sem problemas;
`manage.py makemigrations --check --dry-run` sem alterações pendentes;
`manage.py test account --verbosity 2` com três testes aprovados, incluindo oito
subcasos de páginas. Isso não equivale a validar JavaScript no navegador ou a uma
nova análise do SonarCloud.

Para reproduzir no PowerShell, a partir da raiz do repositório:

```powershell
cd Manutencao-mBank-main/dbank_project/dbank
../.venv/Scripts/python.exe manage.py check
../.venv/Scripts/python.exe manage.py makemigrations --check --dry-run
../.venv/Scripts/python.exe manage.py test account
../.venv/Scripts/python.exe manage.py migrate
```

---

**Projeto:** `Manutencao-mBank`  
**Objetivo:** Registrar o histórico de melhorias, refatorações e correções de segurança recomendadas pelo SonarCloud, documentando o estado anterior (**Antes**), a alteração realizada (**Depois**) e a justificativa técnica (**Por que foi corrigido**).

---

## Índice de Correções

- [Lote 1: Correções Rápidas (Limpeza, Tags HTML & ARIA)](#lote-1-correções-rápidas-limpeza-tags-html--aria)
  - [1.1. Remoção de Papel ARIA Redundante em Formulário (`Web:S6822`)](#11-remoção-de-papel-aria-redundante-em-formulário-webs6822)
  - [1.2. Inclusão de `<title>` na Página de Redirecionamento Swagger (`Web:PageWithoutTitleCheck`)](#12-inclusão-de-title-na-página-de-redirecionamento-swagger-webpagewithouttitlecheck)
  - [1.3. Ocultação de SVG Decorativo para Tecnologias Assistivas (`Web:ImgWithoutAltCheck`)](#13-ocultação-de-svg-decorativo-para-tecnologias-assistivas-webimgwithoutaltcheck)
  - [1.4. Remoção de Código Comentado Inativo (`python:S125`)](#14-remoção-de-código-comentado-inativo-pythons125)
- [Lote 2: Backend e Boas Práticas Python / Django](#lote-2-backend-e-boas-práticas-python--django)
  - [2.1. Substituição de `null=True` por `blank=True` em Campo de Texto (`python:S6553`)](#21-substituição-de-nulltrue-por-blanktrue-em-campo-de-texto-pythons6553)
  - [2.2. Eliminação de Literais Duplicados com Constantes (`python:S1192`)](#22-eliminação-de-literais-duplicados-com-constantes-pythons1192)
  - [2.3. Substituição de `role="navigation"` por Elemento Semântico `<nav>` (`Web:S6819`)](#23-substituição-de-rolenavigation-por-elemento-semântico-nav-webs6819)
  - [2.4. Adição de Subresource Integrity (SRI) em Script CDN (`Web:S5725`)](#24-adição-de-subresource-integrity-sri-em-script-cdn-webs5725)
- [Lote 3: Segurança e Variáveis de Ambiente](#lote-3-segurança-e-variáveis-de-ambiente) *(Planejado)*
- [Lote 4: Acessibilidade dos Templates Web](#lote-4-acessibilidade-dos-templates-web) *(Implementado e validado localmente; reanálise SonarCloud pendente)*

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

---

## Lote 2: Backend e Boas Práticas Python / Django

### 2.1. Substituição de `null=True` por `blank=True` em Campo de Texto (`python:S6553`)
* **Severidade:** MAJOR (Code Smell)
* **Arquivo:** [`Manutencao-mBank-main/dbank_project/dbank/account/models.py`](file:///c:/Users/Mateus/Downloads/Manutencao-mBank-main%20(1)/Manutencao-mBank-main/dbank_project/dbank/account/models.py)

#### 🔍 Diagnóstico e Justificativa Técnica
Na documentação e convenção oficial do Django, não se deve usar `null=True` em campos baseados em caracteres (`CharField`, `TextField`), pois isso gera dois estados "vazios" diferentes no banco de dados: `NULL` (nulo SQL) e `""` (string vazia). A boa prática estabelecida pelo framework e exigida pelo SonarCloud é utilizar apenas `blank=True`, garantindo que dados ausentes sejam sempre armazenados como strings vazias de maneira consistente.

#### 🔴 Antes
```python
class Client(AbstractUser):
    name = models.CharField('clients name', max_length=128, null=False)
    phone_number = models.CharField('phone number', max_length=64, null=True)
```

#### 🟢 Depois
```python
class Client(AbstractUser):
    name = models.CharField('clients name', max_length=128, null=False)
    phone_number = models.CharField('phone number', max_length=64, blank=True)
```

---

### 2.2. Eliminação de Literais Duplicados com Constantes (`python:S1192`)
* **Severidade:** CRITICAL (Code Smell)
* **Arquivo:** [`Manutencao-mBank-main/dbank_project/dbank/account/admin.py`](file:///c:/Users/Mateus/Downloads/Manutencao-mBank-main%20(1)/Manutencao-mBank-main/dbank_project/dbank/account/admin.py)

#### 🔍 Diagnóstico e Justificativa Técnica
A repetição de strings literais (`'admin:{}_{}_change'` repetida 3 vezes e `'<a href="{}">{}</a>'` repetida 5 vezes) fere o princípio DRY (*Don't Repeat Yourself*). Se for necessário alterar o padrão de formatação ou de URL em um refactoring futuro, ter literais espalhados aumenta o risco de esquecimento ou erro de digitação. A solução é declarar constantes descritivas no módulo.

#### 🔴 Antes
```python
    def get_owner_name(self, obj):
        ct = obj.owner._meta  # content type
        url = reverse('admin:{}_{}_change'.format(ct.app_label, ct.model_name), args=(obj.owner.pk,))
        return format_html('<a href="{}">{}</a>', url, obj.owner.name)

    def nr_of_transactions(self, obj):
        # ...
        return format_html('<a href="{}">{}</a>', url, transactions.count())

    def get_src(self, obj):
        # ...
        url = reverse('admin:{}_{}_change'.format(ct.app_label, ct.model_name), args=(obj.src.pk,))
        return format_html('<a href="{}">{}</a>', url, obj.src.iban)

    def get_dest(self, obj):
        # ...
        url = reverse('admin:{}_{}_change'.format(ct.app_label, ct.model_name), args=(obj.dest.pk,))
        return format_html('<a href="{}">{}</a>', url, obj.dest.iban)

    def list_accounts(self, obj):
        # ...
        return format_html('<a href="{}">{}</a>', url, accounts)
```

#### 🟢 Depois
```python
CHANGE_URL_PATTERN = 'admin:{}_{}_change'
HTML_LINK_TEMPLATE = '<a href="{}">{}</a>'

# Uso nos métodos:
url = reverse(CHANGE_URL_PATTERN.format(ct.app_label, ct.model_name), args=(...))
return format_html(HTML_LINK_TEMPLATE, url, ...)
```

---

### 2.3. Substituição de `role="navigation"` por Elemento Semântico `<nav>` (`Web:S6819`)
* **Severidade:** MAJOR (Code Smell)
* **Arquivo:** [`Manutencao-mBank-main/dbank_project/dbank/templates/base.html`](file:///c:/Users/Mateus/Downloads/Manutencao-mBank-main%20(1)/Manutencao-mBank-main/dbank_project/dbank/templates/base.html)

#### 🔍 Diagnóstico e Justificativa Técnica
A regra WAI-ARIA recomenda a utilização de elementos nativos do HTML5 sempre que possível em vez de aplicar atributos `role` em elementos genéricos como `<div>`. Substituir `<div role="navigation">` pela tag semântica nativa `<nav>` melhora o suporte nativo em todos os navegadores e ferramentas assistivas sem necessidade de papéis ARIA artificiais.

#### 🔴 Antes
```html
<div class="navbar navbar-default navbar-static-top" role="navigation">
    <div class="container">
        ...
    </div>
</div>
```

#### 🟢 Depois
```html
<nav class="navbar navbar-default navbar-static-top">
    <div class="container">
        ...
    </div>
</nav>
```

---

### 2.4. Adição de Subresource Integrity (SRI) em Script CDN (`Web:S5725`)
* **Severidade:** MINOR (Vulnerability)
* **Arquivo:** [`Manutencao-mBank-main/dbank_project/dbank/templates/base.html`](file:///c:/Users/Mateus/Downloads/Manutencao-mBank-main%20(1)/Manutencao-mBank-main/dbank_project/dbank/templates/base.html)

#### 🔍 Diagnóstico e Justificativa Técnica
A inclusão de recursos JavaScript de CDNs externas sem os atributos `integrity` e `crossorigin="anonymous"` expõe a aplicação a ataques de *supply chain* ou comprometimento de CDN. Se o arquivo hospedado na CDN for adulterado por invasores, o navegador executaria o script malicioso. O hash criptográfico (SRI) garante que o navegador só executa o script se ele for exatamente idêntico ao esperado.

#### 🔴 Antes
```html
<script src="https://ajax.googleapis.com/ajax/libs/jquery/1.12.4/jquery.min.js"></script>
```

#### 🟢 Depois
```html
<script src="https://ajax.googleapis.com/ajax/libs/jquery/1.12.4/jquery.min.js" integrity="sha384-nvAa0+6Qg9clwYCGGPpDQLVpLNn0fRaROjHqs13t4Ggj3Ez50XnGQqc/r8MhnRDZ" crossorigin="anonymous"></script>
```

