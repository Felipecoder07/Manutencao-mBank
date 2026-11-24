# Requisitos do mBank — Cofrinho, simulação de empréstimo e confirmação de compra

**Finalidade.** Especificação **exclusiva de backend** para desenvolvimento e testes. As funcionalidades expõem contratos REST prontos para o futuro frontend consumir (o frontend será implementado em uma etapa posterior). O servidor identifica o titular pela sessão ou credencial autenticada.

> **Escopo obrigatório — SOMENTE BACKEND:** Não criar nem alterar templates HTML (`templates/`), CSS, JavaScript, formulários web de apresentação ou telas. Implementar apenas **modelos, migrações, regras de negócio/serviços, serializers, endpoints REST (Django REST Framework), validações, idempotência, permissões, Django Admin, comandos de gerenciamento, testes automatizados e especificação OpenAPI (`docs/swagger/swagger.yml`)**.

## 1. Ponto de partida

O código analisado está em `Manutencao-mBank-main/dbank_project/dbank/`. Os caminhos de código abaixo são relativos a essa pasta.

| Onde | Comportamento atual | Alteração necessária (Somente Backend) |
|---|---|---|
| `account/models.py` | `Account` tem titular, IBAN, saldo e data de encerramento. Depósito, saque e transferência salvam saldo e lançamento em etapas. Os métodos de débito não verificam suficiência de fundos. | Centralizar as regras monetárias em camada de serviços para que compras, saques e transferências respeitem a mesma reserva, inclusive sob concorrência. |
| `account/models.py`, `account/serializers.py` | Saldo e valor de transação usam ponto flutuante. O tipo do lançamento é inferido pela presença de origem e destino. | Migrar dinheiro para representação decimal (`DecimalField`) e registrar a natureza da operação explicitamente, preservando a leitura do histórico. |
| `account/views.py` | A lista de contas filtra por titular. O extrato filtrado por ID de conta e a recuperação de transação por ID na API consultam registros sem o mesmo filtro. | Corrigir essas duas consultas antes de expor reservas, compras ou comprovantes. Limitar o detalhe da transação aos participantes e o extrato ao titular da conta consultada. |
| `account/views.py`, `account/serializers.py` | A API atual expõe apenas listagem/criação básica de contas e listagem/detalhe de transações, sem fluxo dedicado de compra, cofrinho ou empréstimo. | Criar endpoints REST, serializers e serviços dedicados para Cofrinho, Empréstimo (configuração, simulação e contratação), Compra com confirmação de senha e operações base da conta. |
| `account/urls.py`, `../docs/swagger/swagger.yml` | As rotas do aplicativo têm prefixo `/bank/` e a API usa `/bank/api/`. | Mapear todos os novos endpoints sob `/bank/api/` e documentá-los integralmente no `swagger.yml`, sem alterar templates HTML. |

**Premissas atualizadas com base nas telas do frontend.** Cofrinhos são reservas internas vinculadas à conta com **rendimento automático configurável (padrão 100% do CDI, cálculo diário/mensal e informação de isenção de IOF após 30 dias)**, suporte a categorias, ícones, metas com percentual e histórico dedicado. O módulo de Empréstimo contempla **limite pré-aprovado**, **simulação completa com detalhamento de parcelas** e **contratação efetiva** com crédito em conta e controle de parcelas. A compra é paga à vista com saldo disponível da conta para um recebedor cadastrado no mBank, exigindo confirmação de senha. O repositório não apresenta checkout, adquirente ou integração de cartão; caso “compra” venha a significar pagamento por cartão ou loja externa, autorização, liquidação e estornos exigirão especificação própria.

## 2. Cofrinho por conta

**Entrada e apresentação.** Em cada linha de Minhas contas, exibir saldo total, reservado, disponível e a ação **Cofrinhos**. A página da conta lista os cofrinhos, o valor de cada um e as ações Criar, Guardar, Resgatar e Ver histórico. No primeiro acesso, informar o que acontece com o saldo ao guardar dinheiro.

| ID | Requisito e regra de negócio |
|---|---|
| CF-01 | Permitir vários cofrinhos por conta aberta. Exigir nome com limite proposto de 60 caracteres. Meta é opcional, deve ser positiva e usa a moeda da conta. Criar com saldo zero. Permitir editar nome e meta sem alterar o dinheiro guardado. |
| CF-02 | Calcular disponível = saldo total da conta menos a soma das reservas. Guardar transfere disponibilidade para o cofrinho. Resgatar a devolve à mesma conta. Ambas as ações preservam o saldo total. Uma meta atingida sinaliza progresso e permite novos aportes. |
| CF-03 | Aceitar aportes apenas até o disponível e resgates parciais ou integrais até a reserva daquele cofrinho. Validar valor positivo, escala da moeda, titularidade, vínculo com a conta e estado aberto dentro da operação. |
| CF-04 | Compras, saques e transferências consultam exclusivamente o disponível para débito. Nenhum deles resgata automaticamente. Créditos recebidos aumentam o disponível. |
| CF-05 | Registrar cada aporte ou resgate com identificador, valor, data, conta e cofrinho. Exibir a movimentação identificada no histórico sem somá-la outra vez aos créditos ou débitos externos. |
| CF-06 | Permitir arquivar somente cofrinho zerado, preservando seu histórico. Recusar encerramento da conta com reserva e orientar o resgate. Conta encerrada permite consulta histórica pelo titular. |

**Modelo sugerido.** Cofrinho vinculado à conta, com nome, meta, reserva atual e data de arquivamento. Movimento de reserva vinculado ao cofrinho, com sentido, valor e referência única da operação. Reserva e movimento são gravados na mesma transação. Conciliar a reserva atual com a soma dos movimentos. Evitar exclusão em cascata de registros financeiros.

## 3. Simular empréstimo

**Entrada e apresentação.** A ação **Simular empréstimo** abre um formulário com conta, moeda, valor desejado e quantidade de parcelas. O resultado aparece na mesma jornada, com opção de alterar os dados e recalcular. Usar o texto “Estimativa de pagamento” e informar a data de referência e as hipóteses usadas.

