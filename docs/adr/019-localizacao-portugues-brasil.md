# ADR-019 — Português do Brasil como idioma do projeto

- **Data:** 2026-09-23
- **Estado:** Aceito
- **Motivação:** solicitação de auditoria e tradução do projeto para português do Brasil.

## Contexto

A interface e os documentos misturavam espanhol e inglês. Também havia
instruções históricas apresentadas como funcionalidades já implementadas.
A aplicação integra dados persistidos em PostgreSQL e atributos configurados
em uma instância externa do Chatwoot.

## Decisão

Usar pt-BR nos textos da interface, mensagens próprias, resumos das rotas,
comentários, documentação e nomes exibidos pelos workflows. Revisar os
documentos históricos em português, mantendo datas, decisões, referências
principais e a distinção entre o que era previsto e o que está disponível.
Regenerar as capturas com dados fictícios em português.

Preservar identificadores de código, rotas, variáveis de ambiente, nomes de
arquivos já referenciados, chaves JSON, tabelas, colunas, estados persistidos
e chaves dos atributos externos. Por exemplo, `mensaje`, `fecha_vencimiento`
e `kanban_view_mensaje` continuam válidos nos contratos existentes.
Traduzir esses contratos exigiria outra migração, com compatibilidade e
validação dos dados reais.

As etapas e os textos dos contatos vêm do Chatwoot. A tradução não altera
esses dados externos. Mensagens originadas de bibliotecas, da API externa
e da documentação interativa de terceiros podem permanecer em seu idioma.

Datas de vencimento sem horário são interpretadas como datas de calendário
local na interface e exibidas em `pt-BR`. Isso não muda o fuso do banco nem
a regra de agendamento no servidor.

## Correções associadas

- Escapar textos e atributos antes de inseri-los no HTML e aceitar apenas
  URLs HTTP/HTTPS nos pontos de imagens e links tratados.
- Corrigir a interpretação de vencimento no fuso brasileiro.
- Remover a dependência CDN Tailwind sem uso no Kanban.
- Tratar falhas de carregamento da configuração e do painel.
- Retirar o segredo presente em documentação histórica, sem reproduzi-lo.

## Consequências

O projeto passa a ter uma linguagem consistente para usuários e mantenedores.
Os contratos técnicos permanecem compatíveis. A auditoria registra problemas
do servidor ainda abertos; tradução e testes unitários não comprovam que a
aplicação esteja pronta para exposição pública.

## Validação

31 testes Python e cinco testes JavaScript aprovados, Ruff e formatação
aprovados. Quadro, modal e painel verificados em navegador com dados simulados,
nos temas claro e escuro, incluindo uma tentativa de injeção de HTML.
Sem validação contra PostgreSQL, Chatwoot ou infraestrutura de produção.
