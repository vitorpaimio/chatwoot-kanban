# Sessão 024 — Correções da validação manual da Fase 1

## Diagnóstico e entregas

Etapas bloqueadas pela unicidade contato/funil na interface e banco. Migração 007
permite negociações independentes e preserva isolamento do histórico por cartão.
Máscara BRL com limite de R$ 999.999.999,99 também validado pela API. Botões discretos
com ícones e quebra responsiva. Busca/seleção de conversa do contato, filtrada por
caixa autorizada no servidor. Clique fora e Escape fecham os modais. Consultas
possuem timeout e falhas de edição aparecem dentro da janela.

O evento SSE `change` chamava a limpeza de autorização indiscriminadamente,
fechando formulários e esvaziando o quadro. Agora consulta primeiro, preserva
rascunhos durante mudanças comuns e limpa dados se perder autorização. Consultas
concorrentes antigas são descartadas e metadados sem alterações não redesenham.

API local permanecia iniciada às 17:36, antes da atualização do contrato de tarefas
(arquivo alterado às 18:32). Reiniciados API e worker com código atual após Alembic;
a criação com descricao/vencimento passou no navegador, sem 422. Rails, Sidekiq,
proxy e Vite continuam disponíveis em localhost:3000.

## Evidências

- Ruff aprovado; 75 testes Python em kanban_test; quatro testes Node; sintaxe JS/CJS.
- Migração preserva os cartões e associa histórico antigo; rollback com duplicatas
  recusa a operação sem apagar dados, comprovado no PostgreSQL exclusivo.
- No Chatwoot local autenticado: criada segunda negociação da Jane no mesmo funil,
  selecionada Proposta enviada e salvo R$ 1.234,56; vínculo escolhido por busca
  de texto. Criada tarefa no contato de teste 1790186608874, vencimento 07/10/2026.
- Clique fora fechou a janela. Em duas abas, mover a negociação na segunda manteve
  a janela e o rascunho R$ 9.876,54 na primeira; rascunho descartado ao fechar.
- Negociação adicional e tarefa de validação ficaram disponíveis para inspeção.
  A segunda negociação terminou em Novo após o teste entre abas.
- Teste controlado de frontend ampliado para preservar rascunho em evento comum
  e limpar o detalhe após revogação. Nesta sessão, prova de navegador executada
  pela interface real; esse script controlado não foi executado.

## Próximo passo

Retomar o checklist manual da Fase 1. Fase 2, publicação e commits não executados.
Decisão: [ADR-031](../adr/031-negociacoes-multiplas-edicao.md).