| ID | Requisito e regra de negócio |
|---|---|
| SE-01 | Oferecer a simulação ao titular de conta aberta. Validar principal positivo, precisão monetária e prazo inteiro dentro das faixas de uma política de crédito ativa. Exibir os limites antes do envio. |
| SE-02 | Obter no servidor a versão vigente da política, taxa, periodicidade, limites e encargos. Em falta de configuração válida, informar indisponibilidade. Campos enviados pelo navegador não podem substituir a taxa. |
| SE-03 | Para o cenário inicial proposto, usar parcelas mensais pela Tabela Price. Com principal P, taxa efetiva mensal i em fração e n parcelas, prestação teórica = P × i / (1 − (1 + i) elevado a −n). Para taxa zero, dividir P por n. Definir primeira parcela após um período mensal completo. |
| SE-04 | Mostrar principal, prazo, taxa mensal e anual efetiva equivalente, valor das parcelas, total de juros, encargos discriminados e total a pagar. Anual equivalente = (1 + i) elevado a 12 menos 1. Identificar moeda, periodicidade e eventual diferença na última parcela. |
| SE-05 | Gerar demonstrativo por parcela com saldo inicial, juros, amortização, prestação e saldo final. Calcular com precisão decimal, aplicar arredondamento monetário uniforme e ajustar a última parcela para zerar o saldo. A soma das amortizações deve reproduzir o principal. |
| SE-06 | Recalcular ao mudar os dados e identificar a versão da política no resultado. A **simulação** em si não movimenta a conta, não consome limite e não cria dívida; a movimentação financeira e o consumo do limite pré-aprovado ocorrem exclusivamente na ação explícita de **Contratação de Empréstimo** (detalhada na Seção 8.3). |

**Condição para publicar condições reais.** Produto deve definir moeda, faixas, política de arredondamento, datas, tarifas e tributos aplicáveis, inclusive se serão financiados ou pagos à parte. O exemplo de cálculo acima assume encargos adicionais zero. Validar com a área responsável as informações de custo e divulgações exigidas para o mercado e produto escolhidos antes de apresentar a simulação a clientes reais.

## 4. Senha antes de finalizar compra

**Jornada.** Na conta aberta, **Pagar compra** abre ou recupera um pedido pendente. A revisão apresenta estabelecimento, referência do pedido, conta mascarada, moeda, valor final e validade. O cliente pode voltar, cancelar ou digitar a senha e acionar **Confirmar pagamento**. A tela de sucesso mostra o comprovante somente após a confirmação da gravação.

| ID | Requisito e regra de negócio |
|---|---|
| CP-01 | Registrar intenção pendente com identificador único, conta pagadora, recebedor autorizado, referência comercial, valor final positivo, moeda, criação e vencimento. Obter o total de uma fonte de pedidos confiável. Identificar como dependência a definição de quem pode emitir pedidos. |
| CP-02 | Premissa inicial de credencial: solicitar novamente a senha do titular autenticado e verificá-la no backend pelo mecanismo do Django. Se o produto exigir senha transacional distinta, definir cadastro, recuperação e bloqueio antes da implementação. |
| CP-03 | Vincular a confirmação àquela intenção e aos dados revisados. Alterações de valor ou recebedor invalidam a revisão anterior. A confirmação recebe apenas referência, senha e identificador de repetição. Recarregar os dados do servidor. |
| CP-04 | Dentro da transação, revalidar titular, estado pendente, validade, contas abertas e saldo disponível. Debitar o pagador, creditar o recebedor, registrar lançamento de compra e marcar como paga em uma única confirmação atômica. Reverter a operação inteira em caso de falha. |
| CP-05 | Senha incorreta mantém a compra pendente sem movimentar dinheiro. Aplicar contagem persistente de falhas e limitação por titular e por origem, inclusive entre pedidos, com janela e duração de bloqueio configuráveis. Informar quando será possível tentar novamente e oferecer o fluxo de recuperação definido pelo banco. |
| CP-06 | Cancelar ou expirar uma intenção pendente encerra a possibilidade de pagamento. Uma compra paga possui um único lançamento e um comprovante recuperável pelo titular. Em duplo clique, reenvio ou timeout, consultar o estado e retornar o resultado existente sem repetir débito ou crédito. |
| CP-07 | Proteger transmissão com HTTPS e formulários de sessão com CSRF. Usar campo de senha mascarado. Excluir senha de URLs, logs, auditoria, ferramentas de monitoramento, persistência e respostas. Não reutilizar a confirmação em outra compra. |

**Estados.** Pendente → paga, cancelada ou expirada. Falha de senha ou saldo insuficiente gera evento de tentativa sem produzir lançamento. Se cancelamento e confirmação concorrerem, somente a primeira transição válida prevalece. Estorno posterior exige operação compensatória vinculada ao lançamento original e política específica de atendimento.

## 5. Integração técnica e requisitos comuns (Somente Backend)

| Camada | Entrega prevista |
|---|---|
| Frontend / Templates | **Fora de escopo nesta etapa.** Não criar nem modificar arquivos em `templates/`, CSS ou JS. As telas serão implementadas posteriormente consumindo a API REST descrita neste documento. |
| API REST (DRF) | Expor todas as funcionalidades sob `/bank/api/` em `account/urls.py`, com serializers dedicados, autenticação obrigatória, campos somente leitura, idempotência, códigos de erro padronizados (`400`, `403`, `404`, `409`, `422`, `429`) e documentação atualizada em `../docs/swagger/swagger.yml`. |
| Autorização | Verificar autenticação e titularidade em cada leitura e escrita, inclusive histórico e comprovante. Resolver recursos filhos dentro da conta autorizada. Tentativas com IDs alheios não devem revelar existência, saldo ou destinatário (`404`). Restringir administração de taxas, políticas, rendimentos e ajustes a papéis autorizados (`staff`/`admin`). |
| Integridade | Usar camada de serviços transacionais (`account/services/`), restrições no banco e chave de idempotência associada à operação, ao titular e ao conteúdo. Reusar chave com conteúdo diferente gera `409 Conflict`. Serializar operações que disputem o saldo, inclusive guardar e comprar simultaneamente. |
| Banco e migração | A configuração atual usa SQLite. Validar a estratégia de concorrência no banco de destino com conexões independentes. Em SQLite, usar atualização condicional e tratar contenção; não depender de bloqueio por linha. Migrar valores legados (`FloatField` → `DecimalField`) em etapas com backup, regra de arredondamento, reconciliação e ensaio de reversão. Contas antigas começam com reserva zero. Investigar divergências ou saldos negativos antes de impor restrições. |
| Operação | Registrar autor, data, referência, resultado e motivo de recusa com acesso restrito. Mascarar dados de conta nos logs. Monitorar pagamentos duplicados, divergências contábeis, falhas de credencial e indisponibilidade do simulador. Definir retenção, alertas, responsáveis e recuperação de backup antes da operação real. |

