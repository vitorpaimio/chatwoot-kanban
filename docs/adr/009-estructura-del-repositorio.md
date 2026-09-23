# ADR-009 — Estrutura do repositório

- **Data:** 2026-07-09
- **Estado:** Aceito

## Contexto

A estrutura precisa ser compreensível por pessoas e assistentes, separando
aplicação, configuração, documentação e integração contínua.

## Decisão

- `AGENTS.md`: contexto e instruções lidos pelo assistente.
- `app/`: código da aplicação; atualmente inclui também os modelos HTML.
- `docs/`: ADRs, convenções e sessões.
- `.github/`: integração e publicação contínuas.
- Raiz: Dockerfile, Compose, pyproject.toml, ruff.toml e .env.example.

## Consequências

A documentação pode ser consultada conforme a necessidade, sem se misturar
com o código executável. As sessões em `docs/sesiones/` recebem número e data.
A descrição inicial restringia `app/` a Python; a interface HTML foi
incorporada posteriormente em `app/templates/`.
