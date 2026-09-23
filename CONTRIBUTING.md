# Como contribuir

Textos e documentação usam português do Brasil. Identificadores técnicos e contratos
externos mantêm os nomes existentes. A release pública planejada é 0.2.0; a versão
atual do pacote não representa certificação dessa entrega.

## Preparar o ambiente

Requisitos: Python 3.12, PostgreSQL 16, Node.js 22 ou superior. Testes de navegador
exigem Playwright, Chrome e Chatwoot local preparado. Siga o
[guia local](docs/instalacao-local.md); ele não é um instalador de produção.

```sh
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env
```

Configure DATABASE_URL para o banco exclusivo do Kanban, CHATWOOT_BASE_URL,
PUBLIC_URL e ENCRYPTION_KEY. Gere a chave localmente conforme `.env.example` e
proteja o arquivo. Não reutilize o banco Rails para o Kanban nem passe DATABASE_URL
ou ENCRYPTION_KEY do Kanban aos processos Rails/Sidekiq.

Execute Alembic explicitamente antes de iniciar API/worker. O startup não altera
schema. Para desenvolvimento integrado, `scripts/local.sh` supervisiona os serviços
locais; ele pressupõe as dependências descritas no guia e não deve ser usado em VPS.

## Verificações

Os testes Python usam PostgreSQL real e simulam as chamadas externas do Chatwoot.
O banco deve ser descartável, exclusivo, com nome terminado em `_test`.
`tests/conftest.py:db` executa TRUNCATE CASCADE das tabelas Kanban; o teste legado
cria tabelas auxiliares e usa pg_dump. Nunca aponte TEST_DATABASE_URL a dados reais.
Configure TEST_DATABASE_URL por entrada protegida ou pelo ambiente de testes.

```sh
: "${TEST_DATABASE_URL:?Configure um banco exclusivo com sufixo _test}"
DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/alembic upgrade head
.venv/bin/ruff check app migrations scripts tests
.venv/bin/pytest -q
node --test tests/test_interface.cjs
for file in app/static/*.js tests/browser/*.cjs; do node --check "$file"; done
```

Testes de integração criam dados e devem rodar apenas em Chatwoot de testes.
Carregue CHATWOOT_LOGIN_EMAIL e CHATWOOT_LOGIN_PASSWORD pelo ambiente, sem colocar
senhas em argumentos, histórico do shell ou arquivos temporários. Não há credenciais
padrão. Sessões são mantidas apenas em memória; não usar storageState persistido.

```sh
npm ci
node tests/browser/live.cjs
node tests/browser/sidebar.cjs
node tests/browser/board-design.cjs
node tests/browser/drag.cjs
```

`tests/browser/outage.py` interrompe serviços locais e não pertence ao gate comum.
Leia o arquivo e prepare o ambiente antes de executá-lo. A suíte de contratos
`tests/contracts/chatwoot_phase0.rb` exige uma cópia isolada do Chatwoot CE e bancos
específicos; o relatório da Fase 0 documenta sua execução e limites.

## Arquitetura e contratos

| Arquivo | Responsabilidade |
|---|---|
| app/main.py | Inicialização e páginas; health atual verifica apenas o processo |
| app/security.py | Sessão Chatwoot, conta ativa, papel e criptografia |
| app/routers/workspace.py | Quadro, tarefas, histórico, ativação, webhooks e SSE |
| app/routers/metrics.py | Métricas autenticadas e CSV |
| app/metrics/ | Agregações temporais e cache de APIs nativas |
| app/database.py | Pool, bloqueios, histórico e fila transacional |
| app/services.py | Provisionamento atual, importação e espelhos |
| app/worker.py | Importação, entregas, sincronização e vencimentos |
| app/chatwoot_client.py | Cliente HTTP; retentativas de sincronização ficam no worker |
| app/static/ e app/templates/ | Loader e interface incorporada |
| migrations/ | Única origem das mudanças de schema via Alembic |

As decisões da 0.2.0 estão no [plano](docs/plano-0.2.0.md). Ele descreve mudanças
futuras, incluindo autoridade local estrita, G5 e atributos novos. Não assumir que
essas políticas já estão implementadas. Não alterar código ou imagem do Chatwoot.

Toda mutação de contato exige isolamento por conta, bloqueio, histórico e fila na
mesma transação. Mudanças de integração exigem validação real nas versões alvo,
além de testes simulados. Não criar schema no startup ou importar no GET do quadro.

## Contribuições

Use Conventional Commits com descrição em português. Python segue Ruff e linhas
de 88 caracteres, com tipagem pública e docstrings Google quando aplicável.
Trabalhos substanciais atualizam ADR e sessão em `docs/sesiones/`.

Branches de contribuição partem de develop e PRs têm develop como destino, salvo
orientação do mantenedor. Não sobrescrever tags. A CI atual condiciona publicação
aos testes do mesmo commit; navegador, carga e Swarm precisam do gate de release
registrado. Inclua no PR problema, comportamento final, testes e limitações.

Relatos de vulnerabilidade seguem [SECURITY](SECURITY.md), nunca uma issue pública
com detalhes exploráveis. Licença da 0.2.0 e canal privado definitivo permanecem
pendentes de decisão; preservar a licença MIT atual até aprovação.
