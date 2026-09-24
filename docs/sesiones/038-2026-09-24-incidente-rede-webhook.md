# Sessão 038 — Incidente de rede e webhook na instalação Swarm

Relato da VPS: instalador baseado em `55c5582` declarou `ready`, mas a rede escolhida
era a do banco e não a do Traefik. `/kanban/loader.js` retornava 504; o script global
com `defer` atrasava DOMContentLoaded. O webhook interno também era recusado pelo
SafeFetch. Nenhuma alteração de produção foi executada nesta sessão.

O patch mencionado no relato existe em um caminho temporário da VPS, não no
workspace. Correções implementadas a partir do diagnóstico e do código vigente,
em branch separada do assistente visual (PR #2).

Decisões registradas no ADR-038: descobrir rede do provedor e comprovar vínculo com
Rails/Traefik; callback público no Swarm; verificar o loader externo antes de
provisionar e no status; loader async; remoção de webhook antigo limitada por
recibo, conta, ID e URL. Estado antigo incompatível é recusado; recuperação dos
dois arquivos de configuração documentada, sem migração silenciosa de identidade.

Validação final: 185 testes Python passaram no banco exclusivo, dois opt-in
omitidos; Ruff, quatro testes JavaScript e sintaxe JavaScript/Ruby aprovados.
Os 15 testes de roteamento incluem estado antigo e preservação do callback Compose. Rails local real validou
migração de webhook, repetição, preservação de recursos alheios e remoção do loader
em transação revertida, sem imprimir tokens. Chromium real confirmou que o loader
indisponível não prende DOMContentLoaded. Scripts dessas provas estão em
`tests/contracts/installer_resources.rb` e `tests/browser/installer-loader.cjs`.

Docker indisponível localmente: topologia completa Swarm e entrega real de evento
do Sidekiq continuam pendentes de ensaio na infraestrutura apropriada. A prova
de GET público não representa certificação de entrega de webhook.
