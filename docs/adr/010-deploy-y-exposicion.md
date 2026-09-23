# ADR-010 — Implantação e exposição da aplicação

- **Data:** 2026-07-09
- **Estado:** Aceito

- **Atualização histórica:** 2026-07-13.

## Contexto

A aplicação roda em um NAS local. O acesso externo deve passar pelo
Cloudflare, sem portas do serviço publicadas diretamente na internet.

## Decisão

| Componente | Definição |
|------------|-----------|
| Imagem | Docker no GHCR; atualmente arm64 conforme ADR-015 |
| Construção | GitHub Actions após envio às branches configuradas |
| Orquestração | Docker Compose no NAS |
| Administração | Arcane para contêineres, registros e atualizações |
| Rede | Rede externa compartilhada `chatwoot_shared` |
| Exposição | Cloudflare Tunnel |
| Autenticação planejada | Cloudflare Access e validação JWT na aplicação |

Os contêineres seguem `chatwoot-<projeto>-<serviço>`.

## Fluxo

1. Enviar a alteração; GitHub Actions constrói e publica a imagem.
2. Arcane baixa a imagem e executa `docker compose pull && docker compose up -d`.
3. A aplicação se conecta a `chatwoot-kanban-db`.
4. O túnel, em contêiner separado na mesma rede, fornece o acesso externo.

## Consequências

O Compose não possui `ports:`. A imagem usa `appuser` e construção em
múltiplas etapas. A validação JWT em cada requisição protegida permanece
pendente; ela não pode ser presumida apenas porque o túnel está configurado.
