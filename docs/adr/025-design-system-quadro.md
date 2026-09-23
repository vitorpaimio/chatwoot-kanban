# ADR-025 — Quadro integrado ao design system do Chatwoot v4

Data: 23/09/2026. Estado: aceito. Complementa ADR-024.

O iframe copia todas as propriedades CSS iniciadas por `--` do documento pai,
na mesma origem. O `theme.js` lê primeiro `documentElement`, depois os valores
resolvidos no `body`: o Chatwoot 4.16.2 aplica a paleta escura em `body.dark`.
Um MutationObserver observa classe e estilo nos dois elementos. A fonte vem de
`getComputedStyle(parent.document.body).fontFamily`. Não há paleta fixa no CSS
do quadro, nem dependência das antigas mensagens de tema do loader.

Superfícies, bordas, texto, botão azul e estados usam variáveis nativas. O primeiro
plano do botão vem do estilo computado de um botão primário nativo. Cores de etapas
e etiquetas são dados configurados pelo usuário, não cores fixas do tema.

O cabeçalho usa a geometria do ContactHeader local: 80 px de altura e título de
20 px. O seletor de funil é o título; a engrenagem abre gerenciamento, incluindo
configuração da conta. O menu de ações contém Histórico e Importar contatos.
Métricas recebe os relatórios que antes abriam no botão do quadro, usando as mesmas
rotas autenticadas `/kanban/reports` e `/kanban/board`.

Cartões abrem detalhes; a navegação à conversa permanece dentro do diálogo.
Tarefas têm ação no hover e no foco por teclado (sempre visível em telas sem hover).
Avatares preservam iniciais/foto e geometria nativa. Canal usa a máscara do ícone
nativo `i-woot-*`, com fallback genérico. Etiquetas exibem até três cores cadastradas
e contagem excedente. Textos, tooltips e valores continuam usando APIs DOM seguras
(`textContent`, `value`, `title`), sem interpolação em HTML; não é necessário aplicar
`escapeHtml` seguido de parsing. Nomes mantêm capitalização original. URLs de fotos
recusam protocolos executáveis. Erros de sincronização não expõem detalhes internos.

Nenhuma rota ou formato da API mudou. Metadados visuais são lidos das rotas existentes
do Chatwoot: etiquetas, agentes e conversa. São requests autenticados pela sessão do
navegador, somente na conta já validada; não há token de serviço ou persistência nova
de credenciais. As conversas são consultadas com concorrência limitada a quatro e
cache em memória do iframe. Se os metadados não estiverem disponíveis, o quadro mantém
iniciais, etiquetas neutras e canal genérico, sem bloquear cartões ou tarefas.

Validação: `tests/browser/board-design.cjs` executa a interface no Chatwoot 4.16.2,
compara variáveis/fonte/geometria com o pai, troca temas com formulário aberto e
verifica interações. As capturas usam dados reais; somente os testes de borda de
falhas, etiquetas e injeção interceptam respostas no navegador, sem gravar dados.

O arraste destaca a coluna de destino com as variáveis azuis nativas e uma linha
na posição de inserção. A região de captura inclui metade do espaçamento entre
colunas (8 px). A posição usa a metade vertical dos cartões para inserir antes
ou depois, mantendo o contrato `before_id`. Ao soltar, o quadro e os totais são
atualizados imediatamente; a API conserva a validação de versão. Durante a escrita,
novos arrastes e recargas SSE aguardam. Falhas restauram o estado anterior e consultam
o servidor. A animação de encaixe respeita `prefers-reduced-motion`.
