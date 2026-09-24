# ADR-034 — Quadro paginado, tarefas e capacidade local

Data: 24/09/2026. Estado: aceito para a Fase 3 da 0.2.0.

## Decisão

O quadro consulta `kb_visible_cards` com filtros no servidor (funil, etapa,
contato, texto literal sem curingas, responsável do contato, etiqueta e estado
da tarefa). Cada etapa retorna 50 cartões, no máximo 100 por chamada, ordenados
por posição e ID. Totais de quantidade e valor usam toda a seleção autorizada,
na mesma instrução SQL da página. A interface troca a página da coluna, sem
acumular milhares de nós DOM. Mudanças/filtros reiniciam a paginação. O catálogo
de contatos deixa de acompanhar o quadro; a criação já usa pesquisa sob demanda.

`stage_entered_at` continua sob responsabilidade da movimentação local e passa a
ser mostrado no cartão. `kb_tasks.assigned_to` separa responsável e criador;
na migração, recebe `created_by`. Nova tarefa atribui ao criador por padrão.
Reatribuição valida participação atual na conta pelo Chatwoot e registra histórico
e fila na mesma transação do contato. Mudanças de responsável da conversa não
alteram a tarefa. Limpar o responsável é permitido explicitamente.

Métricas comerciais e de tarefas permanecem no PostgreSQL local. A interface deixa
de reproduzir indicadores de atendimento; o endpoint antigo informa para usar o
Chatwoot. Equipe não consulta mais conversas remotas para calcular primeira
resposta. Metadados de filtros continuam podendo usar o cache remoto existente.

SSE mantém um LISTEN por processo, pool de API de até 10 conexões e reserva de
até 300 assinantes por processo/60 por conta. Excesso recebe 429 com Retry-After.
A reserva e o assinante são liberados inclusive em falha no envio. Eventos
coalescem por 100 ms; apenas mudança da revisão autorizada emite invalidação.
Sem sinal, o servidor revalida no prazo de sessão/permissão, sem recalcular dados
em cada keepalive. O cliente reconecta com atraso exponencial e jitter até 31s.

Rascunhos autorizados sobrevivem a atualizações e conflitos 409. Revalidação de
cartão, atualização de histórico e limpeza do quadro removem dados revogados.
Falha transitória na consulta de detalhe não apaga o rascunho. Sessão expirada
continua exigindo limpeza imediata. Acesso por link carrega o detalhe mesmo fora
da primeira página. Movimentação por seletor oferece alternativa a arrastar.

## Ensaio aprovado antes da execução

O mantenedor aprovou este Mac como referência: Mac14,2, 8 CPUs lógicas,
16 GiB RAM, PostgreSQL 16.14 Homebrew, Python 3.12. Sem extrapolar para NAS/Swarm.
Volume por conta: 20.000 contatos e 5.000 cartões. Duas contas, 30 sessões mistas,
5 minutos. Metas p95: quadro ≤500 ms; métricas locais ≤1 s; invalidação SSE ≤2 s.
Carga: uma ação HTTP por sessão seguida de 1s de intervalo; percorrer quadro,
filtros e os sete blocos de métricas, mantendo os 30 SSE abertos. Medir conexões,
memória, erros e isolamento. Distinguir transporte ASGI e identidade
controlada do teste de integração com sessão real do Chatwoot. Resultados e limites
em `docs/fase-3-quadro-capacidade.md`.

Orçamento de implantação: cada processo API pode usar 10 conexões de pool + 1
LISTEN; cada worker tem seu próprio pool de até 10. Somar Rails/Sidekiq, migrações
e administração antes de definir réplicas e `max_connections` do PostgreSQL.
Aumentar réplicas multiplica limites; este orçamento não é um limitador distribuído.

A 0.2.0 não inclui o Kanban no aplicativo móvel nativo do Chatwoot. Testar toque no
navegador não significa suporte no aplicativo nativo. Instalador e certificação de
implantação/versões permanecem nos gates das Fases 4 e 5.

## Evidência de otimização

O piloto detectou subconsultas correlacionadas em negociações paradas e degradação
depois de múltiplas chamadas preparadas. EXPLAIN ANALYZE: parados caiu de 467 ms
para 15 ms ao agregar entradas/tarefas antes do join. EXPLAIN EXECUTE confirmou
plano genérico de equipe em 384 ms e origem em 337 ms, contra 15 ms/9 ms com plano
específico. A rota de métricas usa `SET LOCAL plan_cache_mode=force_custom_plan`
na transação; preserva a seleção autorizada e os limites temporais. Não altera
a configuração global do PostgreSQL. O piloto foi repetido antes do ensaio final.
