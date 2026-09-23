# Sessão 023 — Fase 1: autorização e ativação

Plano atualizado com decisões do mantenedor. Git inicializado com o commit-base
solicitado; repositório privado vitorpaimio/chatwoot-kanban criado e remote configurado.
Commits separados por decisões, autorização, corte de atributos, recursos e provas.

Implementados cache de caixas 60s/falha fechada, views de visibilidade, vínculo por
cartão, conta habilitada/desabilitada e guarda no worker. Listener PostgreSQL
compartilhado e SSE filtrado. Corte de chaves e API de tarefas com script de migração
sem escrita dupla. Frontend limpa dados revogados e permite fixar conversa.

ContactPolicy comprovada por API em Rails real nas duas versões: contato identificado
em caixa alheia permanece acessível ao agente da conta. Não houve fallback de tarefa
para visibilidade do cartão. Relatório detalhado: [Fase 1](../fase-1-autorizacao.md).

Pendências: habilitar canal privado quando GitHub for público; escolher licença
(explicitamente não escolhida no pedido); executar Fases 2–5 antes da release.
Nenhuma publicação de capacidade, release ou mudança de código Chatwoot.

Validação final: Ruff aprovado; **71 testes Python** aprovados em `kanban_test`;
**3 testes Node** aprovados; sintaxe de todos os JS/CJS aprovada; Chrome aprovou
cartão sem canal e limpeza da interface após revogação/expiração. A suíte Rails
real aprovou 10 grupos em cada versão CE. Fontes do Chatwoot permaneceram intactas.