## 6. Critérios de aceite

| Caso | Ação | Resultado verificável |
|---|---|---|
| A1 | Com saldo 100, guardar 70 e tentar sacar, transferir ou pagar 31 | Total 100, reservado 70, disponível 30. Cada débito é recusado sem lançamento financeiro. |
| A2 | Resgatar 20 do cenário A1 e pagar 50 | Após resgate, disponível 50. Após compra, total 50, reserva 50, disponível zero. |
| A3 | Tentar guardar zero, valor negativo ou acima do disponível; resgatar além da reserva; arquivar com saldo | Cada tentativa retorna erro específico e preserva valores e histórico financeiro. |
| A4 | Tentar duas operações simultâneas de 70 sobre disponível 100, inclusive uma compra e um aporte | Somente uma conclui. Movimentos e saldos reconciliam após as duas respostas. |
| A5 | Simular 100 em três meses a taxa zero e sem encargos, com moeda de duas casas | Parcelas 33,33, 33,33 e 33,34. Total 100, juros zero e nenhum lançamento na conta. |
| A6 | Simular 100 em dois meses a 10% ao mês sem encargos | Com arredondamento ao centavo mais próximo, primeira prestação 57,62, última 57,62, juros totais 15,24 e saldo final zero. |
| A7 | Enviar prazo fracionário, fora da faixa, taxa adulterada ou simular sem política vigente | Prazo inválido é rejeitado. Apenas a política do servidor determina a taxa. Sem política válida, nenhum resultado é exibido como vigente. |
| A8 | Confirmar com senha errada, exceder limite de falhas ou tentar confirmar compra cancelada, expirada ou alterada | Nenhum débito. Bloqueio segue a política configurada. Alteração exige nova revisão. |
| A9 | Confirmar duas vezes, perder a resposta após gravação ou provocar falha entre débito e crédito | Repetições retornam o mesmo comprovante de uma compra paga. Falha anterior ao commit deixa ambos os saldos e o pedido consistentes. |
| A10 | Acessar conta, cofrinho, intenção, extrato ou comprovante de outro titular pela URL ou API | O servidor impede consulta e alteração. Nenhuma informação financeira do terceiro é retornada. |
| A11 | Encerrar conta com reserva; tentar operar após encerramento; consultar histórico próprio | Encerramento com reserva é recusado. Conta encerrada recusa novas operações e mantém consulta ao histórico. |
| A12 | Migrar base de ensaio e executar depósitos, saques, transferências e consultas anteriores | Totais reconciliados segundo a regra aprovada, histórico legível e débitos respeitando reservas nos fluxos antigos e novos. |
| A13 | Consultar o dashboard do Cofrinho com 2 cofrinhos ativos (`850,00` com meta `1.250,00` e `400,00` com meta `1.000,00`) e rendimentos no mês | O backend retorna `total_saved = 1250.00`, `active_count = 2`, `monthly_yield_total` correto, percentuais `68%` e `40%`, categorias, ícones, data de início e histórico recente dos últimos 30 dias. |
| A14 | Executar rotina/ação de rendimento diário ou mensal sobre cofrinho com saldo positivo | Registra lançamento do tipo `YIELD` (`Automático`), atualiza `current_balance` do cofrinho e o saldo contábil reconciliado, sem duplicar rendimento na mesma competência. |
| A15 | Consultar informações iniciais de Empréstimo e simular `3.000,00` em `12x` | O backend retorna o limite pré-aprovado disponível (ex.: `10.000,00`), atalhos `[6, 12, 24, 36]`, valor da parcela, total a pagar e lista completa das 12 parcelas com vencimento, juros, amortização e saldo devedor zerado ao final. |
| A16 | Contratar empréstimo de `3.000,00` em `12x` com limite pré-aprovado de `10.000,00` | Em transação atômica: cria contrato `Loan` e 12 registros `LoanInstallment`, credita `3.000,00` no saldo disponível da conta, registra lançamento `LOAN_DISBURSEMENT` no extrato e reduz o limite pré-aprovado disponível para `7.000,00`. |
| A17 | Tentar contratar empréstimo acima do limite pré-aprovado disponível ou reenviar a mesma requisição com a mesma `idempotency_key` | Acima do limite é recusado sem creditar conta nem criar contrato. Reenvio idempotente retorna o contrato já criado sem duplicar crédito nem parcelas. |
| A18 | Consultar endpoints de apoio do shell (`/me/`, depósito, saque, transferência, extrato filtrado e controle de gastos) | Todos validam titularidade, retornam valores decimais consistentes, respeitam saldo disponível nos débitos e entregam agregações coerentes com o extrato. |

## 7. Ordem de implementação e critérios para avançar

**Podemos começar agora pela proteção do extrato.** É uma correção pequena, verificável e independente de taxa de juros, rendimento ou checkout. Depois dela, preparar a movimentação financeira comum e entregar um módulo por vez. O escopo desta sequência é backend e API REST. As telas descritas no documento orientam o contrato de dados.

