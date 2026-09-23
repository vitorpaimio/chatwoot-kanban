# ADR-020 — Interface interna e sessão do Chatwoot

Estado: aceito em 23/09/2026. Substitui os ADRs 002/003 quanto à identidade do agente.

O usuário entra no Chatwoot 4.16.2 em `localhost:3000`. Nginx encaminha `/kanban`
para FastAPI e o restante para Rails em 3001, incluindo conexões WebSocket.
`DASHBOARD_SCRIPTS` instala um loader idempotente que acrescenta o menu e um iframe,
sem modificar o código original, interceptar o roteador ou substituir o histórico.
A Dashboard App compacta usa o contexto da conversa apenas para selecionar o contato.

Cada acesso a dados valida a sessão em `/api/v1/profile`. A conta precisa estar ativa
e conter o usuário. Agentes operam cartões/tarefas; administradores gerenciam configuração.
Credenciais de sessão não são persistidas, registradas ou enviadas por postMessage.
Tokens de serviço e segredos de webhook são cifrados com Fernet e chave externa.
Mensagens entre frames exigem mesma origem, janela emissora esperada e identificadores válidos.
