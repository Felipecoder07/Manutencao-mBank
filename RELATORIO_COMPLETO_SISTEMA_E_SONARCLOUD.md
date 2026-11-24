# Relatório Completo do Sistema e Manutenção com SonarCloud — `Manutencao-mBank` (`dbank`)

---

## 1. Contexto e Funcionamento Completo do Sistema

### 1.1. Visão Geral
O **Manutencao-mBank** (internamente chamado de **`dbank`**) é uma aplicação web bancária desenvolvida em **Python** com o framework **Django** e **Django REST Framework (DRF)**. O sistema simula operações bancárias essenciais — gerenciamento de clientes, abertura de contas com validação de IBAN, depósitos, saques e transferências — disponibilizando tanto uma **interface web** (templates HTML com Bootstrap 3) quanto uma **API REST** documentada com **Swagger UI**.

O projeto foi utilizado como base para um ciclo estruturado de **manutenção evolutiva e corretiva**, combinando análise estática automatizada via **SonarCloud** (integrado ao GitHub Actions) com revisões manuais de segurança, banco de dados, acessibilidade e testes automatizados.

### 1.2. Stack Tecnológica
* **Linguagem:** Python 3
* **Framework Web:** Django `5.2.17`
* **API REST:** Django REST Framework `3.18.0`
* **Interface / Frontend:** Templates Django + `django-bootstrap3` (`26.2`) + jQuery 1.12.4
* **Banco de Dados:** SQLite3 (`db.sqlite3`)
* **Ferramentas de Desenvolvimento:** `django-debug-toolbar` (`7.1.1`), `django-extensions` (`4.1`)
* **Documentação da API:** Swagger UI (`docs/swagger/swagger.yml`)
* **Qualidade e CI/CD:** GitHub Actions + SonarCloud

### 1.3. Estrutura de Pastas do Projeto
```text
Manutencao-mBank/
├── .github/workflows/
│   └── sonarcloud.yml               # Workflow ativo do GitHub Actions para o SonarCloud
├── .vscode/
│   └── settings.json                # Configuração local do interpretador Python e extraPaths
├── DOCUMENTACAO_CORRECOES_SONAR.md  # Diário técnico de todas as correções aplicadas
├── SONARCLOUD_ISSUES_REPORT.md      # Diagnóstico inicial das 37 issues do SonarCloud
├── RELATORIO_COMPLETO_SISTEMA_E_SONARCLOUD.md # Este relatório consolidado
└── Manutencao-mBank-main/
    ├── README.md                    # Guia rápido em português de execução
    └── dbank_project/
        ├── .github/workflows/sonarcloud.yml # Workflow legado (não executado pelo GitHub)
        ├── .gitignore
        ├── README.md                # Guia completo (variáveis de ambiente, SonarCloud, execução)
        ├── requirements.txt         # Dependências Python
        ├── sonar-project.properties # Configuração do projeto no SonarCloud
        ├── docs/swagger/            # Especificação OpenAPI/Swagger e interface estática
        └── dbank/                   # Raiz da aplicação Django
            ├── manage.py            # CLI de gerenciamento do Django
            ├── dbank/               # Configurações centrais (settings.py, urls.py, wsgi.py)
            ├── account/             # App principal (models, views, forms, serializers, admin, urls, tests, migrations)
            └── templates/           # Templates HTML (base.html, homepage.html, registration/, account/)
```

### 1.4. Arquitetura e Funcionamento Interno
1. **Modelos de Dados (`account/models.py`):**
   * **`Client` (herda de `AbstractUser`):** Representa o usuário/cliente autenticado do banco (`AUTH_USER_MODEL = 'account.Client'`). Possui `name` (obrigatório) e `phone_number` (opcional, com `blank=True`).
   * **`Account`:** Representa uma conta bancária vinculada a um `Client` (`owner`). Possui `iban` (único, validado por regex `^[A-Z]{2}\d+$` via `validate_iban`), `created`, `closed`, e `balance`. Implementa os métodos de negócio:
     * `deposit(amount)`: valida se a conta está aberta, soma ao saldo e registra uma `Transaction` com `dest=self`.
     * `withdraw(amount)`: valida se a conta está aberta, subtrai do saldo e registra uma `Transaction` com `src=self`.
     * `transfer(dest, amount)`: valida se origem e destino estão abertas, movimenta ambos os saldos e registra `Transaction(src=self, dest=dest, amount=amount)`.
   * **`Transaction`:** Registra o histórico imutável de operações (`timestamp`, `src`, `dest`, `amount`), classificando automaticamente o tipo via `get_type()` (`deposit`, `withdraw` ou `transaction`).

