# Implantação futura em Swarm/Traefik

**Nenhuma implantação remota foi executada.** `deploy/stack.yml` prepara API,
worker separado e PostgreSQL isolado. A rede externa `traefik` deve alcançar o Chatwoot.
A regra do Kanban usa o mesmo host e prioridade 200, somente em `/kanban` e `/kanban/*`.
A regra existente do Chatwoot deve ter prioridade menor.

Configure `KANBAN_IMAGE` com a tag imutável `sha-<commit>`, `KANBAN_DATABASE_URL`,
`KANBAN_ENCRYPTION_KEY`, `CHATWOOT_INTERNAL_URL` e `CHATWOOT_HOST` no gerenciador
seguro de implantação. Crie o secret `kanban_db_password` e atribua ao nó com o
volume persistente a label `kanban_data=true`. Não exponha PostgreSQL na internet.

Faça backup e execute `alembic upgrade head` **uma vez** com a mesma imagem e ambiente
antes de liberar as réplicas da API/worker. O startup não executa migrações.
Configure o loader em `DASHBOARD_SCRIPTS` da instalação e ative as contas como administrador.
Use HTTPS no endereço público e mantenha a chave de criptografia entre atualizações.

A CI executa Ruff, PostgreSQL/pytest e JavaScript para o mesmo commit antes de publicar
as imagens `linux/amd64` e `linux/arm64`. A publicação só ocorre em push de main/develop
após o job de validação. A validação no Chatwoot real permanece um gate manual de release.
O arquivo de stack é preparação; sua execução no Swarm e o build multiarch dependem
de um ambiente Docker/Swarm, que não é usado nesta instalação local.

Rollback: pare as réplicas, selecione a imagem anterior compatível com o esquema e
valide antes de retomar. Se precisar reverter dados, restaure o backup em um banco novo.
Não execute downgrade destrutivo de Alembic nem reutilize automaticamente uma imagem
antiga que escreva nas tabelas legadas.
