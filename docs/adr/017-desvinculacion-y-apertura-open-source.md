# ADR-017 — Independência do projeto e abertura do código

- **Data:** 2026-07-31
- **Estado:** Aceito

- **Autor:** Cristian Alvarez.
- **Substitui / substituído por:** não se aplica.

## Contexto

O projeto começou como integração interna em `I-Labs-Chile/Ruki-Plugins-Kanban`.
A empresa decidiu não utilizá-lo, e o repositório foi transferido para
`CrisAlva1414` para permitir publicação e contribuições externas.

## Decisão

Remover referências operacionais à empresa, tornar a configuração portável
e preparar a abertura do código sob MIT, conforme declarado à época.

| Referência anterior | Substituição registrada |
|---------------------|-------------------------|
| `ruki-plugins-kanban` | `chatwoot-kanban` |
| `ruki-kanban-postgres` / `ruki-kanban-kanban` | `chatwoot-kanban-db` / `chatwoot-kanban-app` |
| `ruki_cloudflared` | `chatwoot_shared` |
| `ruki-bot.com` / `chatwoot.ruki-bot.com` | Exemplos sob `example.com` |
| `@i-labs.cl` / `bot@i-labs.cl` | `@example.com` e `CHATWOOT_BOT_EMAIL` |
| `i-labs` / `i-labs-chile` | Referências genéricas nos documentos históricos |
| Registro GHCR da organização | `ghcr.io/crisalva1414/...` |
| Proprietário `I-Labs-Chile` | `CrisAlva1414` |

E-mail do bot e URL pública passaram a ser configuráveis por
`chatwoot_bot_email` e `CHATWOOT_FRONTEND_URL`. O host padrão do banco passou
a `postgres`.

## Documentação e licença

A sessão registrou a criação de README, CONTRIBUTING, LICENSE, SECURITY,
CODE_OF_CONDUCT e CHANGELOG. Os ADRs e as sessões anteriores foram
preservados com domínios ilustrativos, mantendo o histórico arquitetural.

A intenção registrada foi adotar MIT. **O arquivo LICENSE não está presente
nesta cópia auditada**; a declaração histórica não substitui esse documento.

## Consequências

O projeto ganha identidade independente, configuração reutilizável e espaço
para contribuições. Os fluxos e imagens da organização anterior precisam
ser substituídos. Referências remanescentes devem ser revisadas; domínios
de exemplo precisam ser configurados por quem implantar a aplicação.

## Alternativas descartadas

Apagar documentos ou criar outro repositório perderia histórico útil.
Manter referências originais em configuração impediria a independência
pretendida. O histórico contextual acima não deve ser usado como configuração.