| Ordem | Entrega | Quando considerar concluída |
|---|---|---|
| 0. Isolamento por titular | Em `account/views.py`, restringir o extrato por conta e o detalhe da transação na API. Em `account/tests.py`, criar dois titulares, contas e lançamentos distintos. | O titular consulta seu extrato e as transações de que participa. A consulta por ID de outro titular recebe 404 nas duas rotas. As listagens existentes continuam funcionando. Cobre a parte de extrato de A10. |
| 1. Base financeira | Migrar saldo e valor para decimal, preservar o histórico e centralizar depósito, saque e transferência em operações atômicas. Encaminhar os métodos usados pelos formulários existentes para as mesmas regras da API. Definir o saldo disponível em um único ponto. | A12 passa em base de ensaio reconciliada. Falha entre débito e crédito reverte o conjunto. Dois débitos concorrentes não ultrapassam o disponível. Reenvio de comando financeiro é idempotente. |
| 2a. Cofrinho por conta | Primeiro cadastro, consulta e metas. Depois aporte, resgate, histórico e arquivamento. Integrar a soma das reservas a todos os caminhos de débito e à regra de encerramento. | Com saldo 100 e reserva 70, API e fluxo web existente permitem gastar até 30. Resgatar 20 eleva o disponível a 50. Validar A1–A4 nos fluxos já disponíveis, A10 para cofrinhos e A11. Repetir A1, A2 e A4 com compra na etapa 4. |
| 2b. Rendimento e resumo do cofrinho | Implementar competência, crédito de rendimento e agregação para o dashboard. Antes de ativar a rotina, definir calendário, saldo-base de cada período, origem da taxa e tratamento de competências perdidas. Validar a informação tributária do produto antes de expô-la na API. | A13 e A14 passam. Reprocessar a mesma competência preserva os totais; o crédito eleva igualmente reserva e saldo total. |
| 3. Simulação de empréstimo | Configurar política e limite pré-aprovado, implementar o cálculo Price uma vez e expor informações iniciais e simulação com cronograma. Esta etapa depende da política de crédito e pode ser testada independentemente do rendimento. | A5–A7 e A15 passam. O saldo final do cronograma é zero, os totais fecham e repetir uma simulação preserva saldo, limite e quantidade de contratos. |
| 4. Compra com senha | Definir quem emite o pedido e determina o preço, qual conta recebe e quais são os prazos de expiração e bloqueio. Implementar intenção, revisão via API, confirmação, cancelamento e comprovante. | A8 e A9 passam, além dos cenários de saldo e isolamento de A1, A2, A4 e A10. Senha incorreta não movimenta a conta. Duas confirmações do mesmo pedido geram um pagamento. |
| 5. Contratação e pagamento de parcelas | Entrega adicional prevista na seção 8.3. Reutilizar o cálculo da etapa 3 e as operações da etapa 1. Definir como pagamento e atraso afetam o limite disponível. | A16 e A17 passam. Pagar parcela atualiza saldo e contrato uma vez, inclusive após reenvio. Quitar a última encerra o contrato. |
| 6. Integração do restante da API | Completar os itens da seção 8.1 que ainda faltarem, incluindo filtros de extrato, agregações de gastos e encerramento de sessão. | A18 passa e os totais de gastos reconciliam com os lançamentos, sem contar reservas internas como despesa. |

**Primeira entrega de código.** O primeiro pedido de alteração deve conter apenas a correção das duas consultas da etapa 0 e seus testes de regressão. Na etapa 1, separar a migração monetária da mudança nas regras de débito para que a reconciliação possa ser revisada por conta e por lançamento.

**Decisões com impacto no desenho.** Para uma conta com vários cofrinhos, serializar as operações que disputam o mesmo saldo da conta. Para a compra, aplicar a idempotência à operação financeira e excluir a senha dos dados persistidos, inclusive da composição do registro de repetição. Antes de habilitar depósito em ambiente real, definir como o servidor comprova a entrada dos fundos. Um valor informado pelo titular é insuficiente para autorizar o crédito.

**Fechamento de cada entrega.** Atualizar os endpoints e exemplos correspondentes no Swagger, executar os testes de regressão e registrar os critérios da etapa que passaram. A numeração A1–A18 remete à seção 6. As decisões de CDI, crédito e compra podem ser tomadas até o início dos respectivos módulos, sem adiar a correção do extrato.

---

## 8. Especificação Detalhada de Backend (Somente API REST e Domínio — Referência das Telas Futuras)

Esta seção mapeia **exclusivamente os modelos, serviços, regras de negócio, serializers, payloads e endpoints REST** necessários no backend Django/DRF para que, quando o frontend for construído em uma etapa futura, todas as funcionalidades e dados já estejam prontos e testados. **Não implementar telas, templates HTML ou rotas web de apresentação.**

### 8.1. Shell Global, Autenticação e Navegação Lateral
As telas do frontend compartilham uma estrutura fixa composta por **cabeçalho** (`Olá, <Nome Completo>` + avatar com iniciais, ex.: `IL`) e **menu lateral** com os itens: `Home`, `Minhas contas`, `Depósito`, `Saque`, `Transferência`, `Extrato`, `Cofrinho`, `Empréstimo`, `Controle de gastos` e `Sair`.

#### Requisitos de Backend do Shell e Operações Base
* **Perfil e resumo do usuário autenticado (`GET /bank/api/me/`):**
  * Retorna: `id`, `username`, `name`, `initials` (gerado no backend a partir do primeiro e último nome ou duas primeiras palavras, ex.: `"Israel Levy da Silva Lima"` → `"IL"`), `email`, `phone_number`.
  * Retorna resumo financeiro consolidado das contas abertas do usuário: `default_account_id`, `accounts` (lista com `id`, `iban`, `is_open`, `total_balance`, `reserved_balance`, `available_balance`), `total_balance_all_accounts`, `total_reserved_all_accounts`, `total_available_all_accounts`.
* **Tipo explícito de transação (`Transaction.transaction_type`):**
  * Migrar `Account.balance` e `Transaction.amount` de `FloatField` para `DecimalField(max_digits=14, decimal_places=2)`.
  * Adicionar campo `transaction_type` em `Transaction` com valores explícitos (preservando compatibilidade com `get_type()` para registros antigos):
    * `DEPOSIT` (Depósito)
    * `WITHDRAW` (Saque)
    * `TRANSFER` (Transferência)
    * `PURCHASE` (Compra)
    * `PIGGY_DEPOSIT` (Aporte no cofrinho — ou isolado na tabela de movimentos do cofrinho conforme CF-05)
    * `PIGGY_WITHDRAW` (Resgate do cofrinho)
    * `PIGGY_YIELD` (Rendimento do cofrinho)
    * `LOAN_DISBURSEMENT` (Liberação de empréstimo)
    * `LOAN_PAYMENT` (Pagamento de parcela de empréstimo)
  * Adicionar campo opcional `category` (ex.: `Alimentação`, `Transporte`, `Moradia`, `Lazer`, `Saúde`, `Transferência`, `Empréstimo`, `Cofrinho`, `Outros`) e `description` em `Transaction` para alimentar **Extrato** e **Controle de gastos**.
