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

## Contatos removidos e tentativas limitadas — 30/09/2026

O incidente de 30/09 revelou que um contato apagado mantinha uma sincronização em
retentativa infinita. `kb_sync` e `kb_deliveries` agora param após dez falhas, com
estado `dead` e evento de histórico. O administrador pode reiniciar essas tentativas
pela ação existente; o diagnóstico continua apontando a falha até sua resolução.

Um 404 inicia confirmação por GET do contato e leitura da coleção de contatos da
mesma conta. Falhas de autorização, indisponibilidade ou um contato ainda existente
não autorizam exclusão. Ausência confirmada encerra a sincronização em `gone`, marca
os cartões em `kb_card_deletions`, fecha tarefas ativas e cancela entregas pendentes,
com bloqueio por conta/contato, histórico e notificação na mesma transação. Cartões,
contato e histórico permanecem armazenados. `gone` não entra na retentativa manual.
Entregas de conversa ausente também terminam em `gone`, sem excluir o contato.

A reconciliação aplica a mesma confirmação para recuperar exclusões sem webhook,
inclusive cartões órfãos cuja fila foi encerrada manualmente. O Chatwoot local
4.16.2 não inclui `contact_deleted` em `Webhook::ALLOWED_WEBHOOK_EVENTS`; não se
adiciona uma assinatura inválida nem se altera seu código. A detecção ocorre por
404 durante o processamento ou pela varredura periódica, sem prazo fixo por contato.
Não há mudança de esquema: estados das duas filas já são texto sem enum restritivo.
