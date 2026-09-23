# Sessão 011 — Operações em segundo plano e resposta da interface

- **Data:** 2026-07-26
- **Natureza:** registro histórico, revisado em português do Brasil.

## Contexto

A criação, edição e conclusão aguardavam a API externa por aproximadamente
200–2.000 ms. Cada usuário consultando o quadro gerava chamadas por etapa
e página a cada 30 segundos.

## Alterações

### Tarefas em segundo plano

`BackgroundTasks` passou a executar `_bg_sync_task_and_audit()` depois da
gravação local e da resposta à interface. A função sincroniza os atributos
e grava a auditoria. A mudança de etapa continuou aguardando o Chatwoot.

A sessão estimou 10–50 ms para validação e banco. A intenção era recuperar
falhas por `sync_pendiente` e agendamento; a auditoria atual encontrou
lacunas nessa recuperação. `BackgroundTasks` não é uma fila durável.

### Cache e paginação

`_board_cache` guarda o resultado por etapa durante oito segundos. Criar,
editar, encerrar ou mover invalida o cache. `generated_at` informa quando
o resultado foi produzido. O tamanho solicitado das páginas passou a 50,
com `_PAGE_SIZE = 50` no cálculo de paginação.

### Atualização otimista

`optimisticTaskUpdate()` altera a indicação do cartão antes da resposta.
Criar, salvar e encerrar fecham o modal imediatamente; em erro, a interface
recarrega o quadro.

### Atualização adaptativa

Um `setTimeout` recorrente substituiu `setInterval`. A intenção era comparar
`generated_at`, manter intervalo mínimo de 15 segundos quando houvesse
mudanças e aumentar em dez segundos até 60 quando não houvesse. Abas ocultas
e modais abertos adiam a consulta.

## Arquivos

Cliente HTTP, roteador Kanban, HTML e fixture `_clear_board_cache`.
Não foi criado ADR adicional, por ter sido considerado trabalho de desempenho.

## Próximos passos registrados

Validar criação, edição, encerramento, movimentação e atualização automática
em homologação; depois abrir PR para produção.
