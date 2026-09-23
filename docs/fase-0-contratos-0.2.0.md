# Fase 0 — contratos e preparação da 0.2.0

Execução: 23/09/2026. Escopo: plano, contratos e correções imediatas autorizadas.
Não foram implementados G5, autoridade local estrita, novos atributos, instalador
ou healthchecks. O [plano de fases](plano-0.2.0.md) foi escrito antes das alterações.

## Ambiente e força das evidências

Foram extraídas cópias oficiais independentes do repositório Chatwoot, sem modificar
a instalação existente, com Community Edition explícita (`DISABLE_ENTERPRISE=true`):

| Versão | Commit oficial | Banco exclusivo |
|---|---|---|
| 4.16.2 | `70e284a044f00326725f65f703162745371075ec` | `kanban_phase0_cw4162_test` |
| 4.18.0 | `9f920b549c14491a4e587687a3eed5d21c6ccc7d` | `kanban_phase0_cw4180_test` |

A suíte [chatwoot_phase0.rb](../tests/contracts/chatwoot_phase0.rb) executou o Rails
real e PostgreSQL real. As requisições usam `ActionDispatch::Integration::Session`
e atravessam rotas, autenticação, controllers, políticas e persistência. Não são
respostas HTTP simuladas. Cada execução criou fixtures com credenciais aleatórias
em memória dentro de uma transação desfeita ao final. Não usa contas reais nem
imprime tokens, senhas, headers ou corpos das respostas.

Limite: `RAILS_ENV=test`, fila ActiveJob de teste e Redis de teste do upstream.
Isto não certifica navegador, entrega HTTP do webhook, Sidekiq, proxy ou Swarm.
Os casos de assinatura e scripts invocam métodos reais diretamente, conforme abaixo.
As duas execuções terminaram com código 0; houve apenas avisos de depreciação upstream.

## Matriz de resultados

| Contrato / nome emitido pela suíte | Evidência executada | 4.16.2 | 4.18.0 |
|---|---|---|---|
| `sessao_login_profile` | Login de administrador e agente; headers access-token/client/uid; profile com ID, papel e associação ativa; sem sessão recebe 401 | Passou | Passou |
| `sessao_logout_revogacao` | Logout e reutilização dos mesmos headers em profile recebe 401 | Passou | Passou |
| `inboxes_agente_admin_isolamento` | Duas caixas, agente em apenas uma; agente recebe uma, administrador duas; conta alheia 401; remover InboxMember esvazia o resultado | Passou | Passou |
| `atributos_modelos_tipos_unicidade_conta` | GET vazio; criação por API com token de User administrador; mesma chave em contato/conversa; duplicata no mesmo modelo 422; retorno normaliza enums para strings; outra conta preservada | Passou | Passou |
| `prioridade_nativa` | POST toggle_priority e reload do registro confirmam low, medium, high, urgent | Passou | Passou |
| `automacao_condicao_atributo_contato` | ConditionsFilterService com contact_attribute retorna true e depois false quando muda o valor do contato | Passou | Passou |
| `webhook_api_secret_assinatura` | POST/GET de webhook retornam secret; gerador real de headers produz HMAC SHA256(timestamp.corpo), prefixo sha256= e delivery ID esperado | Passou | Passou |
| `dashboard_scripts_configuracao_controller` | InstallationConfig + GlobalConfig + controller entregam script na rota normal e omitem na edição de senha | Passou | Passou |
| `usuario_servico_platform_api` | API cria User normal, vincula administrador na conta permitida, retorna token utilizável; conta não permitida recebe 401 | Passou | Passou |

O contrato de `/inboxes` sustenta a inclusão planejada de agentes. O filtro do
Kanban ainda precisa ser implementado e testado em todos os recursos na Fase 1;
este resultado não libera acesso de agentes ao código atual. Não foi necessário
acionar o fallback de release exclusiva para administradores.

O cookie `cw_d_session_info` é gravado pelo JavaScript do Chatwoot a partir dos
headers de autenticação. O teste Rails comprova os headers e `/profile`, não a
gravação/leitura desse cookie no navegador. Da mesma forma, o controller entrega
`DASHBOARD_SCRIPTS`, mas renderização do menu/iframe nas duas versões ainda integra
o gate de navegador. A suíte não realizou entrega de webhook pela rede nem mediu
retentativas do Sidekiq. Não presumir entrega garantida; reconciliação continua necessária.

### Fontes oficiais inspecionadas

As referências abaixo estão fixadas nos commits testados. Cada par contém a mesma
área de contrato nas duas versões, sem depender de `develop` ou documentação mutável.