2. **Camada Web (`account/views.py`, `account/forms.py`, `templates/`):**
   * Autenticação obrigatória (`LoginRequiredMixin`) em todas as páginas bancárias (`/bank/clients/`, `/bank/accounts/`, `/bank/transactions/`).
   * `AccountCreate` associa automaticamente a nova conta ao usuário logado.
   * `TransactionCreate` utiliza `TransactionForm` e roteia a operação para `transfer`, `deposit` ou `withdraw` conforme os campos preenchidos, tratando erros de conta fechada ou ausência de contas selecionadas.

3. **Camada de API REST (`account/views.py`, `account/serializers.py`, `account/urls.py`):**
   * `AccountViewSet` (`/bank/api/accounts/`): permite listar e criar contas do usuário autenticado.
   * `TransactionViewSet` (`/bank/api/transactions/`): permite listar e detalhar transações em que o usuário é origem ou destino.
   * Autenticação configurada via `BasicAuthentication` e `SessionAuthentication` no `REST_FRAMEWORK`.

4. **Execução Local:**
   * Exige definição obrigatória da variável de ambiente `SECRET_KEY` (sem valor padrão embutido) e opcionalmente `DEBUG=true` para desenvolvimento:
     ```powershell
     $env:SECRET_KEY = "sua-chave-segura-aqui"
     $env:DEBUG = "true"
     cd Manutencao-mBank-main/dbank_project/dbank
     python manage.py migrate
     python manage.py runserver
     ```

---

## 2. Uso Específico do SonarCloud no Projeto

O **SonarCloud** foi integrado ao ciclo de vida do repositório em **dois pontos específicos**:

1. **Automação via GitHub Actions (`.github/workflows/sonarcloud.yml`):**
   * Disparado automaticamente em `push` na branch `main`, em eventos de `pull_request` (`opened`, `synchronize`, `reopened`) e manualmente via `workflow_dispatch`.
   * Utiliza `actions/checkout` (fixado por SHA `11d5960a326750d5838078e36cf38b85af677262`) com `fetch-depth: 0` (necessário para análise de histórico/blame) e `SonarSource/sonarcloud-github-action` (fixado por SHA `383f7e52eae3ab0510c3cb0e7d9d150bbaeab838`).
   * Define `projectBaseDir: Manutencao-mBank-main/dbank_project` e autentica via segredo `SONAR_TOKEN`.
   * *Observação arquitetural:* existe um arquivo legado em `Manutencao-mBank-main/dbank_project/.github/workflows/sonarcloud.yml`, porém o GitHub Actions executa exclusivamente o workflow localizado na raiz (`.github/workflows/sonarcloud.yml`). Ambos foram corrigidos para manter consistência e eliminar alertas do scanner.

2. **Configuração de Escopo (`Manutencao-mBank-main/dbank_project/sonar-project.properties`):**
   * `sonar.projectKey=Felipecoder07_Manutencao-mBank`
   * `sonar.organization=felipecoder07`
   * `sonar.sources=dbank` — direciona a inspeção estática para o código Python (Django) e templates HTML da aplicação.
   * `sonar.exclusions=**/migrations/**,**/__pycache__/**,**/tests.py` — exclui arquivos gerados automaticamente e testes do escopo padrão (nota: durante as análises, a pasta `docs/swagger` e os workflows `.github/workflows` também foram inspecionados pelo SonarCloud).

---

## 3. O que foi Refatorado / Alterado SEM a Utilização do SonarCloud?

Além das correções apontadas diretamente pelas regras do SonarCloud, foram realizadas melhorias estruturais e corretivas de forma **manual/proativa**, motivadas por boas práticas de engenharia de software e prevenção de regressões:

