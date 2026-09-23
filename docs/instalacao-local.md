# Instalação local integrada

## Pré-requisitos

Chatwoot 4.16.2 preparado em `~/chatwoot`, Ruby 3.4.4, PostgreSQL 16, Redis,
Node/pnpm, Python 3.12, Overmind e Nginx. `CHATWOOT_DIR` permite indicar outro diretório.
O Kanban não altera arquivos do Chatwoot. Não execute `db:seed` sobre uma instalação existente.

1. Verifique `bundle check`, o banco do Rails e os serviços atuais. Faça backup.
2. Crie bancos exclusivos `kanban_development` e `kanban_test`.
3. Crie `.venv`, instale `requirements.txt` e `requirements-dev.txt`.
4. Copie `.env.example` para `.env`; configure banco, URL interna e chave Fernet.
5. Execute `.venv/bin/alembic upgrade head`. O startup não cria nem altera tabelas.
6. No diretório Chatwoot, execute o instalador de configuração:

```sh
KANBAN_CONFIG_BACKUP=/Users/paim/chatwoot-kanban/.local/chatwoot-config-backup.json \
  bundle exec rails runner /Users/paim/chatwoot-kanban/scripts/install_chatwoot.rb
```

O instalador acrescenta um script marcado, preserva outros scripts, habilita a API e
configura `pt_BR` nas contas locais. Uma repetição não duplica o loader.
O backup da configuração deve ficar em diretório restrito; `.local` não é versionado.

7. Pare o processo Rails que ocupa a porta 3000 e o Sidekiq antigo, preservando Vite.
   Nesta máquina: `overmind stop -s ~/chatwoot/.overmind.sock backend worker`.
8. No projeto Kanban, execute `scripts/local.sh start`.
9. Abra `http://localhost:3000`. Um administrador pode ativar a conta no Kanban
   usando o token de serviço da conta, que será validado e armazenado criptografado.
   Alternativamente, `python scripts/activate_local.py` pede login e senha sem gravar a sessão.
   Execute esse script com a `.venv` ativada.

O token de serviço precisa de acesso administrativo à conta para atributos,
webhooks e remoção da antiga Dashboard App, caso exista. Nesta instalação local, a ativação usa o token do
administrador de desenvolvimento. Para uma implantação compartilhada, use um usuário
administrativo de serviço dedicado e conceda somente as contas necessárias.

A importação é executada pelo worker com progresso persistido. Uma falha pode ser
repetida pelo botão **Importar contatos**. Webhook, funil e cartões não são duplicados. A ativação não cria uma aba na conversa.
A configuração `SAFE_FETCH_ALLOW_PRIVATE_NETWORK=true` existe apenas nos scripts locais
do Rails e Sidekiq. Não a inclua em produção.

## Iniciar e parar

`scripts/local.sh status|start|stop|restart` controla os processos da integração.
Quando o Vite já pertencia ao Overmind do Chatwoot, ele continua sob aquele supervisor;
`stop` do Kanban preserva esse processo. Um próximo `start` detecta e reutiliza a porta 3036.
PostgreSQL e Redis também permanecem em execução.

## Desinstalar

No Chatwoot, execute `bundle exec rails runner /caminho/chatwoot-kanban/scripts/uninstall_chatwoot.rb`.
Isso remove apenas o loader marcado e as integrações com URL local do Kanban.
Pare `scripts/local.sh stop` e volte a iniciar Rails/Sidekiq pelo `Procfile.dev` original.
Se o Overmind original ainda existir, use `overmind restart backend worker` no Chatwoot.
O banco Kanban e o histórico são preservados; não há exclusão automática de dados.
Os atributos personalizados também são mantidos para preservar os dados existentes.

O proxy Nginx tem `underscores_in_headers on` para manter o contrato `api_access_token`
do Chatwoot. WebSocket e SSE são encaminhados sem buffer de resposta. O encerramento
usa prazo limitado, para não travar com sessões em tempo real abertas.

Para atualizar uma instalação anterior e remover somente a aba Kanban das conversas:

```sh
PYTHONPATH=. .venv/bin/python scripts/remove_conversation_apps.py
```

O menu lateral e os dados são preservados. Atualize a página do Chatwoot após executar.
