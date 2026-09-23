# ADR-023 — Execução local e publicação condicionada a testes

Estado: aceito em 23/09/2026.

Overmind supervisiona Rails, Sidekiq, API, worker e proxy. Vite existente é reutilizado.
Os bancos Kanban de desenvolvimento e testes são exclusivos. Variáveis de banco do
Kanban não passam para os processos Rails. Não há seed automático do Chatwoot.
A permissão de webhook privado se limita aos scripts de desenvolvimento.

Swarm/Traefik está preparado para o mesmo host com API replicável, worker e banco
isolado. A imagem multiarch só é publicada depois dos testes do mesmo commit.
Nenhuma produção é alterada como parte da entrega local.
