# Relatório de Diagnóstico e Correções do SonarCloud

**Projeto:** `Manutencao-mBank`  
**Organização:** `felipecoder07`  
**Total de Issues Detectadas:** 37  
**Débito Técnico Total Estimado:** ~4h 47min (287 minutos)

---

## 1. Visão Geral das Ocorrências

| Severidade | Tipo | Quantidade | Principais Impactos |
|---|---|---|---|
| **BLOCKER** | VULNERABILITY | 1 | Chave secreta do Django exposta diretamente no código-fonte |
| **CRITICAL** | CODE_SMELL | 2 | Duplicação de strings literais em métodos utilitários |
| **MAJOR** | VULNERABILITY / CODE_SMELL / BUG | 18 | Segurança do GitHub Actions, acessibilidade HTML (ARIA) e código comentado |
| **MINOR** | BUG / VULNERABILITY / CODE_SMELL | 16 | Falta de acessibilidade por teclado em links simulando botões, `DEBUG=True` em produção, tags HTML órfãs |

---

## 2. Detalhamento por Categoria e Arquivo

### 2.1. Segurança & Vulnerabilidades Críticas

#### 🔴 1. Chave Secreta Exposta (BLOCKER - `secrets:S6687`)
* **Arquivo:** `Manutencao-mBank-main/dbank_project/dbank/dbank/settings.py:23`
* **Diagnóstico:** A `SECRET_KEY` do Django está exposta em texto plano diretamente no repositório.
* **Ação Corretiva:**
  * Revogar o segredo atual.
  * Utilizar variáveis de ambiente via `os.environ.get('SECRET_KEY')` ou biblioteca como `python-decouple` / `django-environ`.
  * Fornecer um valor padrão seguro apenas em ambiente de desenvolvimento local não compartilhado.

#### 🟡 2. Modo Debug Ativado (MINOR - `python:S4507`)
* **Arquivo:** `Manutencao-mBank-main/dbank_project/dbank/dbank/settings.py:26`
* **Diagnóstico:** `DEBUG = True` expõe stack traces detalhados e variáveis internas se o aplicativo for implantado assim.
* **Ação Corretiva:**
  * Alterar para `DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'`.

#### 🟡 3. Fixação de Versão no GitHub Actions por Tag (MAJOR - `githubactions:S7637`)
* **Arquivos:**
  * `.github/workflows/sonarcloud.yml:18`
  * `Manutencao-mBank-main/dbank_project/.github/workflows/sonarcloud.yml:18`
* **Diagnóstico:** O uso de tags mutáveis (ex: `@v3` ou `@v4`) em actions de terceiros é vulnerável a sequestro de tag. O Sonar recomenda usar o SHA completo do commit correspondente da action.
* **Ação Corretiva:** Fixar pelo full commit hash SHA (ex: `uses: SonarSource/sonarcloud-github-action@<commit_sha>`).

#### 🟡 4. Falta de Verificação de Integridade em CDN (MINOR - `Web:S5725`)
* **Arquivo:** `Manutencao-mBank-main/dbank_project/dbank/templates/base.html:132`
* **Diagnóstico:** Scripts ou estilos externos importados via CDN sem `integrity` e `crossorigin="anonymous"` (Subresource Integrity - SRI).
* **Ação Corretiva:** Adicionar os atributos `integrity="sha384-..."` e `crossorigin="anonymous"`.

---

### 2.2. Modelos e Backend Python

#### 🟡 5. Uso Indevido de `null=True` em Campo de Texto (MAJOR - `python:S6553`)
* **Arquivo:** `Manutencao-mBank-main/dbank_project/dbank/account/models.py:11`
* **Diagnóstico:** Em campos baseados em texto do Django (`CharField`, `TextField`), a convenção oficial é usar apenas `blank=True` em vez de `null=True` para evitar dois estados nulos diferentes (`NULL` e string vazia `""`).
* **Ação Corretiva:** Substituir `null=True` por `blank=True`.

#### 🔴 6. Literais Duplicados (CRITICAL - `python:S1192`)
* **Arquivo:** `Manutencao-mBank-main/dbank_project/dbank/account/admin.py:19-20`
* **Diagnóstico:** As strings `'admin:{}_{}_change'` (repetida 3x) e `'<a href="{}">{}</a>'` (repetida 5x) estão duplicadas.
* **Ação Corretiva:** Declarar constantes no topo do arquivo (ex: `ADMIN_CHANGE_URL_PATTERN = 'admin:{}_{}_change'` e `LINK_TEMPLATE = '<a href="{}">{}</a>'`).

