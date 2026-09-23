# ADR-001 — Dashboard App como ponto de integração com o Chatwoot

- **Data:** 2026-07-09
- **Estado:** Aceito

## Contexto

Na análise inicial de viabilidade de `kanban.example.com`, a instância
`chatwoot.example.com` oferecia Dashboard Apps para incorporar uma URL externa
em um iframe na visualização de conversas. Era necessário avaliar se esse
recurso comportaria um Kanban de etapas e um sistema de tarefas.

## Decisão

Usar Dashboard App como ponto de entrada visual. Toda leitura e escrita de
dados acontece pela API REST do Chatwoot, independentemente do iframe.

## Fundamentação técnica

O `postMessage` enviado do Chatwoot ao iframe fornece `appContext`, com
`conversation`, `contact` e `currentAgent` da conversa aberta. Esse conteúdo
não é uma credencial assinada verificável pelo servidor externo.

O campo `hmac_verified` se refere à identidade do contato no widget público,
não à autenticação de agentes internos. Na integração analisada, o caminho
inverso de escrita exige chamadas REST com token válido.

## Consequências

- `postMessage` serve apenas como contexto da interface, nunca como autenticação.
- A aplicação é uma pequena interface web com servidor próprio, incorporada
  ao iframe e conectada à API REST.
- Atualizações enviadas ao Chatwoot dependem da API.

## Alternativas descartadas

Confiar no `postMessage` como credencial permitiria mensagens simuladas.
Usar apenas o painel nativo não atendia ao Kanban por etapas nem às tarefas
previstas na análise inicial.
