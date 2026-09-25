# ADR-042 — Branch principal `main` protegida

Estado: aceito em 25/09/2026.
Atualiza o ADR-037 (gate de release) e o fluxo do AGENTS.md.

## Contexto

O repositório usava `master` como única branch, e alterações podiam ser enviadas
direto nela. Com mais pessoas contribuindo, o mantenedor pediu que a branch
principal se chamasse `main` e só recebesse mudanças revisadas.

## Decisão

- `master` foi renomeada para `main` no GitHub; PRs abertos e a branch padrão
  acompanham a mudança.
- `main` exige PR com uma aprovação e o check `test` aprovado; push forçado e
  exclusão ficam bloqueados. Administradores podem integrar em emergência.
- `install.sh` e o README apontam para `main` e para a imagem `installer-main`.
  Enquanto houver scripts antigos, a publicação da `main` também atualiza a tag
  `installer-master`.
- Não há branch `develop`: cada mudança sai de uma branch própria direto para PR
  contra `main`.

## Consequências

- A imagem da aplicação passa a ser publicada como `:main`; ambientes que usam a
  tag `:master` precisam trocar para `:main` ou para o digest do commit.
- Clones antigos precisam de `git branch -m master main` e
  `git branch -u origin/main main`.