| Área | 4.16.2 | 4.18.0 |
|---|---|---|
| Sessão no frontend | [auth.js](https://github.com/chatwoot/chatwoot/blob/70e284a044f00326725f65f703162745371075ec/app/javascript/dashboard/api/auth.js) | [auth.js](https://github.com/chatwoot/chatwoot/blob/9f920b549c14491a4e587687a3eed5d21c6ccc7d/app/javascript/dashboard/api/auth.js) |
| Escopo de caixas | [InboxPolicy](https://github.com/chatwoot/chatwoot/blob/70e284a044f00326725f65f703162745371075ec/app/policies/inbox_policy.rb) | [InboxPolicy](https://github.com/chatwoot/chatwoot/blob/9f920b549c14491a4e587687a3eed5d21c6ccc7d/app/policies/inbox_policy.rb) |
| Definições de atributos | [modelo](https://github.com/chatwoot/chatwoot/blob/70e284a044f00326725f65f703162745371075ec/app/models/custom_attribute_definition.rb) | [modelo](https://github.com/chatwoot/chatwoot/blob/9f920b549c14491a4e587687a3eed5d21c6ccc7d/app/models/custom_attribute_definition.rb) |
| Assinatura | [Trigger](https://github.com/chatwoot/chatwoot/blob/70e284a044f00326725f65f703162745371075ec/lib/webhooks/trigger.rb) | [Trigger](https://github.com/chatwoot/chatwoot/blob/9f920b549c14491a4e587687a3eed5d21c6ccc7d/lib/webhooks/trigger.rb) |
| Scripts | [controller](https://github.com/chatwoot/chatwoot/blob/70e284a044f00326725f65f703162745371075ec/app/controllers/dashboard_controller.rb) | [controller](https://github.com/chatwoot/chatwoot/blob/9f920b549c14491a4e587687a3eed5d21c6ccc7d/app/controllers/dashboard_controller.rb) |
| Automações | [condições](https://github.com/chatwoot/chatwoot/blob/70e284a044f00326725f65f703162745371075ec/app/services/automation_rules/conditions_filter_service.rb) | [condições](https://github.com/chatwoot/chatwoot/blob/9f920b549c14491a4e587687a3eed5d21c6ccc7d/app/services/automation_rules/conditions_filter_service.rb) |
| Usuários de plataforma | [controller](https://github.com/chatwoot/chatwoot/blob/70e284a044f00326725f65f703162745371075ec/app/controllers/platform/api/v1/users_controller.rb) | [controller](https://github.com/chatwoot/chatwoot/blob/9f920b549c14491a4e587687a3eed5d21c6ccc7d/app/controllers/platform/api/v1/users_controller.rb) |

### Reprodução

Em checkout limpo de cada tag, instale seu bundle e carregue `db:schema:load` em
um dos bancos exclusivos da tabela, com Rails test e CE. Configure DATABASE_URL
pelo ambiente; nunca use o banco da instalação ativa. Execute na raiz do Chatwoot:

```sh
RAILS_ENV=test DISABLE_ENTERPRISE=true LOG_LEVEL=fatal \
  bundle exec rails runner /caminho/chatwoot-kanban/tests/contracts/chatwoot_phase0.rb
```

A suíte recusa outros nomes de banco. O caminho acima é um placeholder e não
contém credenciais. Ruby usado: 3.4.4. As dependências de 4.18.0 foram instaladas
em GEM_HOME isolado; cada versão usou seu próprio Gemfile.lock. As cópias desta
execução ficaram em `/tmp/kanban-phase0-4162` e `/tmp/kanban-phase0-4180`.

## Comparação dos atributos antes de migrar

O provisionamento atual está em `app/services.py:ensure_attributes`; as projeções
e a leitura de atributos antigos também estão nesse módulo. Nenhuma chave foi
renomeada nesta sessão.

| Hoje | Proposta aprovada | Encaminhamento na Fase 2 |
|---|---|---|
| contato `pipeline_01_etapas`, lista | Sem equivalente obrigatório | Deprecar espelho do funil principal; compatibilidade explícita durante transição |
| contato `kanban_etapa`, texto, nome “Último funil e etapa” | contato `kanban_etapa`, texto, “Funil / Etapa” | Reutilizar definição compatível; não sobrescrever metadados de terceiros |
| contato `kanban_view_mensaje`, texto | contato `kanban_tarefa`, texto | Criar nova definição, projetar tarefa local e migrar consumidores |
| contato `kanban_view_fecha_termino`, data | contato `kanban_tarefa_vencimento`, data | Criar nova definição, projetar vencimento local e migrar consumidores |
| `origem`, `campanha`, `temperatura` lidos por chave fixa | Opcionais, com mapeamento por conta | Provisionar somente conforme escolha; métricas/importação usam chave configurada |
| Sem provisionamento equivalente na conversa | conversa `kanban_etapa`, texto, opcional | Recomendada dispensa inicial; manter opção se houver necessidade de evento específico |

Identidade da definição: `(account_id, attribute_model, attribute_key)`. As duas
versões permitem `kanban_etapa` em contato e conversa simultaneamente. O catálogo
não pode usar apenas a chave, como faz a indexação atual. Definição somente no
modelo errado deve gerar diagnóstico conforme decisão do mantenedor; definição
correta em ambos os modelos não é, por si, conflito.

Migração proposta, sem execução: inventariar definições/consumidores por conta;
fazer backup; criar/reutilizar destinos via catálogo único; preencher os novos
espelhos a partir de tarefas e cartões locais; verificar valores; adaptar
automações/consumidores e efetuar corte. Escrita dupla temporária só se necessária
e explicitamente configurada. Não importar um espelho divergente por cima do
estado local. Preservar definições antigas; não atribuir propriedade ao Kanban
sem manifesto que a comprove. Chaves espanholas da API de tarefas, como `mensaje`
e `fecha_vencimiento`, são outro contrato e não serão renomeadas por arrasto.

O catálogo `app/provisioning/attributes.py`, manifesto, dry-run, tratamento de
conflitos, mapeamentos e testes de ativação idempotente pertencem à Fase 2.
O adaptador do instalador e `--purge-attributes` pertencem à Fase 4.

## Perguntas em aberto e encaminhamentos

### 1. MIT ou AGPL-3.0 — decisão antes da Fase 5

MIT: manter LICENSE e avisos de autoria; revisar metadados e documentação da
distribuição. Não exige publicar modificações privadas. AGPL: substituir a licença
do código próprio da nova distribuição, definir `AGPL-3.0-only` ou `-or-later`,
atualizar metadados/documentação e, se adotados, cabeçalhos SPDX. Preparar acesso ao
código correspondente às imagens distribuídas e oferta de fonte aos usuários de
versões modificadas via rede. Inventariar autoria e licenças antes da alteração.
Fontes: [MIT](https://choosealicense.com/licenses/mit/) e
[texto AGPL-3.0](https://choosealicense.com/licenses/agpl-3.0/).

Em ambas: preservar `app/static/vendor/Chart.LICENSE.md` e o cabeçalho MIT de
Chart.js; não declarar esse fornecedor como código próprio sob AGPL. Preservar
avisos MIT de código incorporado. Não reescrever histórico/tags nem tentar revogar
cópias anteriores já disponibilizadas sob MIT. Nada obriga alterar a licença do
Chatwoot separado; este projeto não altera seu código. Nenhuma licença foi mudada.

### 2. Canal privado — decisão antes da Fase 5

Recomendação: habilitar e testar Private Vulnerability Reporting com GitHub Security
Advisories no repositório público e publicar o link no SECURITY. E-mail dedicado é
alternativa se houver responsável e rotina de leitura. Advisories, por si só, não
comprovam que o recebimento privado está habilitado. Nesta cópia não foi configurado
nenhum canal remoto. [Documentação do GitHub](https://docs.github.com/en/code-security/concepts/vulnerability-reporting-and-management/repository-security-advisories).

### 3. Dois espelhos — decisão antes das Fases 2 e 4

As condições de automação aceitam atributos do contato nas duas versões, comprovado
com correspondência positiva e negativa no serviço real. Recomendo dispensar o
espelho de conversa por padrão: reduz escritas, divergências e dependência da troca
de conversa vinculada. Contudo, condição não é gatilho: o listener de automações
trata eventos de conversa/mensagem, não `contact_updated`. Se a intenção for
disparar uma ação imediatamente quando mover uma etapa, apenas escrever no contato
não garante execução. Esse cenário precisa de contrato próprio (eventualmente I1)
ou de um teste específico antes de justificar o segundo espelho.

### 4. Capacidade — mudanças e certificação na Fase 3

Não considero os volumes certificados nem recomendo publicá-los com o quadro atual
sem paginação. Trinta clientes SSE reservam trinta conexões PostgreSQL, além dos
pools da API, worker e Chatwoot; isso pode caber, mas exige orçamento explícito,
principalmente com múltiplas réplicas. Cinco mil cartões carregados por trinta
clientes correspondem a 150 mil representações de cartões por atualização global,
antes de considerar custo DOM, filtros e metadados remotos. Vinte mil contatos
ampliam importação e chamadas remotas; não equivalem a vinte mil cartões.

Necessário: paginação/filtros/autorização no servidor e totais independentes da
página; renderização limitada no cliente; importação retomável em lotes com limites;
metadados incrementais/cache; coalescência de invalidações SSE e reconexão com atraso;
índices e orçamento total de conexões. Recomendo um listener PostgreSQL compartilhado
por processo com distribuição autorizada aos clientes, ou demonstrar por carga que
o modelo atual cabe no orçamento. Medir 30 sessões mistas, latência p95, memória,
conexões, atraso da fila, reconexão e isolamento de contas. Hardware e metas ainda
precisam ser acordados; estimativas aritméticas não são benchmark.

### 5. Celular — escolha de escopo antes das Fases 3 e 5

Recomendação para a 0.2.0: documentar a ausência no app nativo; oferecer URL direta
somente se couber um fluxo autenticado testado, com tema padrão, navegação própria,
toque e retorno ao login. Abrir `/kanban` não resolve automaticamente a ausência
de sessão no navegador móvel. Não usar token técnico na URL nem presumir que o app
nativo compartilha cookies. A alternativa fica no plano, sem implementação agora.

### 6. Usuário de serviço — decisão do adaptador na Fase 4

Nas duas versões a API Platform permite criar User normal via POST `/platform/api/v1/users`,
associá-lo como administrador via POST `/platform/api/v1/accounts/{id}/account_users`
e obter token via POST `/platform/api/v1/users/{id}/token`. A sequência passou e o
token autenticou a API de atributos. Não é AgentBot.

API sem Rails é viável quando já existe Platform App com credencial e permissão
explícita nas contas escolhidas. Token de administrador da conta não substitui
essa credencial. A suíte criou PlatformApp/permissão como fixture Rails: não provou
bootstrap sem acesso administrativo à instalação. O instalador deve detectar o
pré-requisito e apresentar o caminho escolhido no plano.

Rails runner é alternativa para bootstrap local sob controle do operador: cria
User/AccountUser e obtém token pelos modelos, mas depende de execução no container,
versão dos modelos e acesso elevado ao banco. Preferir API quando já preparada;
caso contrário, adaptador Rails explícito, idempotente e isolado, sem alterar fontes
do Chatwoot. Em ambos, transportar segredo somente em memória/canal protegido,
cifrá-lo no destino e registrar IDs/propriedade, nunca o token no manifesto.

## Ressalvas às decisões

- Cache de cinco minutos cria uma janela de até cinco minutos para revogar acesso
  a uma caixa. Não descrevê-lo como revogação imediata. Definir invalidação antecipada
  ou aceitar expressamente a janela antes da Fase 1; expiração com falha deve negar.
- Política por caixa é deliberadamente mais restrita que possíveis acessos por
  time/participação de conversa no Chatwoot. Não prometer paridade total de permissões.
- Tarefa compartilhada por contato pode aparecer em cartões de funis/caixas com
  escopos diferentes. Definir autorização da tarefa e do histórico sem usar a
  existência de qualquer cartão como passe para dados dos demais. Card sem conversa
  fica visível apenas ao administrador segundo a política aprovada.
- Dispenso o segundo espelho apenas para condições de automação; não estendo essa
  conclusão a gatilhos imediatos. Não discordo das demais decisões de produto.

## Correções e verificações locais

- Removido storageState persistido de board-design e dos outros consumidores de
  sessão salva. Testes iniciam contexto novo em memória.
- README e testes browser usam CHATWOOT_LOGIN_EMAIL/CHATWOOT_LOGIN_PASSWORD, sem
  credenciais padrão. O teste de indisponibilidade recusa ausência delas antes de
  qualquer comando que reinicie serviços.
- SQLAlchemy declarado diretamente; httpx duplicado removido; AUTH duplicado removido.
- SECURITY e CONTRIBUTING corrigidos para sessão real, PostgreSQL, fila e limitações.

Verificações: `ruff check .` passou; `pytest -q`: **35 passaram** em `kanban_test`;
`node --test tests/test_interface.cjs`: **3 passaram**; `node --check` em todos os
JS/CJS de app/static e tests/browser passou. Helper de credenciais falhou como
esperado com as duas variáveis ausentes. Contratos Rails: **9 grupos por versão**,
todos passaram. Não foram executados os roteiros browser completos nesta sessão.
Não foi feita certificação de carga ou Swarm (Docker indisponível neste ambiente).

Esta cópia do Kanban não tem diretório `.git`; não foi possível produzir commit
ou PR. Versão do pacote e tags não foram alteradas. Permanecem como gates futuros
as provas de navegador/entrega, autorização integral, implantação e carga.
