# Sessão 025 — Ações, etiquetas e exclusão

Segunda rodada de ajustes da validação manual da Fase 1. Implementados vínculo
condicional, conclusão com ícone ao lado de Salvar, catálogo de etiquetas no filtro
e exclusão recuperável da negociação com lixeira ao lado do X. Decisão detalhada:
[ADR-032](../adr/032-exclusao-recuperavel-negociacoes.md).

Validação: Ruff; 77 testes Python no banco exclusivo; quatro testes Node; sintaxe
JS/CJS; exclusão e Desfazer pela interface Chatwoot real (9 → 8 → 9 negociações,
valores restaurados). Etiquetas 123/1234 carregadas. Tarefa de validação mantida
ativa; posição e ícone do botão conferidos sem concluí-la.

Migração local 008 aguardou transação da API; reinício de API/worker liberou o
bloqueio. Migração concluída e processos reiniciados. Nenhuma fonte do Chatwoot
alterada. Correções anteriores preservadas, sem commit ou publicação.

Próximo passo: continuar checklist manual da Fase 1 antes da Fase 2.
