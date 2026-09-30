# ADR-023 — Execução local e publicação condicionada a testes

Estado: aceito em 23/09/2026.

Overmind supervisiona Rails, Sidekiq, API, worker e proxy. Vite existente é reutilizado.
Os bancos Kanban de desenvolvimento e testes são exclusivos. Variáveis de banco do
Kanban não passam para os processos Rails. Não há seed automático do Chatwoot.
A permissão de webhook privado se limita aos scripts de desenvolvimento.

Swarm/Traefik está preparado para o mesmo host com API replicável, worker e banco
isolado. A imagem multiarch só é publicada depois dos testes do mesmo commit.
Nenhuma produção é alterada como parte da entrega local.

## Liveness independente das filas — 30/09/2026

O `HEALTHCHECK` da imagem da API consulta `/health/live`, que retorna 200 quando a
API responde, sem depender de banco, worker, importação ou filas. Reiniciar a API
não corrige um item persistente inválido de uma conta e não deve retirar as demais
do ar. `/health` mantém o diagnóstico detalhado e HTTP 503 em degradação, para
observabilidade; `/health/worker` e a sonda do container worker mantêm sua função.
Itens `gone` saem do diagnóstico de pendências; `dead` continua gerando alerta.
A correção exige publicar e implantar a nova imagem para mudar a sonda do container.
