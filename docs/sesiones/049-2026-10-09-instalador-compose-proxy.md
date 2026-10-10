# Sessão 049 — Instalador Compose atrás de proxy existente

## Problema

Duas issues do instalador Compose, abertas por quem instala em Coolify:

- #22: o Nginx gerado descarta o cabeçalho `api_access_token`; a API do Chatwoot
  responde 401 pelo gateway.
- #21: o webhook usa sempre `http://<nome>_api:8000`, recusado pelo `SafeFetch` do
  Chatwoot 4.17+. Atrás de um domínio HTTPS, salvar no Kanban também dava 403
  porque `PUBLIC_URL` ficava em `http://localhost:<porta>`.

## Avanços

- `underscores_in_headers on` no bloco `server` do Nginx gerado.
- Campo opcional `external_url` em `Deployment` e opção `--external-url` no fluxo
  rápido, somente Compose. Define `PUBLIC_URL` e a base do webhook; a comparação
  de configuração imutável aceita a mudança num `update`.
- ADR-036 e README atualizados.

## Validação

- Ruff aprovado; pytest com PostgreSQL exclusivo `kanban_test`: 258 testes passaram
  e 3 foram ignorados. Testes de JavaScript aprovados.
- Novos testes cobrem o cabeçalho do Nginx, a URL externa no ambiente renderizado,
  a recusa no Swarm, a inclusão por `update` e a preservação num `update` seguinte.
- Não houve teste num Chatwoot Compose real nesta sessão; quem abriu a issue validou
  a mesma abordagem no Chatwoot 4.18.0 com Coolify.

## Próximos passos

Validar num Chatwoot Compose real atrás de proxy HTTPS. Avaliar aviso no `status`
quando o callback for privado e nenhum evento chegar em `kb_deliveries`.
