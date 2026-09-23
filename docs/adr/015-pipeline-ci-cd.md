# ADR-015 — Integração contínua e implantação

- **Data:** 2026-07-17
- **Estado:** Aceito

- **Decidido na:** sessão 008.

## Contexto

Havia apenas a publicação da imagem em `main`, sem testes automáticos nem
homologação. A implantação era manual. O novo fluxo precisava testar PRs,
publicar `:develop` e atualizar os dois ambientes pelo Arcane GitOps.

## Decisão

### Testes

`test.yml` é acionado em PRs para `main` e `develop`. Executa Ruff e pytest,
com PostgreSQL 16 disponível como serviço temporário. Na sessão original,
a equipe optou por não adicionar mypy considerando o tamanho do projeto
(cerca de 1.800 linhas) e os 29 testes existentes. Ruff, porém, não verifica
tipos como mypy; essa justificativa não comprova segurança de tipagem.

### Publicação

`docker_publish_develop.yml` publica `:develop` após envio para `develop`.
`docker_publish.yml` publica a produção após envio para `main`.
Ambos usam GHCR, cache do GitHub Actions e `linux/arm64`, arquitetura do
OrangePi5 utilizado como NAS.

### Implantação pelo Arcane

Não usar SSH a partir do GitHub Actions. Configurar dois projetos GitOps:

1. Produção: branch `main`, arquivo `docker-compose.yml`.
2. Homologação: branch `develop`, arquivo `developer-compose.yml`.
3. Habilitar sincronização automática, prevista a cada um ou dois minutos.

Fluxo esperado: envio → construção → publicação no GHCR → detecção pelo
Arcane → download e reimplantação. Um webhook para forçar sincronização
imediata ficou como melhoria futura.

## Consequências

Testes em PRs e homologação tornam a revisão mais controlada. A atualização
depende do Arcane; em caso de indisponibilidade, o operador pode executar
`docker compose pull && docker compose up -d` no servidor.

Não há dependência entre os workflows de testes e publicação em pushes
diretos. A proteção da branch `main` precisa ser configurada no GitHub.

## Alternativas descartadas

SSH público exigiria credenciais e mais exposição. Um executor próprio no
NAS acrescentaria manutenção. Usar somente Arcane eliminaria os testes e
a construção no GitHub. Um webhook de implantação imediata não era necessário
para a frequência de mudanças prevista.
