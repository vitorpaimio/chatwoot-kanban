# Sessão 029 — Fase 3: quadro e capacidade

Pedido: iniciar a Fase 3 e continuar até concluir. O mantenedor aprovou o Mac local
como referência, 30 sessões mistas durante cinco minutos, 20 mil contatos/5 mil
cartões por conta e p95 de 500 ms/1 s/2 s para quadro/métricas/SSE.

Implementados: consulta paginada por etapa com filtros e totais completos,
interface com páginas limitadas, tempo na etapa, responsável de tarefa independente,
migração 012, limite de assinantes e liberação de SSE, reconexão com jitter,
revalidação de histórico/detalhe sem apagar rascunhos autorizados, links de cartões
fora da página, âncora de arraste e fallback de funil arquivado. Indicadores de
atendimento permanecem no Chatwoot; métricas do Kanban são locais.

O piloto encontrou varreduras correlacionadas em negociações paradas e planos
SQL genéricos lentos. EXPLAIN comprovou as causas. Agregação prévia e planejamento
específico na transação corrigiram a degradação, sem cache de autorização novo.

Ensaio final: 8.296 requisições/300,95 s, zero erros; p95 quadro 357 ms, maior p95
entre métricas 283 ms, SSE 519 ms. Duas contas isoladas, 24 agentes e seis admins;
123 invalidações por sessão afetada e zero nas 15 sessões da outra conta.
Pool 10 + LISTEN 1; pico Python 91,4 MiB; orçamento devolvido ao desconectar.
Escopo ASGI/PostgreSQL com identidade controlada; não certifica autenticação/rede
Rails, 30 navegadores, worker remoto, NAS ou Swarm.

Migração aplicada no ambiente local preservando 8 contatos, 16 negociações e 12
tarefas. Interface conferida na sessão real do Chatwoot: filtro, totais, tempo na
etapa, atribuição/remoção/restauração do responsável e métricas. Conta de teste
manteve seus dados e o histórico das operações. Fontes do Chatwoot não alterados.

Relatório, provas e reprodução: [Fase 3](../fase-3-quadro-capacidade.md).
Decisão: [ADR-034](../adr/034-quadro-paginado-capacidade.md).
Alterações anteriores preservadas, sem commit, push ou publicação nesta sessão.
Próxima fase: instalador Swarm/Traefik e ciclo de vida (Fase 4).

Planejamento complementar solicitado pelo mantenedor: o adaptador Compose/Nginx
passa a ter escopo explícito na Fase 4.2, como próxima ampliação do instalador
após Swarm/Traefik e antes do gate da Fase 5. Compartilha comandos, manifesto,
provisionamento e garantias de recuperação; exige validação real própria.

Validação final: Ruff e diff sem erros; 117 testes Python, quatro Node e os três
roteiros Chrome aprovados. Carga opt-in executada separadamente; integração Rails
da Fase 2 não repetida. API e worker locais reiniciados com sondas HTTP 200.
