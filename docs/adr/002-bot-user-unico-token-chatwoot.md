# ADR-002 — Usuário de serviço único para autenticação na API do Chatwoot

- **Data:** 2026-07-09
- **Estado:** Aceito

## Contexto

A análise inicial identificou a necessidade de um `api_access_token` válido
para as chamadas do servidor. Registrou a limitação de escopo dos tokens
(issue #12590): o token herda permissões do usuário ao qual pertence.

Tokens individuais ampliariam a quantidade de credenciais e o trabalho de
integração e revogação por agente. O acesso de cada agente ao próprio token,
sem uma visão administrativa centralizada, também foi considerado um risco.

## Decisão

Usar um usuário de serviço dedicado, como `api-bot@example.com`, com papel de
agente. Seu token fica exclusivamente nas variáveis de ambiente do servidor,
sem exposição ao navegador ou aos agentes humanos.

## Fundamentação técnica

| Alternativa | Risco e operação | Resultado |
|-------------|------------------|-----------|
| Token por agente | Mais credenciais, configuração individual e dependência de pessoas | Descartada |
| Token único no servidor | Uma credencial para controlar e substituir | Escolhida |

O risco residual é a amplitude das permissões do token. As medidas previstas
são mantê-lo no servidor e expor somente as operações necessárias à interface.
O comprometimento do servidor ou do token continua podendo afetar a conta.

## Ciclo de vida

A sessão original registrou que desativar um usuário invalida seu token.
Por isso, vincular a integração a um funcionário cria uma dependência
operacional de sua permanência. O usuário de serviço reduz essa dependência.

## Consequências

- O servidor intermedeia as chamadas ao Chatwoot.
- A atribuição ao agente humano é mantida pelo registro próprio (ADR-004),
  pois o Chatwoot identifica o usuário de serviço como autor das chamadas.
- A análise original registrou que `sender_id` em mensagens deriva do token
  e não pode ser escolhido arbitrariamente no corpo de `POST .../messages`.
