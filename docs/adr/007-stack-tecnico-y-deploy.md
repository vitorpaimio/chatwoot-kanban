# ADR-007 — Tecnologias e estratégia de implantação

- **Data:** 2026-07-09
- **Estado:** Aceito

- **Atualização histórica:** 2026-07-13.

## Contexto

O projeto começou como um repositório privado com servidor e interface,
hospedado em infraestrutura própria. O GitHub Actions constrói a imagem,
o GHCR a armazena e o Arcane gerencia a implantação.

## Decisão

Python 3.12, FastAPI 0.139.0 e PostgreSQL 16. A experiência do desenvolvedor
com Python favorecia compreensão e manutenção. Pydantic oferece validação
de dados; para menos de dez agentes, a linguagem não era considerada um
limitador de desempenho. PostgreSQL já estava disponível.

Dependências registradas:

```text
fastapi==0.139.0
uvicorn[standard]==0.30.6
httpx==0.27.2
pydantic-settings==2.5.2
asyncpg==0.29.0
```

## Implantação

GitHub Actions → GHCR → Arcane → Docker Compose no NAS.
Um envio para `main` inicia a construção da imagem; o Arcane baixa e
reinicia a aplicação, que se conecta ao contêiner `chatwoot-kanban-db`.
A proposta inicial previa amd64 e arm64; o ADR-015 restringiu a publicação
a `linux/arm64`.

A aplicação `chatwoot-kanban-app` escuta na porta 8000, sem publicação de
portas no Compose. O acesso externo usa Cloudflare Tunnel. O Dockerfile
usa múltiplas etapas e o usuário sem privilégios `appuser`.

## Configuração e estrutura

Segredos pertencem ao `.env` do servidor, nunca ao repositório.
`.env.example` documenta nomes e valores ilustrativos. O código fica em
`app/`, com rotas, modelos e modelos de página; testes em `tests/` e
workflows em `.github/workflows/`. A configuração fica na raiz.

Os exemplos históricos abaixo preservam os nomes técnicos. Para implantar
a versão atual, siga o README e o `.env.example`, especialmente o nome do
host PostgreSQL correspondente ao ambiente.

## Exemplos técnicos registrados

```bash
# Chatwoot
CHATWOOT_BASE_URL=https://chatwoot.example.com
CHATWOOT_ACCOUNT_ID=
CHATWOOT_BOT_TOKEN=

# Postgres
POSTGRES_USER=
POSTGRES_PASSWORD=
POSTGRES_DB=
DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}

# Cloudflare Access
CF_ACCESS_TEAM_DOMAIN=
CF_ACCESS_AUD=

# App
ENV=production
```
