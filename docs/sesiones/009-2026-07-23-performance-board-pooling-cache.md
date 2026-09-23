# Sessão 009 — Desempenho do quadro, chamadas HTTP e atualização periódica

- **Data:** 2026-07-23
- **Natureza:** registro histórico, revisado em português do Brasil.

## Contexto

O carregamento executava uma sincronização de banco por cartão, carregava
etapas em sequência, buscava definições de atributos repetidamente e mantinha
atualizações mesmo em abas ocultas. Escritas faziam leitura antes do envio.

## Alterações

- `batch_sync_tasks_from_chatwoot()` passou a receber cartões por etapa e
  usar `executemany` para atualizar, criar e encerrar em lotes.
- `skip_read=True` permitiu enviar atributos sem a leitura anterior nos
  caminhos de mudança de etapa, criação, edição, encerramento e agendamento.
- Definições de atributos passaram a usar cache em memória por cinco minutos.
- `_load_stage()` passou a executar em paralelo com `asyncio.gather()`.
- `visibilitychange` passou a evitar atualização em abas ocultas e recarregar
  quando o usuário voltasse à aba.

## Arquivos e decisões

Alterados cliente HTTP, banco, roteador Kanban, interface e dados simulados.
Não foi criado novo ADR, pois a sessão tratou as mudanças como otimizações.
A justificativa de `skip_read` foi a combinação de atributos no servidor
observada na API utilizada. Isso depende do comportamento da versão integrada.

O uso de `executemany` reduz chamadas individuais, mas não transforma por
si só uma sequência de leitura e inserção em uma operação concorrente segura.

## Próximos passos registrados

Medir a latência em homologação, conferir o agendamento com `skip_read` e
considerar `INSERT ... ON CONFLICT` caso o banco se tornasse um limitador.