1. **Criação da Migração Complementar de Banco de Dados (`account/migrations/0002_normalize_phone_number.py`):**
   * *Por que foi feita sem o SonarCloud:* O SonarCloud apontou apenas a troca de `null=True` para `blank=True` em `models.py` (`python:S6553`), mas não detectou que o esquema do banco permanecia desatualizado na migração `0001_initial.py` e que registros antigos poderiam conter `NULL`.
   * *O que foi feito:* Criada uma migração de dados + esquema que converte valores `phone_number=NULL` existentes para `""` (string vazia) antes de aplicar o `AlterField`, preservando telefones já preenchidos.
2. **Criação da Suíte de Testes Automatizados (`account/tests.py`):**
   * *Antes:* O arquivo continha apenas o esqueleto padrão vazio do Django (`# Create your tests here.`).
   * *Depois:* Implementados testes automatizados cobrindo: renderização de 8 páginas da aplicação, validação de cliente sem telefone (`blank=True`) e teste de migração de registros antigos (`PhoneNumberMigrationTests`).
3. **Configuração do Ambiente de Desenvolvimento (`.vscode/settings.json`):**
   * Adicionados `python.defaultInterpreterPath` e `python.analysis.extraPaths` apontando para o `.venv` e para a raiz dos módulos `dbank`/`account`, resolvendo falhas de resolução de imports no editor.
4. **Documentação Operacional e de Manutenção:**
   * Atualização completa de `Manutencao-mBank-main/dbank_project/README.md` com instruções de `SECRET_KEY`, `DEBUG`, rotação de segredos e execução no Windows/Linux.
   * Criação dos registros `SONARCLOUD_ISSUES_REPORT.md` e `DOCUMENTACAO_CORRECOES_SONAR.md`.
5. **Limpeza Preventiva em `settings.py`:**
   * Remoção da entrada comentada `'account'` em `INSTALLED_APPS` durante o Lote 3, mesmo sem confirmação de issue aberta específica para aquela linha.

---

## 4. Primeira Inspeção do SonarCloud: Quantas Issues Foram Detectadas?

Na primeira inspeção oficial registrada em `SONARCLOUD_ISSUES_REPORT.md`, o SonarCloud detectou **37 issues** no total, com um **débito técnico estimado de ~4h 47min (287 minutos)**:

| Severidade | Tipo(s) | Quantidade | Principais Impactos |
| :--- | :--- | :---: | :--- |
| **BLOCKER** | Vulnerability | **1** | `SECRET_KEY` do Django exposta em texto plano no código-fonte (`settings.py`). |
| **CRITICAL** | Code Smell | **2** | Duplicação de strings literais em métodos do painel admin (`admin.py`). |
| **MAJOR** | Vulnerability / Code Smell / Bug | **18** | Actions fixadas por tag mutável, `null=True` em `CharField`, código comentado, papéis ARIA redundantes/inadequados, página HTML sem `<title>`. |
| **MINOR** | Bug / Vulnerability / Code Smell | **16** | `DEBUG=True` fixo, ausência de SRI em script CDN, eventos de mouse sem teclado em links com `role="button"`, tags `<li>` fora de `<ul>`/`<ol>`, SVG sem atributo acessível. |
| **TOTAL** | — | **37** | **~287 minutos (~4h 47min) de débito técnico inicial** |

---

## 5. Quantas e Quais Issues Foram Refatoradas? (Histórico Completo do Início ao Fim)

Todas as **37 issues originais** detectadas na primeira inspeção foram refatoradas, além de **1 nova issue** aberta durante o processo (totalizando **38 issues corrigidas** ao longo de **8 commits**).

### Linha do Tempo Completa dos Commits
1. **`062013b` (05/11/2026) — `Initial commit`:** Importação do projeto base `dbank` (45 arquivos).
2. **`c6b664a` (05/11/2026) — `Configure SonarCloud project properties and GitHub Actions workflow`:** Configuração inicial do `.github/workflows/sonarcloud.yml` na raiz e ajuste do `sonar-project.properties`.
3. **`a72d87e` (09/11/2026) — `fix(sonar): lote 1`:**
   * `Web:S6822` (1 MAJOR): Remoção de `role="form"` redundante em `account_form.html`.
   * `Web:PageWithoutTitleCheck` (1 MAJOR): Adição de `<head>`, `<meta charset>` e `<title>` em `docs/swagger/oauth2-redirect.html`.
   * `Web:ImgWithoutAltCheck` (1 MINOR): Adição de `aria-hidden="true"` no `<svg>` decorativo em `docs/swagger/index.html`.
   * `python:S125` (5 MAJOR): Remoção de blocos de código comentado em `admin.py`, `models.py`, `urls.py` e `views.py` (2 blocos).
