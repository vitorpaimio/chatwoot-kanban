# Métricas do Pipeline

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

As migrações de métricas acrescentam dimensões, eventos temporais e índices por
`(account_id, created_at)`. Antes de atualizar, faça backup e rode
`.venv/bin/alembic upgrade head`. Não há alteração automática de schema no startup.
Para atualizar metadados dos contatos já instalados, sem mover cards, execute:

```sh
PYTHONPATH=. .venv/bin/python scripts/refresh_metric_dimensions.py
```

O histórico antigo só é reconstruído a partir de movimentos efetivamente registrados.
Dimensões/valores ausentes continuam desconhecidos; o retrato atual começa na migração.
Não são inventadas durações anteriores à importação. A restauração exige backup próprio, parada dos serviços e o
procedimento em [backup e recuperação](backup-recuperacao.md). O código anterior
pode rodar mantendo as colunas aditivas; remover o histórico novo exige restauração.

Os gráficos usam [Chart.js 4.5.1](https://www.chartjs.org/docs/latest/getting-started/integration.html),
servido pelo próprio aplicativo em `/kanban/static/vendor/chart.umd.js`, sem CDN.
A [licença MIT do Chart.js](../app/static/vendor/Chart.LICENSE.md) acompanha o arquivo.
Cores, fontes, gráficos e tooltips herdam as variáveis do Chatwoot, incluindo o tema
escuro. Dados de usuários são inseridos com `textContent`, sem interpolação de HTML.


A visibilidade dos cartões e de seus eventos segue a conversa vinculada atual,
mesmo em períodos históricos. Consulte a [política de autorização](fase-1-autorizacao.md).
