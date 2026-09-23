# Convenções de Git

## Commits

Formato **Conventional Commits**:

```text
<tipo>(<escopo opcional>): <descrição no imperativo>

[corpo opcional]
```

- `feat`: funcionalidade nova.
- `fix`: correção de defeito.
- `docs`: documentação.
- `style`: formatação, sem mudança de comportamento.
- `refactor`: reorganização sem mudança funcional.
- `perf`: melhoria de desempenho.
- `test`: inclusão ou correção de testes.
- `chore`: ferramentas, integração contínua e configuração.

A descrição deve estar em português, no imperativo (por exemplo, "adicione
uma rota"), sem ponto final nem emojis. Use o corpo para explicar o motivo
quando necessário. Não altere hashes ou referências de commits históricos.

## Branches

| Branch | Finalidade | Proteção planejada |
|--------|------------|--------------------|
| `main` | Produção; recebe PRs de `develop` | Verificação `test` e uma aprovação |
| `develop` | Homologação e integração diária | Sem proteção |
| `feat/<nome>` | Funcionalidade que exige isolamento | Parte de `develop`; PR para `develop` |
| `fix/<nome>` | Correção pontual | Parte de `develop`; PR para `develop` |
| `docs/<nome>` | Documentação | Parte de `develop`; PR para `develop` |

## Fluxo de trabalho

Para mudanças pequenas:

1. `git checkout develop`.
2. Trabalhar, executar Ruff e pytest e criar o commit.
3. `git push origin develop`.
4. A imagem `:develop` é publicada e o Arcane atualiza a homologação.
5. Validar em `devkanban.example.com`.
6. Abrir PR de `develop` para `main`; revisar, aprovar e integrar.

Para funcionalidades maiores, criar `git checkout -b feat/<nome> develop`,
implementar, validar e abrir PR para `develop`. Após a homologação, seguir
com o PR para `main`.

## PRs

O título segue o formato do commit principal. Inclua referências a ADRs e
relatos quando pertinente. A proteção proposta para `main` exige testes
aprovados e pelo menos uma revisão; sua configuração no GitHub deve ser
verificada no repositório remoto. Os workflows locais só executam testes
em PRs: um push direto não possui essa barreira de qualidade.
