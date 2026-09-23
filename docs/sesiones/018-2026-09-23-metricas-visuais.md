# Sessão 018 — Métricas visuais dentro do Chatwoot

Implementado ADR-026: painel nativo com indicadores, barras por funil/etapa,
evolução diária, comparação dos funis, movimentos por agente e trajetória individual.
Filtros por funil, período, quantidade/valor e contato. Sem bibliotecas de gráficos
novas, rotas removidas ou alterações no código do Chatwoot.

Validação: 22 testes Python com PostgreSQL real, incluindo isolamento entre contas,
rejeição de funil estrangeiro, limites do período, dia civil de Brasília, dias
zerados e exclusão de reordenações/alterações apenas de valor. JavaScript e Ruff
verificados. Interface conferida na sessão autenticada do usuário no navegador
integrado, Chatwoot 4.16.2: temas claro e escuro, seleção de funil, período e contato.
Os dados locais começam hoje; o gráfico conserva os dias anteriores sem eventos.