4. **`73e8cfd` (09/11/2026) — `fix(sonar): lote 2`:**
   * `python:S6553` (1 MAJOR): Substituição de `null=True` por `blank=True` em `Client.phone_number` (`models.py`).
   * `python:S1192` (2 CRITICAL): Extração das constantes `CHANGE_URL_PATTERN` e `HTML_LINK_TEMPLATE` em `admin.py`.
   * `Web:S6819` (1 MAJOR): Substituição de `<div role="navigation">` por `<nav>` em `base.html`.
   * `Web:S5725` (1 MINOR): Adição de `integrity="sha384-..."` e `crossorigin="anonymous"` (SRI) no script jQuery em `base.html`.
5. **`b75b866` (09/11/2026) — `fix(sonar): correcoes manuais nos templates e testes` (Lote 4 + Revisão de Regressões):**
   * `Web:ItemTagNotWithinContainerTagCheck` (5 MINOR): Estruturação explícita de `<nav aria-label="Breadcrumb"><ol class="breadcrumb">...</ol></nav>` via bloco `breadcrumbs_container` em `account_list.html`, `client_detail.html` (2 ocorrências), `client_list.html` e `transaction_list.html`.
   * `Web:S6819` + `Web:MouseEventWithoutKeyboardEquivalentCheck` (7 MAJOR + 7 MINOR): Remoção de `role="button"` em 7 links `<a>` (`homepage.html` [4], `account_list.html` [2], `transaction_list.html` [1]), preservando a semântica nativa de navegação por teclado.
   * `Web:S6819` (1 MAJOR): Substituição de `<div class="btn-group" role="group" aria-label="...">` por `<nav class="btn-group" aria-label="Account actions">` em `account_list.html`.
   * *Sem Sonar:* Criação de `0002_normalize_phone_number.py`, testes em `account/tests.py` e `.vscode/settings.json`.
6. **`eb595fc` (12/11/2026) — `fix(sonar): lote 3`:**
   * `secrets:S6687` (1 BLOCKER): Remoção da `SECRET_KEY` hardcoded em `settings.py`; leitura obrigatória via `os.environ.get('SECRET_KEY')` com `ImproperlyConfigured`.
   * `python:S4507` (1 MINOR): `DEBUG` controlado via variável de ambiente com padrão `False`.
   * `githubactions:S7637` (2 MAJOR): Fixação das actions (`actions/checkout` e `SonarSource/sonarcloud-github-action`) por hash SHA completo nos dois workflows.
7. **`b4b7f20` (12/11/2026) — `ci: trigger sonarcloud analysis`:** Disparo de nova análise no SonarCloud após o Lote 3.
8. **`0a38e12` (12/11/2026) — `docs: atualizar documentacao de correcoes e refatorar variavel na migracao`:**
   * `python:S117` (1 MINOR — *nova issue*): Renomeação da variável local `Client` para `client_model` em `0002_normalize_phone_number.py`.

---

## 6. Organização da Equipe para Resolução das Issues

Com base no histórico do repositório Git e na documentação de controle (`DOCUMENTACAO_CORRECOES_SONAR.md` e `SONARCLOUD_ISSUES_REPORT.md`), a resolução das issues foi organizada por meio de uma **estratégia incremental em lotes temáticos priorizados**, com consolidação dos commits no repositório sob a autoria principal de **Luiz Felipe Verissimo**:

