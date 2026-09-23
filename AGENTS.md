# Chatwoot-Kanban — Kanban

Integração de Kanban e tarefas com o Chatwoot CRM. Aplicação FastAPI com
interface HTML/JavaScript própria, exibida em um iframe dentro do Chatwoot.
O idioma dos textos e da documentação é português do Brasil (pt-BR).

## Arquitetura vigente — integração local

Os ADRs 020–023 substituem as decisões antigas sobre identidade, sincronização e execução.
A interface é interna ao Chatwoot em localhost:3000; Nginx encaminha /kanban para API:8000
 e o restante para Rails:3001. Não modificar o código do Chatwoot.

- `app/security.py`: sessão real, conta ativa e autorização por papel.
- `app/routers/workspace.py`: API autenticada, webhooks e SSE.
- `app/services.py`: ativação, projeções e reconciliação de contatos.
- `app/worker.py`: importação, fila de sincronização e vencimentos.
- `migrations/`: único lugar para mudanças de esquema (Alembic).
- `app/static/`: loader e interface em português.
- `scripts/local.sh`: iniciar/parar os processos locais; nunca herdar DATABASE_URL do Kanban no Rails.
- `tests/`: PostgreSQL real; `tests/browser/`: integração com o Chatwoot local.

Não criar tabelas no startup, importar dados no GET do quadro ou usar identidade de bot.
Toda mutação de contato precisa de isolamento por conta, bloqueio, histórico e fila
na mesma transação. Não expor tokens em logs ou arquivos temporários.
Validação obrigatória: Ruff, pytest no banco exclusivo e JavaScript; mudanças de integração
exigem teste no Chatwoot real. A CI publica apenas depois dos testes do mesmo commit.

## Tecnologias

| Camada | Tecnologia |
|--------|------------|
| Ambiente de execução | Python 3.12 |
| Framework | FastAPI |
| Cliente HTTP | httpx (API do Chatwoot) |
| Banco de dados | PostgreSQL 16 com asyncpg |
| Análise de código | Ruff |
| Integração contínua | GitHub Actions (Ruff + pytest em PRs) |
| Implantação | Docker → GHCR → Arcane GitOps |
| Exposição | Cloudflare Tunnel + Access na infraestrutura |

## Estrutura do projeto

```text
├── AGENTS.md              ← instruções do projeto
├── docker-compose.yml     ← produção (Arcane sincroniza main)
├── developer-compose.yml  ← homologação (Arcane sincroniza develop)
├── Dockerfile
├── pyproject.toml
├── ruff.toml
├── requirements.txt
├── requirements-dev.txt
├── .env.example
├── .gitignore
├── app/
│   ├── main.py             ← aplicação FastAPI
│   ├── config.py           ← configurações com pydantic-settings
│   ├── chatwoot_client.py  ← cliente da API do Chatwoot
│   ├── database.py         ← conexões, estrutura e consultas do banco
│   ├── schemas/chatwoot.py ← modelos Pydantic
│   ├── routers/
│   │   ├── kanban.py       ← quadro, tarefas, agendamento e estatísticas
│   │   ├── webhooks.py     ← recebimento de eventos
│   │   ├── conversations.py ← rotas de diagnóstico
│   │   └── api.py          ← encaminhamento de requisições
│   └── templates/
│       ├── kanban.html
│       └── dashboard.html
├── tests/                 ← testes automatizados
├── .github/workflows/     ← testes e publicação de imagens
└── docs/
    ├── README.md          ← índice da documentação
    ├── adr/               ← registros de decisões arquiteturais
    ├── format/            ← convenções de desenvolvimento
    └── sesiones/          ← histórico das sessões de trabalho
```

## Convenções

- **Idioma:** português do Brasil em textos, documentação e mensagens próprias.
  Preservar rotas, chaves de API, atributos do Chatwoot, tabelas, colunas,
  estados persistidos e identificadores técnicos usados por integrações.
- **Commits:** Conventional Commits (`feat:`, `fix:`, `docs:` etc.), com descrição em português.
- **Python:** Ruff, linhas de 88 caracteres, tipagem completa nas interfaces
  públicas e comentários apenas quando necessários.
- **Comentários:** docstrings no estilo Google em módulos públicos. Comentários
  pontuais devem explicar um motivo que não seja evidente pelo código.
- **Documentação:** toda mudança substancial deve incluir ou atualizar o ADR
  correspondente e a sessão ativa.
- **Banco:** versionar o esquema com Alembic quando a ferramenta for adicionada.
- **Etapas:** seguir o ADR-011; cada sessão registra avanços e próximos passos.

## Fluxo de trabalho diário

| Branch | Ambiente | Implantação |
|--------|----------|-------------|
| `main` | Produção | Arcane GitOps após integração de develop |
| `develop` | Homologação | Arcane GitOps após envio de alterações |

1. Trabalhar diretamente em `develop` nas alterações pequenas.
2. Executar Ruff e pytest localmente; enviar com `git push origin develop`.
3. GitHub Actions publica a imagem `:develop` no GHCR.
4. Arcane sincroniza, baixa a imagem e reimplanta no NAS.
5. Validar em `devkanban.example.com`.
6. Abrir um PR de `develop` para `main`.
7. Após os testes e a aprovação manual, integrar o PR.
8. Arcane reimplanta a produção em `kanban.example.com`.

A CI vigente executa testes em PRs e pushes. A publicação depende do job de testes
do mesmo commit; ver ADR-023.

### Homologação no Arcane

1. Criar um projeto a partir do repositório Git.
2. Selecionar a branch `develop` e `developer-compose.yml`.
3. Configurar `.env` com `POSTGRES_DB=kanban_staging` e
   `POSTGRES_HOST=chatwoot-kanban-staging-db`.
4. Habilitar a sincronização automática (`Auto Sync`).

### Recuperação manual

No Arcane, usar `Redeploy` para baixar a imagem disponível ou `Restart` para
reiniciar. No servidor, executar `docker compose pull && docker compose up -d`.
Isso reaplica a imagem da tag atual; para retornar a uma versão anterior,
é necessário selecionar uma imagem anterior e avaliar a compatibilidade do banco.

## Referências

- [Documentação](docs/README.md)
- [Decisões arquiteturais](docs/adr/README.md)
- [Convenções](docs/format/README.md)
- [Sessões](docs/sesiones/README.md)