#### 🟡 7. Código Comentado Inativo (MAJOR - `python:S125`)
* **Ocorrências:**
  * `Manutencao-mBank-main/dbank_project/dbank/account/admin.py:14`
  * `Manutencao-mBank-main/dbank_project/dbank/account/models.py:79`
  * `Manutencao-mBank-main/dbank_project/dbank/account/urls.py:21`
  * `Manutencao-mBank-main/dbank_project/dbank/account/views.py:98, 105`
* **Diagnóstico:** Blocos de código Python comentados que poluem o código e degradam a manutenibilidade.
* **Ação Corretiva:** Excluir os trechos comentados (o histórico do Git preserva versões antigas).

---

### 2.3. Templates HTML e Acessibilidade (Frontend)

#### 🟡 8. Papéis ARIA Redundantes e Inadequados (MAJOR - `Web:S6819`, `Web:S6822`)
* **Ocorrências:**
  * `account_form.html:8` (`role="form"` em elemento `<form>` é redundante).
  * `base.html:38` (`role="navigation"` em vez da tag semântica `<nav>`).
  * `account_list.html:44` (`role="group"` em vez de `<fieldset>`, `<details>`, etc.).
  * `account_list.html:45, 46`, `transaction_list.html:44`, `homepage.html:10, 20, 25, 30` (Uso de `role="button"` em tags `<a>`).
* **Ação Corretiva:**
  * Remover atributos de role nativos redundantes.
  * Onde for ação de botão, utilizar `<button type="button">` em vez de `<a role="button">`. Se for navegação real entre páginas, manter `<a>` sem `role="button"`.

#### 🟡 9. Eventos de Mouse sem Equivalente de Teclado (MINOR - `Web:MouseEventWithoutKeyboardEquivalentCheck`)
* **Ocorrências:**
  * `account_list.html:45, 46`
  * `transaction_list.html:44`
  * `homepage.html:10, 20, 25, 30`
* **Diagnóstico:** Elementos com listeners ou comportamento de clique sem suporte aos eventos de teclado (`onkeydown` / `onkeyup`), impedindo a navegação acessível por usuários que usam teclado/leitores de tela.
* **Ação Corretiva:** Transformar esses elementos em botões nativos (`<button>`) que já possuem suporte nativo à tecla Enter e Espaço, ou adicionar o atributo correspondente de teclado.

#### 🟡 10. Tags `<li>` Fora de Contêineres de Lista (MINOR - `Web:ItemTagNotWithinContainerTagCheck`)
* **Ocorrências:**
  * `account_list.html:6`
  * `client_detail.html:6, 7`
  * `client_list.html:6`
  * `transaction_list.html:6`
* **Diagnóstico:** Tags `<li>` declaradas soltas, sem estarem envelopadas por `<ul>`, `<ol>` ou `<menu>`.
* **Ação Corretiva:** Envolver a lista em uma tag `<ul>` ou `<ol>`.

---

### 2.4. Documentação Swagger

* **`Web:ImgWithoutAltCheck`:** `docs/swagger/index.html:34` — Tag `<svg>` sem título ou descrição acessível. Adicionar `aria-hidden="true"` caso decorativo ou `<title>` interno.
* **`Web:PageWithoutTitleCheck`:** `docs/swagger/oauth2-redirect.html:2` — Página HTML sem a tag `<title>`. Adicionar `<title>Swagger UI Redirect</title>`.

---

## 3. Roteiro Recomendado de Resolução

1. **Prioridade I (Segurança Imediata):** Mover a `SECRET_KEY` e o `DEBUG` em `settings.py` para variáveis de ambiente.
2. **Prioridade II (Qualidade do Backend):**
   * Corrigir `null=True` em `models.py`.
   * Extrair constantes em `admin.py`.
   * Deletar comentários obsoletos em `admin.py`, `models.py`, `urls.py` e `views.py`.
3. **Prioridade III (Semântica e Acessibilidade Web):**
   * Corrigir as tags `<li>` soltas nos templates Django.
   * Substituir links estilizados como botões (`<a role="button">`) por tags `<button>` ou links semânticos.
   * Ajustar SRI (`integrity`) nos scripts externos em `base.html`.