1. **Fase 0 — Diagnóstico e Roteiro:** Execução da análise inicial, geração do relatório `SONARCLOUD_ISSUES_REPORT.md` e classificação das 37 issues em 3 níveis de prioridade (Segurança, Qualidade de Backend e Semântica/Acessibilidade Web).
2. **Lote 1 (Quick Wins / Limpeza):** Remoção de código morto/comentado e ajustes pontuais de HTML/Swagger com baixo risco de regressão.
3. **Lote 2 (Backend & Boas Práticas):** Refatorações em Python/Django (`models.py`, `admin.py`) e segurança de CDN (`base.html`).
4. **Checkpoint de Regressão e Testes:** Pausa estratégica após o Lote 2 para auditar impactos no banco de dados (criação da migração `0002`) e criar a suíte de testes automatizados (`account/tests.py`).
5. **Lote 4 (Acessibilidade dos Templates):** Padronização semântica de breadcrumbs, navegação e links nos templates HTML, validada via `HTMLParser` e testes de renderização.
6. **Lote 3 (Segurança Crítica e CI/CD):** Remoção de segredos expostos (`SECRET_KEY`), desativação de `DEBUG` por padrão e fixação de SHAs no GitHub Actions, acompanhados de atualização do `README.md`.
7. **Verificação Pós-CI e Fechamento:** Disparo do SonarCloud e correção imediata da única issue residual aberta na migração nova (`python:S117`).

---

## 7. Após a Refatoração, Houve Abertura de Novas Issues?

**Sim, houve a abertura de 1 (uma) nova issue.**

* **ID / Regra / Severidade:** `AaHCkc96_3gdn818-21f` — `python:S117` — **MINOR** (Manutenibilidade / Convenção de Nomenclatura).
* **Origem:** Ao criar manualmente a migração complementar `account/migrations/0002_normalize_phone_number.py` para corrigir a regressão do campo `phone_number`, a variável local que recebia o modelo histórico foi nomeada em PascalCase (`Client = apps.get_model('account', 'Client')`), violando a convenção `snake_case` exigida pelo SonarCloud para variáveis locais em Python.
* **Resolução:** Corrigida imediatamente no commit `0a38e12`, renomeando a variável para `client_model` e revalidando com `manage.py test account.tests.PhoneNumberMigrationTests`.

---

## 8. Medição Final: Antes vs. Depois das Refatorações

| Métrica / Indicador | Inspeção Inicial (Antes) | Estado Final (Depois das Refatorações) |
| :--- | :---: | :---: |
| **Issues BLOCKER** | 1 | **0** (corrigida localmente) |
| **Issues CRITICAL** | 2 | **0** (corrigidas localmente) |
| **Issues MAJOR** | 18 | **0** (corrigidas localmente) |
| **Issues MINOR** | 16 | **0** (16 originais + 1 nova issue `python:S117` corrigidas) |
| **Total de Issues Abertas** | **37** | **0 pendências locais conhecidas** *(38/38 tratadas)* |
| **Débito Técnico Estimado** | ~4h 47min (287 min) | **0 min** *(pendente apenas confirmação final no painel após último push)* |
| **Cobertura de Testes Automatizados** | 0 testes (arquivo vazio) | **3 suítes / 8 subcasos de páginas + migração** (100% aprovados) |
| **Django System Check / Migrations** | Migração desatualizada após edição | `manage.py check` e `makemigrations --check --dry-run` sem erros |

> **Nota de transparência:** Conforme registrado em `DOCUMENTACAO_CORRECOES_SONAR.md`, todas as correções foram implementadas e validadas localmente (`manage.py check`, `manage.py test account`, `HTMLParser`), mas o encerramento formal do contador no dashboard do SonarCloud depende da execução automática da pipeline do GitHub Actions após o envio do último commit (`0a38e12`).

---

## 9. Categorização das Técnicas de Refatoração Utilizadas

A tabela abaixo categoriza cada correção aplicada, indicando a **técnica de refatoração**, **como foi aplicada** na prática e **se foi utilizada a solução sugerida pelo SonarCloud**:

