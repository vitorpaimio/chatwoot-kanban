# ADR-027 — Negociações com busca de contatos e acesso pelo menu lateral

Data: 23/09/2026. Estado: aceito. Atualiza ADR-020, ADR-024 e ADR-025.

O acesso ao Kanban ocorre somente em Pipeline, no menu lateral. A ativação deixa
 de registrar Dashboard App e remove apenas a antiga app Kanban com URL exata desta
instalação/conta. `scripts/remove_conversation_apps.py` aplica a mesma atualização
às contas existentes. Outras apps, webhooks, contatos e histórico são preservados.
A rota compacta permanece compatível, mas não é registrada na conversa.

Adicionar negociação abre um diálogo amplo de duas colunas. Primeiro o usuário
busca um contato por nome, telefone ou e-mail na API nativa do Chatwoot, usando a
sessão atual e a conta selecionada. Os resultados são paginados; a busca tem debounce
e descarta respostas antigas. A seleção revela funil e etapas, com o contato
identificado. O seletor principal e o do diálogo usam menus de 14 px com variáveis
nativas, navegação por teclado e fechamento por Escape/clique externo.

Negociação é o cartão existente: permanece uma por contato/funil. A interface avisa
sobre duplicidade antes de salvar e o servidor mantém o conflito 409. A criação
continua em POST /kanban/cards. Quando o contato ainda não existe no banco Kanban,
o servidor o consulta na conta do Chatwoot e importa seus metadados, sem criar um
cartão implícito na primeira etapa. Criação, histórico e sincronização continuam na
mesma transação. Não se cria um novo contato nem se altera o modelo de dados.
