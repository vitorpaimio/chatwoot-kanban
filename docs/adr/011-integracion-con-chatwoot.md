# ADR-011 — Integração com o Chatwoot por etapas

- **Data:** 2026-07-09
- **Estado:** Aceito

- **Substitui:** a divisão de etapas inicialmente associada ao ADR-007.

## Contexto

A API REST oferece filtros, atributos personalizados e webhooks. A
integração visual usa iframe; não modifica a interface do Chatwoot.
É necessário conhecer o formato real das respostas antes de modelar o domínio.

## Decisão

Formalizar as cinco etapas da sessão de viabilidade (Opus 4.8):

| Etapa | Objetivo | Componentes |
|-------|----------|-------------|
| 0 | Autenticação e agentes | Cloudflare Access, validação JWT, tabela `agentes`, `/health` |
| 1 | Exploração somente para leitura | `/debug/custom-attribute-definitions`, `/debug/conversations/filter` |
| 2 | Escrita e eventos | Atualização de atributos e webhook `conversation_updated` |
| 3 | Kanban completo | Interface, arrastar e soltar e sincronização entre agentes |
| 4 | Tarefas | Criação, edição, encerramento, agendamento, auditoria e histórico |

Cada mudança de direção deve atualizar ou criar um ADR. Validar uma etapa
antes de avançar; infraestrutura e exploração podem ocorrer em paralelo.

## Consequências

Os modelos de domínio são definidos após conhecer os dados reais. O cliente
HTTP concentra as operações externas. A interface usa HTML e JavaScript
servidos pelo FastAPI. A etapa 0 prevê middleware de validação JWT, ainda
pendente no código auditado.
