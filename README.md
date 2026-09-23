# Kanban dentro do Chatwoot

Quadros, múltiplos funis, tarefas, histórico e relatórios integrados ao **Chatwoot 4.16.2**.
Acesse **http://localhost:3000**, entre no Chatwoot e clique em **Pipeline → Kanban** no menu lateral.
O grupo também contém **Métricas**, com os relatórios por funil, etapa e agente.
O quadro herda a fonte e as cores do Chatwoot, inclusive ao trocar de tema.
A interface é em português do Brasil e usa a sessão e as permissões da conta selecionada.

O código original do Chatwoot é preservado. Um loader registrado em `DASHBOARD_SCRIPTS`
abre o quadro incorporado pelo menu lateral. Não instala abas dentro das conversas.

## Executar nesta máquina

Os bancos do Kanban são `kanban_development` e `kanban_test`. O Chatwoot continua
usando `chatwoot_dev`; não execute seed novamente.

```sh
cd /Users/paim/chatwoot-kanban
scripts/local.sh status
scripts/local.sh stop
scripts/local.sh start
```

O script inicia Rails em 3001, FastAPI em 8000, worker, Sidekiq e Nginx em 3000.
Reutiliza o Vite existente na porta 3036; se não houver um, inicia também o Vite.
PostgreSQL e Redis precisam estar em execução. As variáveis do banco Kanban são
removidas do ambiente antes de iniciar Rails, Sidekiq e Vite.

## Usar

- Selecione um funil; arraste cartões entre etapas e dentro de uma coluna.
- **Adicionar negociação** abre a busca de contatos da conta; selecione o contato, o funil e a etapa.
- Clique no cartão para abrir detalhes; ali você pode abrir a conversa ou o cadastro do contato.
- **Detalhes** permite mudar a etapa e o valor. **Tarefa** cria, edita e conclui a tarefa.
- Um contato pode participar de vários funis, mas sua tarefa ativa é compartilhada.
- Administradores podem gerenciar funis/etapas, repetir importações e tentar sincronizar novamente.
- Consulte **Histórico** e **Relatórios**; ganhos ÷ (ganhos + perdas) define a conversão.
- Tarefas vencem durante toda a data escolhida em Brasília; ficam atrasadas no dia seguinte.
- O acesso ao Kanban fica exclusivamente no menu **Pipeline**.

O banco Kanban é a referência de cartões e tarefas. Uma falha temporária no Chatwoot
aparece como sincronização pendente/falha, e o worker tenta novamente. Alterações
concorrentes retornam conflito em vez de sobrescrever silenciosamente o trabalho de alguém.

## Instalação, migração e infraestrutura

- [Instalação local e desinstalação](docs/instalacao-local.md)
- [Backup, recuperação e dados legados](docs/backup-recuperacao.md)
- [Swarm/Traefik, preparado para implantação futura](docs/implantacao-swarm.md)
- [Decisões da integração](docs/adr/020-integracao-nativa-sessao.md)
- [Validação desta entrega](docs/validacao-integracao.md)

## Testes

```sh
.venv/bin/ruff check app migrations scripts tests
DATABASE_URL=postgresql://paim@localhost:5432/kanban_test .venv/bin/alembic upgrade head
.venv/bin/pytest -q
node --test tests/test_interface.cjs
node --check app/static/kanban.js
node --check app/static/loader.js
```

Os testes Python usam PostgreSQL real e truncam somente as tabelas `kb_*` do banco
configurado por `TEST_DATABASE_URL`, que deve ser exclusivo de testes.
O teste de navegador exige Chatwoot local, Chrome e Playwright; cria contatos/funis de teste:

```sh
npm ci
# Configure CHATWOOT_LOGIN_EMAIL e CHATWOOT_LOGIN_PASSWORD no ambiente
# com credenciais de uma conta exclusiva de testes. Não coloque a senha no comando.
node tests/browser/live.cjs
```

Os testes de navegador exigem as duas variáveis e não têm credenciais padrão.
Carregue-as por entrada protegida ou pelo gerenciador de segredos do ambiente.
Sessões permanecem em memória e não são enviadas por `postMessage`.

## Licença

