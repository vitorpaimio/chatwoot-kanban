# Chatwoot oficial no Swarm local

**Histórico:** o laboratório e Docker foram removidos após concluir a Fase 4,
por solicitação do mantenedor. Os endereços, backups e chaves descritos abaixo
não existem mais. Estes arquivos documentam a montagem do ensaio; para o
instalador geral, consulte `docs/fase-4-instalador.md`.

Laboratório da Fase 4, separado do Chatwoot em localhost:3000.
Acesso: **http://localhost:18080**. O primeiro acesso permite criar a conta
administrativa pela tela inicial; nenhuma senha humana foi predefinida.

Imagem oficial `chatwoot/chatwoot:latest-ce`, consultada em 24/09/2026:
Chatwoot **4.18.0**, release estável mais recente naquele momento.
O template fixa o digest do índice multiarch retornado pelo Docker Hub:
`sha256:991d6fe4e1553757987093c5e7345322ce46cbf4a932061efbb13e15bb928565`.

- Contexto Docker: `colima-kanban-phase4`; stack: `cwlab`.
- PostgreSQL 16/pgvector e Redis 7 exclusivos, sem portas publicadas.
- Rails e Sidekiq compartilham armazenamento persistente da stack.
- Traefik publica 18080 em modo host; funciona pelo encaminhamento local do Colima.
- Banco e chave Rails são Docker Secrets externos `cw_lab_db_password` e
  `cw_lab_secret_key_base`, criados em memória durante a instalação.
- `chatwoot-entrypoint.sh` carrega esses segredos sem tracing. É configuração
  externa; a imagem e o código do Chatwoot permanecem intactos.
- Cadastro habilitado para o primeiro administrador, ambiente local de testes.
- SMTP e canais externos não configurados; não é uma implantação de produção.

## Operação

```sh
docker --context colima-kanban-phase4 stack services cwlab
docker --context colima-kanban-phase4 stack deploy -c deploy/lab/stack.yml cwlab
```

Para liberar RAM mantendo os dados: `colima stop kanban-phase4`.
Retomar: `colima start kanban-phase4`.

A primeira preparação já foi executada com `rails db:chatwoot_prepare` no serviço
`cwlab_prepare`. Esse serviço fica com zero réplicas após a conclusão.
Em atualização futura, fazer backup antes e executar essa tarefa explicitamente,
verificando o término com sucesso antes de reiniciar Rails/Sidekiq.
Nunca apontar o Kanban ou o Chatwoot local preexistente para este banco.

Fontes: [release oficial](https://github.com/chatwoot/chatwoot/releases/tag/v4.18.0)
e [guia Docker](https://developers.chatwoot.com/self-hosted/deployment/docker).

## Kanban instalado

A stack `kblab` contém API, worker e PostgreSQL exclusivo. O menu **Pipeline**
foi incluído por `DASHBOARD_SCRIPTS`; quadro e métricas usam a sessão humana.
Imagem local `kanban-lab:phase4`, construída deste checkout, sem publicação.

`kanban.yml` usa Docker Secrets e a rede externa `cwlab_internal`. O nome completo
`kblab_postgres` evita colisão com o alias `postgres` do Chatwoot nessa topologia.
`WEBHOOK_BASE_URL=http://cwlab_proxy` define somente o callback servidor-servidor;
`PUBLIC_URL=http://localhost:18080` continua sendo a origem da interface.
O Chatwoot de laboratório permite callbacks privados por
`SAFE_FETCH_ALLOW_PRIVATE_NETWORK=true`; esta opção é específica deste laboratório.

A conta 1 tem um usuário técnico dedicado, com associação administrativa somente
nessa conta. Seu ID e a propriedade do loader ficam em `KANBAN_LAB_MANIFEST` no
Chatwoot. A credencial transitou por pipes e foi cifrada em `kb_accounts`; atributos
e webhook têm manifesto em `kb_resources`. Nenhuma importação foi solicitada.

O roteiro `activate-kanban.py` é exclusivo destas stacks e da conta 1: verifica o
backup cifrado e usa `provision-kanban.rb` e `register-account.py`. Não é ainda o
instalador genérico da Fase 4, nem deve ser usado em produção. Falhas remotas
omitem stdout/stderr, pois a resposta Rails contém uma credencial técnica.

Backup anterior à instalação: `.local/phase4/chatwoot-before-kanban.dump.fernet`.
Chave de recuperação: `.local/phase4/backup.key`, ambos com permissão 0600 no
host, fora do Git. Preservar ambos para recuperar; armazená-los juntos não substitui
uma política de backup externo. O dump foi decifrado em memória e restaurado com
`pg_restore --exit-on-error` em banco temporário, removido após a conferência.

Para reaplicar a stack Kanban após construir a imagem local:

```sh
docker --context colima-kanban-phase4 stack deploy --resolve-image never \
  -c deploy/lab/kanban.yml kblab
```

Migrações ficam no serviço `kblab_migrate`, com zero réplicas após execução.
Não executar uma atualização sem backup e revisão das migrações.
