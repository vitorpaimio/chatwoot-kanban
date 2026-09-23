# ADR-013 — Branches e proteção da produção

- **Data:** 2026-07-17
- **Estado:** Aceito

- **Decidido na:** sessão 008.

## Contexto

A produção recebia alterações diretamente em `main`, sem proteção de branch
ou testes em CI, com implantação manual no Arcane. Era necessário proteger
a produção e permitir iteração simples para uma equipe de uma pessoa.

## Decisão

| Branch | Finalidade | Proteção planejada |
|--------|------------|--------------------|
| `main` | Produção; recebe PR de `develop` | Verificação `test` e uma aprovação |
| `develop` | Homologação e trabalho diário | Sem proteção |
| `feat/<nome>` | Funcionalidades maiores | Parte de `develop`; PR para `develop` |

Para mudanças pequenas: trabalhar em `develop`, validar, enviar, testar em
`devkanban.example.com` e abrir PR para `main`. A produção é atualizada após
aprovação e integração. Mudanças maiores usam uma branch de funcionalidade.

A proteção é configurada no GitHub com uma regra de branch. Sua existência
no repositório remoto não pode ser comprovada apenas pelos arquivos locais.

## Consequências

Há uma etapa adicional de revisão, com homologação antes da produção.
`enforce_admins: false` permitiria ignorar a regra em situações urgentes,
o que também representa um risco.

## Alternativas consideradas

Trabalhar em `main` não oferece uma barreira de qualidade. Gitflow completo
adicionaria complexidade excessiva. Uma única branch sem homologação não
separaria os ambientes; apenas branches de funcionalidades não ofereceriam
uma área comum de integração para alterações pequenas.

Nota da auditoria: os testes atuais rodam em PRs. A publicação em um envio
direto para `develop` não aguarda testes, apesar do fluxo ideal descrito
na sessão original.

## Exemplos técnicos registrados

```bash
gh api repos/{owner}/{repo}/branches/main/protection \
  --method PUT \
  --input branch-protection.json
```