[MIT](LICENSE). Atribuição original: Copyright (c) 2026 Chatwoot-Kanban contributors.
Licença recuperada do [repositório original](https://github.com/CrisAlva1414/Chatwoot-Kanban/blob/main/LICENSE).

## Métricas do Pipeline

Abra **Pipeline → Métricas** dentro do Chatwoot. O endereço incorporado é
`/kanban/metricas?account=N`. Funil, período, responsável e caixa de entrada ficam
na URL do iframe. Os atalhos usam datas civis em `America/Sao_Paulo`; o fim escolhido
é inclusivo. Cada bloco tem exportação CSV e comparação com o intervalo imediatamente
anterior, com a mesma quantidade de dias. Os filtros se aplicam à conta autenticada.

| Indicador | Definição |
| --- | --- |
| Lead novo | Card criado no período. |
| Ganho / Perdido | Card que entrou numa etapa `kind=won` / `kind=lost` no período. |
| Taxa de ganho | Ganhos / (ganhos + perdidos) do período. |
| Em andamento | Cards em etapas `kind=open` no fim do período. |
| Ticket médio | Soma do valor dos ganhos / número de ganhos. |
| Valor em aberto | Soma do valor dos cards em andamento. |
| Ciclo médio | Média de (data do ganho − data de criação) dos ganhos do período. |
| Conversão entre etapas | Dos cards que entraram na etapa X no período, percentual que depois entrou em qualquer etapa posterior do mesmo funil. |
| Tempo médio na etapa | Média da permanência, calculada pelos eventos de movimento. |
| Card parado | Sem movimento nem tarefa concluída há mais de N dias; N é configurável por funil, padrão 7. |

O mesmo card conta uma vez como ganho e uma vez como perda por período, mesmo com
reentradas. Receita e ciclo usam a primeira entrada ganha desse período; o valor é o
registrado nesse evento, não um valor editado posteriormente. Um contato em dois
funis representa duas negociações. Tarefas são compartilhadas por contato/conta e
não são duplicadas na contagem.

Os saldos usam o último evento anterior ao fim do período (ou o estado registrado
até agora, para períodos futuros). Responsável, caixa, origem e campanha usam esse
mesmo retrato. A caixa é a da conversa mais recente do contato. Conversão acompanha
a coorte até agora, inclusive movimentos posteriores ao período selecionado; a coluna
“Próxima etapa” mede especificamente a etapa seguinte na ordenação atual. Permanência
considera passagens cuja saída ocorreu no período; passagens ainda abertas não entram
na média. Reclassificar uma etapa atualiza o saldo sem inventar entrada ganha/perdida.

Percentuais sem denominador mostram **0%**; médias sem amostra mostram **sem dados**.
Variação = (atual − anterior) / |anterior| × 100. Dois zeros produzem 0%; com base
anterior zero e valor atual positivo, a variação é indefinida e mostra **sem dados
no período anterior**. Setas usam as cores semânticas do tema, invertendo o sentido
favorável para perdas, atrasos e tempos.

### Perdas, atribuição e atendimento

Ao criar ou mover uma negociação para uma etapa perdida, o quadro exige um motivo.
Administradores configuram a lista em **Gerenciar funis → Motivos de perda**; **Outro**
exige texto. O motivo fica no card e no evento, junto à etapa de saída. Movimentos
externos/legados sem motivo são apresentados como **Não informado**. Alterar a etapa
novamente preserva o motivo no histórico, limpando o motivo atual ao sair de perdido.

Os atributos de contato **origem**, **campanha** e, opcionalmente, **temperatura** são
copiados na criação do card e atualizados pelos webhooks, inclusive quando limpos.
Preencha-os no Chatwoot manualmente, por automação ou n8n; isso não cria endpoints nem
uma integração n8n neste aplicativo. Origem e campanha têm tabelas separadas,
ordenáveis. Temperatura só aparece quando a conta define o atributo de contato ou já possui valores importados.

Atendimento usa `/api/v2/accounts/{id}/reports/summary`, `/reports` e os eventos
paginados de `/reports/drilldown`, com cache no backend de **5 minutos**, isolado por
conta e filtros. Os tempos são agregados em SQL sobre os eventos, evitando média de
médias. Conversas abertas, sem resposta e maior espera representam a **situação atual**:
a API nativa não expõe seus saldos históricos; a tela explica essa limitação e não
inventa comparação anterior. Conversas criadas, primeira resposta e resolução têm
comparação por período. A maior espera abre a conversa dentro do Chatwoot.

### API, atualização e recuperação

`GET /kanban/metrics/{summary|funnel|losses|sources|service|team|tasks|timeline}` exige
sessão Chatwoot e conta autorizada. Parâmetros: `account`, `start`, `end` (YYYY-MM-DD),
`funnel_id`, `assignee_id`, `inbox_id`; `format=csv` exporta cada bloco, incluindo
período anterior, em colunas `campo;valor`, com BOM UTF-8 e proteção de fórmulas.
O intervalo máximo é 366 dias. Agregações do Pipeline são SQL no PostgreSQL.

As migrações 004/005 acrescentam dimensões, eventos temporais e índices por
`(account_id, created_at)`. Antes de atualizar, faça backup e rode
`.venv/bin/alembic upgrade head`. Não há alteração automática de schema no startup.
Para atualizar metadados dos contatos já instalados, sem mover cards, execute:

```sh
PYTHONPATH=. .venv/bin/python scripts/refresh_metric_dimensions.py
```

O histórico antigo só é reconstruído a partir de movimentos efetivamente registrados.
Dimensões/valores ausentes continuam desconhecidos; o retrato atual começa na migração.
Não são inventadas durações anteriores à importação. O backup local desta atualização
está em `.local/antes-metricas-004.dump`; restauração exige parada dos serviços e o
procedimento em [backup e recuperação](docs/backup-recuperacao.md). O código anterior
pode rodar mantendo as colunas aditivas; remover o histórico novo exige restauração.

Os gráficos usam [Chart.js 4.5.1](https://www.chartjs.org/docs/latest/getting-started/integration.html),
servido pelo próprio aplicativo em `/kanban/static/vendor/chart.umd.js`, sem CDN.
A [licença MIT do Chart.js](app/static/vendor/Chart.LICENSE.md) acompanha o arquivo.
Cores, fontes, gráficos e tooltips herdam as variáveis do Chatwoot, incluindo o tema
escuro. Dados de usuários são inseridos com `textContent`, sem interpolação de HTML.