* **Endpoints dedicados para as telas do menu lateral (todos exigindo autenticação, titularidade e transação atômica):**
  * `POST /bank/api/accounts/<id>/deposito/`: realiza depósito validando valor > 0 e conta aberta.
  * `POST /bank/api/accounts/<id>/saque/`: realiza saque validando `amount <= available_balance` e conta aberta.
  * `POST /bank/api/accounts/<id>/transferencia/`: transfere para `dest_iban` ou `dest_account_id` validando `amount <= available_balance`, contas abertas e origem ≠ destino.
  * `GET /bank/api/extrato/` e `GET /bank/api/accounts/<id>/extrato/`: extrato filtrado estritamente ao titular, com filtros opcionais `?type=`, `?category=`, `?start_date=`, `?end_date=`, `?days=30`, `?page=`.
  * `GET /bank/api/controle-gastos/`: retorna agregação do período (`?month=YYYY-MM` ou `?days=30`) com `total_income`, `total_expense`, `net_balance`, `by_category` (nome, valor total, percentual, quantidade de lançamentos) e evolução diária/mensal para alimentar a tela de **Controle de gastos**.
  * `POST /bank/api/logout/` (além do logout de sessão web padrão): encerra sessão para o botão `Sair`.

---

### 8.2. Backend Completo da Tela **Cofrinho**

A tela **Cofrinho** exibe:
1. **Card de Resumo Superior:** `Saldo total guardado`, contagem de cofrinhos ativos (`X cofrinhos ativos`), rendimento acumulado no mês (`+R$ XX,XX este mês`), informação de rendimento (`Rendimento automático a 100% do CDI (isento de IOF após 30 dias)`) e ações rápidas **`+ Guardar Dinheiro`** e **`↓ Resgatar`**.
2. **Seção "Meus Objetivos":** botão **`+ Novo Cofrinho`** e cards individuais contendo **ícone**, **tag/categoria** (ex.: `Prioridade`, `Lazer`), **nome**, **data de início** (`Iniciado em DD/MM/AAAA`), **saldo atual**, **barra de progresso + meta + percentual** (`Meta: R$ 1.250,00` / `68%`), indicador **`Rendendo diário`** e link **`Detalhes >`**.
3. **Seção "Histórico Recente" (Últimos 30 dias):** lista de movimentações com tipo/descrição (`Depósito no cofrinho`, `Resgate para conta`, `Rendimento mensal`), data formatada + nome curto do objetivo/regra (`15 de Fevereiro · Reserva`, `01 de Fevereiro · 100% CDI`), valor com sinal (`+ R$ 200,00`, `- R$ 100,00`, `+ R$ 5,80`), status (`Concluído`, `Saldo liberado`, `Automático`) e link **`Ver extrato completo do cofrinho →`**.