| Regra SonarCloud | Arquivo(s) | Técnica de Refatoração | Como Foi Aplicada | Usou Solução do SonarCloud? |
| :--- | :--- | :--- | :--- | :--- |
| `secrets:S6687` | `dbank/settings.py` | **Externalizar Configuração (Parametrização de Ambiente)** | Removida a string literal da `SECRET_KEY`; substituída por `os.environ.get('SECRET_KEY', '').strip()` com lançamento de `ImproperlyConfigured` se vazia. | **Sim** (com validação explícita de falha rápida). |
| `python:S4507` | `dbank/settings.py` | **Externalizar Configuração (Fail-Safe Default)** | Substituído `DEBUG = True` por `os.environ.get('DEBUG', 'false').lower() == 'true'`. | **Sim.** |
| `githubactions:S7637` | `.github/workflows/sonarcloud.yml` (raiz e subpasta) | **Fixação de Dependência por Hash Imutável (*Dependency Pinning*)** | Substituídas tags mutáveis (`@v4`, `@v3`) pelos hashes SHA completos de 40 caracteres dos commits oficiais das Actions. | **Sim.** |
| `python:S1192` | `account/admin.py` | **Substituir Literal Duplicado por Constante Simbólica** (*Replace Magic Literal with Symbolic Constant*) | Extraídas as constantes de módulo `CHANGE_URL_PATTERN = 'admin:{}_{}_change'` e `HTML_LINK_TEMPLATE = '<a href="{}">{}</a>'`, reutilizadas em 5 métodos. | **Sim.** |
| `python:S125` | `admin.py`, `models.py`, `urls.py`, `views.py` | **Remover Código Morto** (*Remove Dead Code*) | Excluídos todos os blocos de código Python comentados, confiando no histórico do Git para recuperação se necessário. | **Sim.** |
| `python:S6553` | `account/models.py` + `0002_normalize_phone_number.py` | **Padronização de Restrição de Domínio + Migração de Dados** | Trocado `null=True` por `blank=True` em `CharField` e criada migração manual para normalizar `NULL` → `""` no banco sem perda de dados. | **Parcialmente / Expandida** (Sonar sugeriu apenas `blank=True`; a migração de dados foi adicionada manualmente). |
| `python:S117` | `account/migrations/0002_normalize_phone_number.py` | **Renomear Variável** (*Rename Variable*) | Renomeada a variável local `Client` para `client_model` para aderir ao padrão `snake_case`. | **Sim.** |
| `Web:S5725` | `templates/base.html` | **Adição de Integridade de Subrecurso (SRI)** | Adicionados os atributos `integrity="sha384-..."` e `crossorigin="anonymous"` na tag `<script>` do jQuery via CDN. | **Sim.** |
| `Web:S6822` | `templates/account/account_form.html` | **Remover Atributo Redundante** | Removido `role="form"` da tag `<form>`, pois o elemento HTML5 já possui esse papel nativamente. | **Sim.** |
| `Web:PageWithoutTitleCheck` | `docs/swagger/oauth2-redirect.html` | **Completar Estrutura Semântica de Documento** | Inserido `<head>` com `<meta charset="utf-8">` e `<title>Swagger UI: OAuth2 Redirect</title>`. | **Sim.** |
| `Web:ImgWithoutAltCheck` | `docs/swagger/index.html` | **Ocultação de Elemento Decorativo (Acessibilidade)** | Adicionado `aria-hidden="true"` no `<svg>` invisível que contém apenas `<defs>` e `<symbol>`. | **Sim.** |
| `Web:S6819` (`navigation` e `group`) | `templates/base.html`, `templates/account/account_list.html` | **Substituir Elemento Genérico por Elemento Semântico Nativo** | Trocados `<div role="navigation">` e `<div role="group" aria-label="...">` pela tag nativa `<nav>` (com `aria-label="Account actions"` nas ações). | **Sim.** |
| `Web:S6819` + `Web:MouseEventWithoutKeyboardEquivalentCheck` | `homepage.html`, `account_list.html`, `transaction_list.html` | **Restauração de Semântica Nativa de Links** | Removido `role="button"` de 7 links `<a href="...">`, mantendo as classes visuais Bootstrap (`btn`), pois links nativos já suportam foco por `Tab` e ativação por `Enter`. | **Adaptada** (Sonar sugeriu trocar por `<button>` ou adicionar handlers de teclado; optou-se por manter `<a>` semântico por serem links de navegação real). |
| `Web:ItemTagNotWithinContainerTagCheck` | `account_list.html`, `client_detail.html`, `client_list.html`, `transaction_list.html` | **Refatoração de Herança de Template (Substituição de Bloco Contêiner)** | Em vez de envolver `<li>` com outro `<ol>` dentro do bloco antigo (o que geraria listas aninhadas), substituiu-se o bloco `breadcrumbs_container` inteiro com `<nav aria-label="Breadcrumb"><ol class="breadcrumb">...</ol></nav>` e `aria-current="page"`. | **Adaptada** (Sonar sugeriu envolver `<li>` em `<ul>`/`<ol>`; a solução foi adaptada para a herança de templates Django sem duplicar o `<ol>` de `base.html`). |

