# ADR-030 — Autorização por caixa e habilitação da conta

Data: 23/09/2026. Estado: aceito e implementado na Fase 1.

A associação à conta não basta para autorizar cartões. Adotar sessão humana com
`/inboxes`, cache de 60s e falha fechada; filtrar cartão/movimentos/histórico/métricas
pela caixa da conversa vinculada. Sem conversa, acesso de administrador/criador.
ContactPolicy das duas versões CE foi validada: contato e tarefa compartilhada
continuam visíveis na conta independentemente da caixa do cartão.

Centralizar leituras em views SQL com contexto transacional. Conta desativada impede
operações e worker; bloqueio compartilhado na unidade de trabalho serializa a
confirmação da desativação. SSE compartilha listener, revalida e emite invalidação
apenas quando o estado visível muda. Não há garantia de capacidade antes da carga.

Substituir as alternativas de cache de cinco minutos, card órfão só administrativo,
espelho de conversa e escrita dupla do ADR-029. Corte direto português inclui API
interna de tarefas e script único de desenvolvimento com relatório. Autoridade local
é preservada ao retirar leitura de espelhos do refresh. Catálogo completo e
reconciliação periódica seguem na Fase 2. Rails runner será padrão do instalador;
Platform API fica como alternativa. Celular 0.2.0 apenas documenta a limitação.

Ver [evidências e limites](../fase-1-autorizacao.md) e [plano](../plano-0.2.0.md).
