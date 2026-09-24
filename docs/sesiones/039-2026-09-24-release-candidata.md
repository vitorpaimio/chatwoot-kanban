# Sessão 039 — Integração e release candidata

O mantenedor autorizou integrar os PRs abertos e publicar uma nova release.
A branch principal existente é `master`; não foi renomeada. PR #3 integrado
primeiro; PR #2 atualizado com suas correções e conflito documental resolvido
preservando as duas sessões. Versão preparada: `v0.2.0-rc.1` (`0.2.0rc1` no Python),
sem declarar concluída a certificação da versão estável.

Validação combinada local: 197 testes Python aprovados no banco exclusivo, dois
opt-in omitidos, Ruff, sintaxe JavaScript/shell e quatro testes JavaScript aprovados.
A publicação do instalador continua condicionada ao ensaio descartável com Chatwoot
real, duas contas, navegador, webhook, repetição, update e uninstall. A release
apontará para o commit final validado e documentará os digests publicados.

A seleção de todas as contas vale para a primeira instalação; expansão de contas
em instalações existentes não foi implementada. A recuperação da rede antiga exige
seguir o guia e preservar manifesto/recibos. Esta autorização publica código e
imagens; não executa comandos na VPS do cliente.
