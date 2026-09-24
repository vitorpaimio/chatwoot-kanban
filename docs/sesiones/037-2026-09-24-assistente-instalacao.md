# Sessão 037 — Assistente de instalação

Pedido: simplificar a instalação, trocar escolhas numéricas por setas e permitir
selecionar várias contas ou todas, incluindo sua ativação.

Implementado menu `curses` sem dependência nova: setas, espaço, seleção de todas,
contador, rolagem e cancelamento. Instalações existentes ganham menu para retomar,
verificar, atualizar e remover. A confirmação mostra destino e quantidade de
contas, com Cancelar selecionado inicialmente. Nomes externos têm controles
removidos antes da exibição.

O fluxo padrão apresenta resumo e progresso; JSON fica em `--details`. O mesmo
lifecycle continua responsável por backup, provisionamento e saúde de todas as
contas. Interrupção durante aplicação registra `failed` e libera as travas.
`--all-accounts` inclui explicitamente as contas existentes na primeira instalação;
não altera contas de instalações persistidas nem ativa contas futuras por regra.

Validação: Ruff, formatação dos arquivos Python alterados, sintaxe JavaScript e
shell, quatro testes JavaScript e suíte completa de 181 testes Python aprovados
no banco exclusivo (dois opt-in omitidos). Após acrescentar a prova de interrupção,
os 24 testes focados do setup passaram. Exercitado menu em terminal real com
setas, marcar todas, desmarcar uma e Enter. Inventário somente leitura do Chatwoot
local retornou duas contas, ambas selecionadas corretamente pelo assistente com
transporte Docker simulado. Nenhum dado do Chatwoot foi alterado.

O contrato descartável de CI agora instala em duas contas com `--all-accounts`,
verifica acesso a ambas e usa `status --details` no diagnóstico. Docker indisponível
localmente: esse contrato completo não foi executado nesta sessão; continua sendo
o gate de publicação do instalador. Nenhum merge ou deploy faz parte desta mudança.
