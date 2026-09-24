# Fase 3 — Quadro, métricas locais e capacidade

Referência: [ADR-034](adr/034-quadro-paginado-capacidade.md).

## Entregas

- Paginação por etapa, filtros no servidor e totais completos na mesma seleção
  autorizada. Interface limitada a 50 cartões por coluna; navegação substitui a
  página. Primeira consulta de descoberta usa um cartão por etapa. Pesquisa não
  precisa carregar o catálogo de 20 mil contatos. Link direto busca o cartão
  independentemente da página. Arraste na borda usa a âncora da próxima página.
- Tempo na etapa visível; responsável da tarefa independente da conversa, editável
  e com padrão no criador. Migração 012 preserva tarefas existentes. Histórico,
  controle de versão, bloqueio e fila permanecem na transação do contato.
- Métricas comerciais e tarefas calculadas localmente, inclusive equipe. Indicadores
  de atendimento ficam no Chatwoot. Negociações paradas usam agregação antes do
  join; métricas usam planos específicos de parâmetros na transação.
- SSE limitado a 60 conexões por conta e 300 por processo, sem reservar conexão
  PostgreSQL por cliente. Uma conexão LISTEN + pool de até 10 por API. Liberação
  garantida em cancelamento/falha; sinais coalescidos e invalidação autorizada.
  Reconexão exponencial com jitter; revisão no prazo de autorização mesmo sem sinal.
- Teclado e toque por detalhes/seletor de etapa, conflitos mantendo formulário,
  preservação de rascunho autorizado, revalidação de detalhe/histórico e remoção de
  dados revogados. Troca de funil arquivado refaz a consulta.

## Reprodução

Banco PostgreSQL exclusivo, nome terminado em `_test`. Aplicar as migrações antes
dos testes. **Não executar a suíte comum junto com a carga:** as fixtures truncam
as contas do banco de testes.

```sh
DATABASE_URL=postgresql://paim@localhost:5432/kanban_test .venv/bin/alembic upgrade head
.venv/bin/ruff check app migrations scripts tests
.venv/bin/pytest -q
node --test tests/test_interface.cjs
node tests/browser/authorization.cjs
node tests/browser/phase2.cjs
node tests/browser/phase3.cjs
PHASE3_LOAD_SECONDS=300 .venv/bin/pytest -q tests/test_phase3_capacity.py
```

A URL ilustrada é somente o banco local exclusivo, sem senha. Em outra máquina,
configurar `TEST_DATABASE_URL` e a mesma `DATABASE_URL` ao migrar.

## Metodologia e limites

Hardware e metas aprovados pelo mantenedor antes do ensaio: Mac14,2, 8 CPUs
lógicas, 16 GiB RAM, PostgreSQL 16.14 Homebrew, Python 3.12. Duas contas com 20.000
contatos, 5.000 cartões e 1.000 tarefas cada, além do registro-base da fixture.
Trinta sessões (24 agentes/6 administradores), 15 por conta, com caixas disjuntas.
Cada sessão percorre quadro, filtro e sete blocos de métricas, aguardando um segundo
entre respostas. Trinta SSE ficam abertos; duas negociações da conta 1 mudam
periodicamente, e a conta 2 não deve receber invalidações.

Metas p95: quadro ≤500 ms, métricas locais ≤1 s, invalidação SSE ≤2 s. A medição de
invalidação começa antes da transação de movimento e termina ao receber `change`.
O relatório registra contagens, erros, conexões, memória e fila.

O ensaio usa transporte ASGI e identidades controladas, com PostgreSQL e LISTEN
reais. Não inclui custo da autenticação Rails, rede/proxy, 30 navegadores ou
sincronização remota. O worker não processa as duas entradas de fila produzidas
pelo ensaio; portanto, esse contexto não certifica vazão do
Chatwoot nem tempo de sincronização. Recuperação e limites de processamento são
cobertos pelos testes da Fase 2. Não extrapolar esta referência para NAS, Swarm ou
instalação pública; esses ambientes continuam sujeitos aos gates finais.

O teste de frontend executa Chrome real com respostas de API controladas e não
substitui a prova de integração real. Na sessão real do Chatwoot local foram
verificados quadro, filtros, totais, tempo na etapa, edição do responsável e
métricas. A alteração de responsável no contato de teste foi revertida pela API,
conservando o histórico. Nenhuma credencial foi gravada ou impressa.

A migração no ambiente local preservou **8 contatos, 16 negociações e 12 tarefas**.
O aplicativo móvel nativo do Chatwoot não inclui o Kanban na 0.2.0; a prova de toque
é exclusivamente da interface web.

## Resultado final — 24/09/2026

Ensaio aprovado, duração medida **300,95 s**, **8.296 requisições**, **zero erros**.
Dados brutos: [phase3-capacity.json](phase3-capacity.json).

| Medida | p95 | Meta |
|---|---:|---:|
| Quadro | 357,0 ms | ≤500 ms |
| Quadro filtrado | 258,7 ms | ≤500 ms |
| Resumo | 215,4 ms | ≤1.000 ms |
| Tarefas | 150,8 ms | ≤1.000 ms |
| Equipe | 169,6 ms | ≤1.000 ms |
| Funil | 204,8 ms | ≤1.000 ms |
| Perdas | 83,0 ms | ≤1.000 ms |
| Origem/campanha | 283,1 ms | ≤1.000 ms |
| Evolução/temperatura | 259,7 ms | ≤1.000 ms |
| Invalidação SSE | 519,4 ms | ≤2.000 ms |

Pool máximo 10; total PostgreSQL no banco de teste 11 (inclui LISTEN). Pico de
memória do processo Python: 91,4 MiB. Cada uma das 15 sessões da conta alterada
recebeu 123 invalidações; nenhuma das 15 sessões da outra conta recebeu alguma.
Reservas e assinantes zerados após desconexão. Fila limitada a dois contatos,
sem worker neste ensaio; não é medição de vazão ou atraso de sincronização remota.

Validação adicional: Ruff, sintaxe dos 13 JS/CJS, quatro testes Node, 117 testes
Python aprovados no PostgreSQL exclusivo e três
roteiros Chrome (autorização, Fase 2 e Fase 3). Roteiro da Fase 3 cobre a âncora
na borda da página e a seleção de outro funil após arquivamento do atual.

A suíte comum omite os dois testes opt-in (carga e ponte Rails da Fase 2). O teste
de carga foi executado separadamente por cinco minutos nesta sessão; a ponte Rails
da Fase 2 não foi repetida. API e worker locais reiniciados com sondas HTTP 200.