#### Modelos de Dados Necessários (`account/models.py`)
1. **`PiggyBank` (Cofrinho / Objetivo):**
   * `id`: PK.
   * `account`: `ForeignKey(Account, on_delete=models.PROTECT, related_name='piggy_banks')`.
   * `name`: `CharField(max_length=60)` (obrigatório).
   * `category`: `CharField(max_length=30, default='Geral')` — exemplos sugeridos/choices: `Prioridade`, `Lazer`, `Reserva`, `Viagem`, `Educação`, `Imóvel`, `Geral`.
   * `icon`: `CharField(max_length=30, default='piggy')` — identificadores para o front renderizar o ícone (ex.: `shield`, `plane`, `piggy`, `home`, `car`, `star`, `graduation`, `heart`).
   * `goal_amount`: `DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)` (opcional; se preenchida, deve ser > 0).
   * `current_balance`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))` (sempre >= 0).
   * `cdi_percentage`: `DecimalField(max_digits=6, decimal_places=2, default=Decimal('100.00'))` (padrão `100.00` = 100% do CDI).
   * `is_yielding_daily`: `BooleanField(default=True)`.
   * `created_at`: `DateTimeField(auto_now_add=True)` (usado para `"Iniciado em DD/MM/AAAA"`).
   * `updated_at`: `DateTimeField(auto_now=True)`.
   * `archived_at`: `DateTimeField(null=True, blank=True)` (null = cofrinho ativo).
   * **Campos/propriedades calculados (somente leitura na API):**
     * `is_active`: `archived_at is None`.
     * `progress_percent`: se `goal_amount` > 0, `round(min((current_balance / goal_amount) * 100, 999.99), 2)` (e inteiro/arredondado para barra, ex.: `68`); caso sem meta, `None`.
     * `goal_reached`: `bool(goal_amount and current_balance >= goal_amount)`.
     * `yield_status_label`: `"Rendendo diário"` quando ativo e `is_yielding_daily=True` (ou `"Sem saldo para rendimento"` se zerado — o front pode exibir conforme flag `is_yielding_daily`).
     * `days_active` e `iof_exempt`: indica se já superou 30 dias (`days_since_first_deposit >= 30`).

2. **`PiggyBankMovement` (Movimentação e Rendimento do Cofrinho):**
   * `id`: PK.
   * `reference_id`: `UUIDField(default=uuid.uuid4, unique=True, editable=False)`.
   * `piggy_bank`: `ForeignKey(PiggyBank, on_delete=models.PROTECT, related_name='movements')`.
   * `account`: `ForeignKey(Account, on_delete=models.PROTECT, related_name='piggy_bank_movements')`.
   * `movement_type`: `CharField(choices=[('DEPOSIT', 'Depósito no cofrinho'), ('WITHDRAW', 'Resgate para conta'), ('YIELD', 'Rendimento')])`.
   * `amount`: `DecimalField(max_digits=14, decimal_places=2)` (sempre positivo; sinal inferido por `movement_type`: `+` para `DEPOSIT`/`YIELD`, `-` para `WITHDRAW`).
   * `status`: `CharField(choices=[('COMPLETED', 'Concluído'), ('RELEASED', 'Saldo liberado'), ('AUTOMATIC', 'Automático')])`.
   * `title`: `CharField(max_length=80)` (ex.: `"Depósito no cofrinho"`, `"Resgate para conta"`, `"Rendimento mensal"` / `"Rendimento diário"`).
   * `subtitle`: `CharField(max_length=80, blank=True)` (ex.: nome do cofrinho ou `"100% CDI"`).
   * `competence_date`: `DateField(null=True, blank=True)` (usado para impedir duplicidade de rendimento na mesma data/competência via constraint única condicional para `movement_type='YIELD'`).
   * `idempotency_key`: `CharField(max_length=128, null=True, blank=True)`.
   * `created_at`: `DateTimeField(auto_now_add=True)`.

3. **`YieldSettings` (Configuração Global de Rendimento CDI — gerenciada no servidor/admin):**
   * `id`, `cdi_annual_rate` (`DecimalField`, ex.: `Decimal('0.1065')` = 10,65% a.a. configurável), `default_cdi_percentage` (`100.00`), `iof_exempt_after_days` (`30`), `business_days_per_year` (`252`), `is_active`, `updated_at`.

#### Regras Contábeis e de Rendimento do Cofrinho
* **Guardar (`DEPOSIT`):** verifica `amount > 0`, conta aberta, cofrinho ativo da conta e `amount <= account.available_balance`. Incrementa `piggy_bank.current_balance += amount` (preserva `account.balance`, reduz `account.available_balance`) e grava `PiggyBankMovement(movement_type='DEPOSIT', status='COMPLETED')` atomicamente.
* **Resgatar (`WITHDRAW`):** verifica `amount > 0`, cofrinho ativo e `amount <= piggy_bank.current_balance`. Decrementa `piggy_bank.current_balance -= amount` (preserva `account.balance`, aumenta `account.available_balance`) e grava `PiggyBankMovement(movement_type='WITHDRAW', status='RELEASED')` atomicamente.
* **Rendimento (`YIELD`):**
  * Taxa diária equivalente: `(1 + taxa_cdi_anual) ** (1 / 252) - 1`, multiplicada por `(piggy_bank.cdi_percentage / 100)`.
  * Ao creditar o rendimento (via comando de gerenciamento `python manage.py apply_piggybank_yield` ou serviço dedicado), o valor calculado (com arredondamento decimal `ROUND_HALF_UP` para 2 casas; somente grava se >= `0.01`) **aumenta simultaneamente `piggy_bank.current_balance` e `account.balance`** (mantendo `available_balance = account.balance - soma_reservas` inalterado até o resgate) e cria `PiggyBankMovement(movement_type='YIELD', status='AUTOMATIC')`.
  * Deve haver proteção contra aplicação duplicada para a mesma `competence_date` e mesmo `piggy_bank`.

#### Endpoints REST do Cofrinho (Somente API)
| Necessidade do Front Futuro | Endpoint API REST | Observações / Payload |
|---|---|---|
| Carregar tela inteira do Cofrinho | `GET /bank/api/cofrinhos/dashboard/` (opcional `?account_id=`) | Retorna resumo superior (`total_saved`, `active_count`, `monthly_yield_total`, `yield_policy`, `available_balance`), lista de `objectives` e `recent_history` (últimos 30 dias). |
| Listar objetivos | `GET /bank/api/cofrinhos/` (filtros `?account_id=`, `?include_archived=false`) | Lista todos os cofrinhos do titular ou da conta. |
| `+ Novo Cofrinho` | `POST /bank/api/cofrinhos/` | Body: `account_id` (opcional se cliente tiver 1 conta), `name`, `category`, `icon`, `goal_amount` (opcional). |
| `Detalhes >` (consultar) | `GET /bank/api/cofrinhos/<cid>/` | Retorna dados completos do cofrinho + rendimento acumulado + movimentos recentes do objetivo. |
| Editar cofrinho | `PATCH /bank/api/cofrinhos/<cid>/` | Permite alterar `name`, `category`, `icon`, `goal_amount` sem alterar saldo. |
| `+ Guardar Dinheiro` | `POST /bank/api/cofrinhos/<cid>/guardar/` | Body: `amount`, `idempotency_key`. Retorna cofrinho atualizado + novo `available_balance` + movimento criado. |
| `↓ Resgatar` | `POST /bank/api/cofrinhos/<cid>/resgatar/` | Body: `amount`, `idempotency_key`. Aceita resgate parcial ou total até `current_balance`. |
| Arquivar cofrinho zerado | `POST /bank/api/cofrinhos/<cid>/arquivar/` | Recusa com `409 Conflict` se `current_balance > 0`. |
| `Ver extrato completo do cofrinho →` | `GET /bank/api/cofrinhos/extrato/` e `GET /bank/api/cofrinhos/<cid>/extrato/` | Filtros: `?days=30`, `?type=DEPOSIT|WITHDRAW|YIELD`, `?piggy_bank_id=`, `?page=`. |
| Aplicar rendimento (admin/cron/dev) | `POST /bank/api/cofrinhos/aplicar-rendimento/` (restrito a staff/admin) + comando `manage.py apply_piggybank_yield` | Permite simular/executar o crédito diário ou mensal de rendimentos com idempotência por data. |

---

### 8.3. Backend Completo da Tela **Empréstimo**

A tela **Empréstimo** exibe:
1. **Cabeçalho de Limite:** `Limite pré-aprovado disponível: R$ 10.000,00`.
2. **Simulador Interativo:**
   * Campo `Quanto você precisa?` (valor desejado, ex.: `R$ 3.000,00`).
   * Campo `Em quantas vezes?` (input livre + botões de seleção rápida `6x`, `12x`, `24x`, `36x`).
3. **Painel de Resultado da Simulação:**
   * `Parcela estimada` (ex.: `12x de R$ 283,50`).
   * `Total a pagar` (ex.: `R$ 3.402,06`).
   * Acordeão expansível **`Ver detalhes das parcelas (12x de R$ 283,50)`** contendo o demonstrativo completo de cada parcela.
4. **Botão Principal:** **`Contratar Empréstimo →`**.

#### Modelos de Dados Necessários (`account/models.py`)
1. **`CreditPolicy` (Política de Crédito Vigente):**
   * `id`: PK.
   * `version`: `CharField(max_length=32, unique=True)` (ex.: `"2026.1"`).
   * `monthly_interest_rate`: `DecimalField(max_digits=8, decimal_places=6)` (taxa efetiva mensal em fração, ex.: `Decimal('0.019900')` ≈ 1,99% a.m., que resulta em ~`12x de R$ 283,50` / total `R$ 3.402,06` para `R$ 3.000,00` na Tabela Price).
   * `min_amount`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('100.00'))`.
   * `max_amount`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('50000.00'))`.
   * `min_installments`: `PositiveIntegerField(default=1)`.
   * `max_installments`: `PositiveIntegerField(default=36)`.
   * `quick_installments`: `JSONField(default=list)` (padrão `[6, 12, 24, 36]`).
   * `default_preapproved_limit`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('10000.00'))`.
   * `fixed_fee`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))`.
   * `iof_rate`: `DecimalField(max_digits=8, decimal_places=6, default=Decimal('0.000000'))`.
   * `is_active`: `BooleanField(default=True)`.
   * `effective_from`: `DateTimeField(auto_now_add=True)`.
   * *(Migration de dados inicial deve criar 1 `CreditPolicy` ativa padrão para que a tela funcione imediatamente sem indisponibilidade em ambiente novo.)*

2. **Limite Pré-aprovado do Cliente (em `Client` ou modelo dedicado `ClientCreditProfile`):**
   * `preapproved_limit`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('10000.00'))` (configurável por cliente).
   * **Cálculo de limite disponível (no servidor):**
     * `used_limit = soma(principal_amount de empréstimos ACTIVE do cliente)` (ou soma do saldo devedor principal restante das parcelas `PENDING`/`OVERDUE`).
     * `available_limit = max(Decimal('0.00'), preapproved_limit - used_limit)`.

