# Sessão 020 — Destaque e encaixe ao arrastar negociações

Alterados somente JavaScript/CSS do quadro. Colunas acendem quando o cartão se
aproxima, mostram posição de entrada e recebem o cartão imediatamente ao soltar.
O cartão original fica translúcido durante o arraste; uma animação curta marca a
chegada. Cancelamento limpa os efeitos, e a preferência de movimento reduzido é
respeitada. Em falha de gravação, restaura-se a posição e consulta-se o estado atual.
Não houve alteração de rotas ou esquema.

Verificado no Chatwoot real: arraste de um contato de teste de Novo para Em
atendimento, persistência ao reabrir o quadro e retorno à coluna original.
Validação de sintaxe JavaScript e suíte dos helpers aprovadas.
