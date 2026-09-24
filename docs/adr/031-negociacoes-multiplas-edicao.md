# ADR-031 — Negociações múltiplas e estabilidade da edição

Data: 23/09/2026. Estado: aceito.

## Contexto

A validação manual da Fase 1 exigiu várias negociações do mesmo contato no mesmo
funil. A restrição anterior bloqueava as etapas do formulário. Eventos SSE também
limpavam o quadro e fechavam os formulários mesmo sem perda de autorização.

## Decisão

Cada cartão é uma negociação independente, inclusive dentro do mesmo funil.
A migração 007 remove a unicidade contato/funil e associa históricos anteriores
ao cartão correspondente antes da mudança. A autorização de histórico passa a
usar o ID do cartão: outra negociação visível do mesmo contato não concede acesso
ao histórico de uma negociação oculta. A API legada de movimentação por contato
continua recusando ambiguidades; a interface movimenta por cartão.

Tarefa continua única e compartilhada por contato/conta. Os atributos permanecem
espelhos do contato; a etapa usa o último cartão movimentado e, sem essa referência,
o cartão mais recente do funil principal. Não há alteração de código do Chatwoot.

Atualizações comuns consultam o quadro sem esvaziá-lo. Durante edição/arraste,
a aplicação adia a renderização; perda de cartões autorizados, sessão expirada ou
403 continuam limpando detalhes e dados imediatamente após a resposta. Respostas
antigas não sobrescrevem consultas novas nem restauram dados revogados.

O valor aceita máscara BRL e no máximo 11 dígitos em centavos (R$ 999.999.999,99),
com validação equivalente na API. Ações usam ícones e se organizam lado a lado,
com quebra em telas estreitas. Conversas são buscadas pelo texto, caixa e situação,
com seleção explícita ou automática; o servidor filtra as caixas autorizadas.
Modais fecham por X, Escape ou clique iniciado e concluído fora da janela.

## Migração e retorno

Aplicar Alembic antes de reiniciar API/worker; não manter processos anteriores
após a aplicação. A migração preserva cartões, valores e histórico. O downgrade
reintroduz a unicidade somente se não houver duplicatas; caso contrário falha
transacionalmente sem excluir negociações. Não consolidar dados automaticamente.

## Validação

Testes PostgreSQL cobrem negociações independentes, tarefa compartilhada, limite
monetário, histórico entre caixas, opções de conversa e preservação/rollback.
A sessão 024 registra a prova manual em Chatwoot real.
