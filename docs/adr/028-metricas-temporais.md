# ADR-028 — Métricas temporais e motivos de perda

Data: 23/09/2026. Estado: aceito. Complementa ADR-026.

Contar somente o estado atual do card não responde a perguntas sobre ganhos no
período nem saldo ao final de um intervalo. A integração passa a gravar snapshots
imutáveis de entrada, movimento e alteração de dimensões em `kb_card_events`, na
mesma transação do card. Triggers cobrem API, worker e webhooks; a edição de uma
classificação de etapa cria snapshot sem simular movimento. O histórico existente
permanece preservado. Migrações 004/005 são aditivas e executadas via Alembic.

Todas as agregações do Pipeline são SQL, parametrizadas por conta, limites civis
de Brasília, funil, responsável e caixa. Valores e datas de ganhos usam o evento;
saldos usam o último snapshot antes do limite. Conversão usa coorte de entradas,
com progressão posterior observada até agora. Tarefas são deduplicadas por contato.
As definições, regras para reentradas e dados desconhecidos estão no README.

Motivos de perda são configuração administrativa da conta. A UI centraliza a
solicitação tanto ao criar quanto ao mover para perdido; o backend valida o motivo.
Cancelamento mantém o card; entrada externa sem informação não fabrica um motivo.

O atendimento usa APIs nativas do Chatwoot 4.16.2, com cache de cinco minutos em
PostgreSQL por conta/recorte. Dados de mensagens não são guardados no cache. Eventos
de relatório normalizados permitem filtros combinados e médias SQL. Saldos atuais
de atendimento não têm comparação histórica inventada.

A página incorporada usa Chart.js local, tema compartilhado, oito blocos independentes
com skeleton/erro/CSV, URL para filtros e SSE para atualização. A navegação de um
card parado passa pelo loader, validando origem, janela emissora, conta e ID.
