# Sessão 017 — Visual do quadro com design system nativo

Implementado ADR-025. Removidos o título grande, texto superior, botão Fechar e
botão Relatórios do quadro. Seletor de funil e engrenagem no cabeçalho, ponto de
conexão, ações compactas e aviso de falhas condicionado à contagem.

Cartões: avatar, canal, nome original, telefone, três etiquetas e excedentes,
responsável com tooltip, atividade relativa, valor positivo, alerta de falha,
clique para detalhes e tarefas com vencimento destacado.

Capturas reais: `.local/quadro-chatwoot-light.png` e `.local/quadro-chatwoot-dark.png`.
Teste: `PLAYWRIGHT_MODULE=/caminho/playwright node tests/browser/board-design.cjs`.
A sessão temporária fica em `.local/board-browser-state.json` com permissão 0600
para repetir sem acumular logins. Ao concluir, encerrar essa sessão e apagar o arquivo.
Nenhum código, banco ou contrato da API do Chatwoot foi alterado.

Validação concluída: navegador real com ambos os temas, variáveis e fontes copiadas,
header de 80 px/título de 20 px iguais a Contatos, filtros, detalhes, tarefas,
rascunho preservado, gerenciamento, histórico, métricas, limites de etiquetas,
valores zerados, falhas e XSS. 20 testes Python, 3 JavaScript, Ruff e formatação
aprovados. Também conferido o clique no cartão e o quadro final na sessão do usuário
no navegador integrado, deixando Pipeline → Kanban aberto.
