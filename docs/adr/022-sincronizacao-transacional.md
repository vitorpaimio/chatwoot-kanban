# ADR-022 — Autoridade local e sincronização transacional

Estado: aceito em 23/09/2026. Substitui leitura/importação do quadro nos ADRs anteriores.

O banco Kanban é autoridade de funis, cartões e tarefas. Chatwoot é autoridade dos
contatos e conversas. GET do quadro não modifica dados. Alteração local, histórico,
versão desejada da projeção e NOTIFY são gravados na mesma transação.

O worker processa uma fila persistente por conta/contato. Bloqueios consultivos e
transações impedem duas projeções simultâneas do mesmo contato; sempre é calculada
a projeção completa mais recente. Retentativas usam atraso crescente. Ao morrer o
processo, PostgreSQL desfaz a transação e libera os bloqueios. O worker atualiza
os estados de vencimento usando a data civil de `America/Sao_Paulo`.

Webhooks usam a assinatura real da versão 4.16.2: HMAC-SHA256 de `timestamp.corpo`,
janela de cinco minutos, conta do payload e deduplicação por conta/entrega. O recebimento
é persistido antes da resposta. O processamento consulta o estado atual no Chatwoot,
evita aplicar payloads atrasados, identifica ecos e registra conflitos com pendências locais.

SSE usa LISTEN/NOTIFY por conta e revalida a sessão periodicamente. Reconexão relê o
quadro; formulários abertos adiam a atualização visual para preservar rascunhos.
