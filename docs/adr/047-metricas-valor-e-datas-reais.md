# ADR-047 — Valor da passagem, conversão sem perda e datas reais

Estado: aceito em 25/09/2026.
Complementa o ADR-028 (métricas temporais) e o ADR-046.

## Contexto

Um operador em produção (conta 8, v0.2.0-rc.4) importou contatos em massa e
organizou o funil depois. O quadro ficou correto, mas as métricas não:

- ganhos e perdas usavam o valor do cartão no instante em que entrou na etapa, e a
  primeira entrada; o valor preenchido depois do ganho não contava (receita zero);
- editar só o valor pela janela do cartão levava o cartão para o fim da coluna;
- a importação dava a todos os leads a data da importação;
- a conversão contava a ida para a etapa de perda como avanço;
- etapas com a mesma posição quebravam a ordem da conversão;
- não havia como registrar a data real de um movimento feito depois do fato.

## Decisão

- Métricas: cada entrada em etapa leva o último valor registrado antes de sair
  dela. Ganho e perda usam a entrada mais recente do período.
- Conversão ("Etapa posterior" e "Etapa seguinte") ignora etapas `lost` e usa a
  ordem atual das etapas por `(position, id)`. A ida para perda vira a coluna
  "Perda" (`loss_rate`).
- `PATCH /kanban/cards/{id}/value` altera só o valor, sem mudar etapa, posição ou
  entrada na etapa. Registra `valor_atualizado`. A janela do cartão usa essa rota
  quando a etapa não muda.
- `PATCH /kanban/cards/{id}` aceita `occurred_at`, só para administrador e só com
  mudança de etapa. A data não pode estar no futuro nem antes da criação ou da
  entrada na etapa atual. Sem fuso, vale o horário de Brasília. A migração 014
  cria `kb_occurred_at()`, lida pelos gatilhos de histórico a partir da variável
  de transação `kanban.occurred_at`.
- `kb_contacts.first_seen_at` guarda a abertura da conversa mais antiga (ou o
  cadastro do contato). A importação cria o cartão com essa data.
- Posições de etapa: criar numa posição ocupada é recusado (409); editar para uma
  posição ocupada troca as duas etapas, o que mantém o reordenar da interface.
- Origem ou campanha sem atributo mapeado mostram aviso com atalho para
  Configurações no próprio painel.
- Reparo: `python -m app.maintenance` retroage criações de um dia de importação,
  registra a data real de ganhos e renumera etapas com posição repetida. A
  simulação (`--dry-run`) aplica e desfaz numa transação. Cada alteração vira
  `manutencao_metricas` em `kb_history`, com autor "Manutenção".

Avançar a etapa sozinho no primeiro diálogo nos dois sentidos fica fora desta
versão: exigiria assinar `message_created`, que multiplica o volume de webhooks.

## Complemento: segundo diagnóstico

- "Negociação parada" considera também a última mensagem do cliente
  (`kb_contacts.last_activity_at`, atualizada pelo `contact_updated` a cada
  mensagem recebida). Quem conversa todo dia não aparece como parado.
- A tabela da equipe credita ganhos, perdas e receita ao responsável registrado
  no evento de fechamento, não ao responsável atual do cartão.
- A taxa de ganho mostra o tamanho da amostra ("3 de 15 fechamentos").
- Removidos o bloco `service` de Métricas (sempre respondia 409) e o endpoint
  antigo `GET /kanban/reports` com `app/reporting.py`, sem uso na interface. Os
  indicadores de atendimento ficam nos relatórios do Chatwoot.
- A ajuda de "Leads novos" explica que conta negociações manuais, importadas e da
  entrada automática, conforme as caixas de cada funil.

## Complemento: ganhos organizados em massa

`--won-at` recusava a data real quando o cartão tinha sido movido em massa depois
dela. Com `--fit-moves`, os movimentos intermediários posteriores à data do ganho
são redistribuídos, na mesma ordem, entre o registro anterior e o ganho, e o
histórico guarda as datas antigas e novas.

## Consequências

- Receita e ticket passam a refletir o valor informado depois do ganho; o valor
  de uma etapa já deixada não muda com edições posteriores.
- A conversão cai onde havia perdas contadas como avanço; a perda aparece à parte.
- Leads importados distribuem-se pelos dias do primeiro contato.
- Instalações já com dados precisam do comando de reparo para o passado.
