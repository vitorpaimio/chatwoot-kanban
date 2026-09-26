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

## Consequências

- Receita e ticket passam a refletir o valor informado depois do ganho; o valor
  de uma etapa já deixada não muda com edições posteriores.
- A conversão cai onde havia perdas contadas como avanço; a perda aparece à parte.
- Leads importados distribuem-se pelos dias do primeiro contato.
- Instalações já com dados precisam do comando de reparo para o passado.