3. **`Loan` (Contrato de Empréstimo Contratado):**
   * `id`: PK.
   * `contract_number`: `CharField(max_length=32, unique=True)` (gerado automaticamente, ex.: `EMP-20261124-XXXX`).
   * `client`: `ForeignKey(Client, on_delete=models.PROTECT, related_name='loans')`.
   * `account`: `ForeignKey(Account, on_delete=models.PROTECT, related_name='loans')` (conta onde o crédito foi depositado).
   * `policy`: `ForeignKey(CreditPolicy, on_delete=models.PROTECT)`.
   * `policy_version`: `CharField(max_length=32)`.
   * `principal_amount`: `DecimalField(max_digits=14, decimal_places=2)`.
   * `installments_count`: `PositiveIntegerField()`.
   * `monthly_interest_rate`: `DecimalField(max_digits=8, decimal_places=6)`.
   * `annual_effective_rate`: `DecimalField(max_digits=8, decimal_places=6)`.
   * `installment_amount`: `DecimalField(max_digits=14, decimal_places=2)` (prestação base).
   * `total_interest`: `DecimalField(max_digits=14, decimal_places=2)`.
   * `total_fees`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))`.
   * `total_payable`: `DecimalField(max_digits=14, decimal_places=2)`.
   * `status`: `CharField(choices=[('ACTIVE', 'Ativo'), ('PAID_OFF', 'Quitado'), ('CANCELLED', 'Cancelado')], default='ACTIVE')`.
   * `disbursement_transaction`: `OneToOneField(Transaction, on_delete=models.PROTECT, related_name='loan_disbursement')`.
   * `idempotency_key`: `CharField(max_length=128, null=True, blank=True)`.
   * `contracted_at`: `DateTimeField(auto_now_add=True)`.

4. **`LoanInstallment` (Parcela do Empréstimo):**
   * `id`: PK.
   * `loan`: `ForeignKey(Loan, on_delete=models.PROTECT, related_name='installments')`.
   * `number`: `PositiveIntegerField()` (1 até `N`).
   * `due_date`: `DateField()` (1ª parcela após 1 mês completo a partir da contratação; subsequentes mês a mês).
   * `opening_balance`: `DecimalField(max_digits=14, decimal_places=2)`.
   * `interest_amount`: `DecimalField(max_digits=14, decimal_places=2)`.
   * `amortization_amount`: `DecimalField(max_digits=14, decimal_places=2)`.
   * `total_amount`: `DecimalField(max_digits=14, decimal_places=2)`.
   * `closing_balance`: `DecimalField(max_digits=14, decimal_places=2)` (`0.00` na última parcela).
   * `status`: `CharField(choices=[('PENDING', 'Pendente'), ('PAID', 'Paga'), ('OVERDUE', 'Em atraso')], default='PENDING')`.
   * `paid_at`: `DateTimeField(null=True, blank=True)`.
   * `payment_transaction`: `ForeignKey(Transaction, null=True, blank=True, on_delete=models.PROTECT)`.
   * Constraint única: `(loan, number)`.

#### Regras de Cálculo (Serviço Único Compartilhado entre Simulação e Contratação)
* Toda simulação e contratação chama exatamente o mesmo serviço (`simulate_loan(policy, principal, installments, reference_date)`):
  * Utiliza aritmética `Decimal` com arredondamento `ROUND_HALF_UP` para 2 casas decimais.
  * Tabela Price conforme SE-03/SE-04/SE-05, ajustando a última parcela para que a soma das amortizações seja exatamente igual ao `principal_amount` e o `closing_balance` da parcela `N` seja `0.00`.
  * Nunca aceita taxa de juros ou valor de parcela enviados pelo frontend.
  * Em caso de `amount > available_limit`, a simulação pode retornar erro de validação (`400`) ou sinalizar `can_contract: false` com `exceeds_limit_message` (e na contratação **sempre** recusa com `400/422`).

#### Endpoints REST de Empréstimo (Somente API)
| Necessidade do Front Futuro | Endpoint API REST | Observações / Payload |
|---|---|---|
| Carregar tela de Empréstimo | `GET /bank/api/emprestimos/config/` | Retorna `preapproved_limit_total`, `preapproved_limit_available`, `min_amount`, `max_amount`, `min_installments`, `max_installments`, `quick_installments` (`[6, 12, 24, 36]`), `policy_version`, `monthly_interest_rate`, `annual_effective_rate`, `accounts` abertas do titular. |
| Simular ao alterar valor ou parcelas | `POST /bank/api/emprestimos/simular/` | Body: `amount`, `installments`, opcional `account_id`. Retorna estimativa completa (`installment_amount`, `last_installment_amount`, `has_last_installment_diff`, `total_interest`, `total_fees`, `total_payable`, `monthly_interest_rate`, `annual_effective_rate`, `policy_version`, `reference_date`, `assumptions`, `can_contract`) **e o array `installments_schedule`** com todas as `N` parcelas para preencher o acordeão **`Ver detalhes das parcelas`**. |
| **`Contratar Empréstimo →`** | `POST /bank/api/emprestimos/contratar/` | Body: `account_id` (opcional se tiver 1 conta aberta), `amount`, `installments`, `idempotency_key` (e `password` caso a política de confirmação de senha seja ativada para contratação). Em transação atômica: valida limite pré-aprovado e conta aberta, recalcula Tabela Price, cria `Loan` + `LoanInstallment`s, credita `amount` na conta, registra `Transaction(LOAN_DISBURSEMENT)` e retorna contrato + novo limite disponível + novo saldo. |
| Listar empréstimos contratados | `GET /bank/api/emprestimos/` | Retorna contratos do titular com saldo devedor restante e próximas parcelas. |
| Detalhar contrato e parcelas | `GET /bank/api/emprestimos/<loan_id>/` | Restrito ao titular; lista todas as parcelas com status (`PENDING`, `PAID`, `OVERDUE`). |
| Pagar parcela do empréstimo | `POST /bank/api/emprestimos/<loan_id>/parcelas/<installment_id>/pagar/` | Debita do `available_balance` da conta, registra `Transaction(LOAN_PAYMENT)`, marca parcela como `PAID` e quita o contrato (`PAID_OFF`) quando não restarem parcelas pendentes. |

---

### 8.4. Endpoints REST da Confirmação de Compra com Senha (Somente API)
Para completar as regras da Seção 4 exclusivamente via backend/API:
* `POST /bank/api/compras/`: cria uma intenção de compra pendente (`PurchaseIntent`) vinculada à conta pagadora, recebedor autorizado, referência comercial, valor decimal positivo, moeda e expiração.
* `GET /bank/api/compras/` e `GET /bank/api/compras/<reference>/`: lista ou consulta uma intenção/comprovante exclusivamente do titular (conta mascarada, estabelecimento, referência, valor, validade, status e comprovante quando paga).
* `POST /bank/api/compras/<reference>/confirmar/`: recebe `password` e `idempotency_key`, verifica senha do titular (com contagem persistente de falhas e bloqueio temporário por excesso de tentativas), revalida status/validade/saldo disponível e executa débito + crédito + lançamento `PURCHASE` + comprovante em uma única transação atômica. Nunca loga ou retorna a senha.
* `POST /bank/api/compras/<reference>/cancelar/`: cancela intenção ainda pendente, impedindo pagamento posterior.

---

### 8.5. Padrões Técnicos Transversais (Somente Backend)
1. **Respostas JSON padronizadas e prontas para consumo futuro:**
   * Valores monetários sempre retornados como strings decimais formatadas com duas casas (ex.: `"1250.00"`) para evitar perda de precisão em `Number` do JavaScript, podendo incluir `currency: "BRL"`.
   * Datas em ISO-8601 (`YYYY-MM-DD` / `YYYY-MM-DDTHH:MM:SSZ`) para formatação no cliente sem ambiguidade.
   * Erros padronizados em português contendo `code` (ex.: `INSUFFICIENT_AVAILABLE_BALANCE`, `CREDIT_LIMIT_EXCEEDED`, `PIGGY_BANK_NOT_EMPTY`, `INVALID_PASSWORD`, `ACCOUNT_CLOSED`, `IDEMPOTENCY_CONFLICT`, `POLICY_UNAVAILABLE`), `detail` e `field_errors`.
2. **Idempotência obrigatória em todas as operações de escrita financeira:**
   * Aceitar cabeçalho HTTP `Idempotency-Key` (ou campo `idempotency_key` no payload) em: aporte/resgate de cofrinho, contratação de empréstimo, pagamento de parcela, confirmação de compra, depósito, saque e transferência.
   * Persistir chave + titular + hash do payload + resposta; reenvio idêntico devolve o resultado original sem duplicar movimentação; mesma chave com payload diferente retorna `409 Conflict`.
3. **Segurança e Isolamento por Titular:**
   * Corrigir imediatamente as brechas existentes em `TransactionListView` (filtro por `account_id`) e `TransactionViewSet.retrieve` (consulta por `pk` sem filtrar por `request.user`), garantindo `404` quando um recurso não pertencer ao usuário autenticado.
   * Nunca retornar ou registrar `password` em logs, payloads, auditoria ou respostas.
4. **Camada de Serviços (`account/services/`):**
   * Organizar a lógica de domínio em módulos dedicados (`account/services/ledger.py`, `account/services/piggy_bank.py`, `account/services/loans.py`, `account/services/purchases.py`) consumidos exclusivamente pelos endpoints DRF (e testes automatizados).
5. **Documentação OpenAPI/Swagger (`docs/swagger/swagger.yml`):**
   * Atualizar `swagger.yml` com todos os novos schemas, endpoints REST, códigos de erro e exemplos de payload de Cofrinho, Empréstimo, Compra, Extrato e Controle de Gastos.

### Operação local da etapa 2b

O dashboard está disponível em `GET /bank/api/cofrinhos/dashboard/`, com filtro opcional por `account_id`. O total de rendimento mensal usa a data de competência. O histórico recente usa a data de lançamento.

A política é cadastrada no admin Django em **Yield settings**, com início de vigência, CDI anual em fração, percentual do CDI e divisor anual. A migração deixa a taxa sem configuração. Os cálculos usam o saldo do cofrinho no encerramento de cada competência, com capitalização dos rendimentos das competências anteriores e arredondamento diário ao centavo. O calendário implementado considera segunda a sexta e o fuso do projeto. O processamento considera cofrinhos ativos de contas abertas. Calendário de feriados, tratamento de objetivos arquivados antes de um crédito em atraso e texto tributário dependem da definição do produto para operação real.

- Simular um mês fechado: `python manage.py apply_piggybank_yield --month 2025-02 --dry-run`.
- Creditar um dia encerrado: `python manage.py apply_piggybank_yield --date 2025-02-03`.
- Reprocessar dias perdidos em ordem cronológica, individualmente ou por mês fechado. O lote mensal percorre as mesmas competências do processamento diário e ignora créditos já registrados. Lacunas anteriores a créditos posteriores exigem reconciliação.
- O endpoint administrativo `POST /bank/api/cofrinhos/aplicar-rendimento/` aceita `date` ou `month` e `preview`. A execução periódica depende de um agendador que invoque o comando.
