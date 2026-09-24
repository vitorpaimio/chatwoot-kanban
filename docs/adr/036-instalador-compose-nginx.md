# ADR-036 — Adaptador Compose/Nginx

Data: 24/09/2026. Complementa ADR-035 e fase 4.2 do plano 0.2.0.

## Contexto

O ciclo de vida Swarm já estabelece propriedade de recursos, provisionamento por
conta, revogação e backup cifrado. Instalações Chatwoot em Compose precisam do
mesmo contrato sem depender de manager, overlay ou Docker Secrets Swarm.

## Decisão

`adapter: compose` seleciona `ComposeLifecycle`. O núcleo `Lifecycle` conserva
planejamento, manifesto, bloqueio, backup/restauração, Rails e matrícula cifrada.
Os pontos específicos são inspeção de infraestrutura, recursos, deploy, parada,
migração, início/sondagem do worker e remoção. O adaptador Swarm é o padrão;
manifestos anteriores sem o campo são normalizados ao comparar configuração.

Containers são resolvidos pelas labels de projeto **e** serviço. A inspeção
inclui containers parados, volume de dados e rede privada. Recursos alheios são
recusados, não adotados. Redes externas bridge e alias Rails precisam existir.
Compose requer contexto Docker local com caminhos do estado acessíveis ao daemon.

Um projeto Kanban separado contém PostgreSQL, API, worker, job de migração e
Nginx. Nginx publica uma porta explícita, encaminha `/kanban` e `/kanban/…` à API
e o restante ao Rails. Preserva host/porta, encaminha WebSocket e desabilita
buffering de SSE. Não monta socket Docker nem altera código/imagem Chatwoot.
Não edita automaticamente configurações de um Nginx anterior: este gateway tem
propriedade explícita e porta própria. Uma porta ocupada exige configuração livre.

Compose monta segredos a partir de arquivos duráveis em `mounts/` (0700; arquivos
0600), dentro do diretório privado de estado. Esses arquivos contêm senha do
PostgreSQL e chave de cifragem, nunca token Chatwoot. Não são Docker Secrets
Swarm e não devem ser descritos como cifrados em repouso: o cofre e backups são
cifrados, mas os mounts são legíveis ao proprietário local e ao administrador.
O bootstrap lê os mounts como root e troca UID/GID para 10001, incluindo HOME do
usuário Kanban, antes de executar aplicação ou migração. A imagem deve seguir o
contrato do Dockerfile deste projeto.

Atualização para processos antes do backup, executa `compose run --rm migrate`
e exige saída zero antes de iniciar API. Worker só inicia após provisionamento.
Restore recupera apenas banco Kanban e imagem anterior; não sobrescreve Chatwoot
compartilhado. Uninstall revoga a identidade e remove projeto sem `-v`; preserva
volume/cofre/backups e remove mounts após desmontar containers. Também remove
este Nginx; o acesso anterior ao Chatwoot, se existente, continua independente.

## Limites

A certificação desta fase se limita ao Compose local ARM64, HTTP e imagens
registradas nas evidências. TLS externo, contexto remoto, HA, outras arquiteturas
e edição de um Nginx preexistente não estão certificados. Publicação depende da
fase 5. Estado e chave de recuperação precisam ser guardados pelo operador.
