# Sessão 001 — Viabilidade técnica e arquitetura do Kanban e das tarefas

- **Data:** 2026-07-09
- **Natureza:** registro histórico, revisado em português do Brasil.

## Objetivo e contexto

Avaliar a viabilidade de adicionar ao Chatwoot auto-hospedado um Kanban
com movimentação entre etapas e tarefas com autoria, duração e estados.
O escopo inicial era verificar APIs e limitações, sem prototipar a interface.
O projeto era `kanban.example.com`, integrado a `chatwoot.example.com`.

## Fontes registradas na sessão original

- [Dashboard Apps](https://www.chatwoot.com/hc/user-guide/articles/1677691702-how-to-use-dashboard-apps): iframe, `postMessage` e `hmac_verified`.
- [Índice técnico do Chatwoot](https://www.chatwoot.com/llms.txt): API, eventos, conexões e integrações.
- Discussões sobre filtros, `create_message`, `sender_id` e ciclo de vida dos tokens.
- Issues #12590 (escopo dos tokens), #7402 (eventos duplicados) e #13993
  (variação no formato dos webhooks).

Essas são referências da investigação histórica, não uma revalidação atual.

## Decisões

| ADR | Decisão original |
|-----|------------------|
| 001 | Dashboard App é apenas a integração visual; operações usam REST |
| 002 | Um usuário de serviço com token exclusivo no servidor |
| 003 | Cloudflare Access com código temporário por e-mail corporativo |
| 004 | Registro próprio para identificar quem realizou cada ação |
| 005 | Tarefas no banco próprio, espelhando `tarea_estado` |
| 006 | Quadro baseado em atributos de conversas |
| 007 | Python, FastAPI e PostgreSQL; implantação em servidor próprio |

A estratégia inicial de SSH e construção no servidor foi posteriormente
substituída por GitHub Actions, GHCR e Arcane.

## Escopo original do MVP

O quadro usaria `pipeline` como seletor, `pipeline_stage` para colunas e
`tarea_estado` como filtro adicional na mesma chamada a
`/conversations/filter`. Arrastar e soltar atualizaria atributos pela API.
Eventos `conversation_updated` exigiriam idempotência por
`conversation.id + updated_at`.

Uma tarefa ativa por conversa, com bloqueio inicial de nova criação se já
houvesse uma. Qualquer agente poderia criar e encerrar tarefas. O fluxo
previsto era `tarea_activa → tarea_hoy → tarea_vencida → tarea_cerrada`, com
agendamento às 23h30 e sem notas automáticas. Mensagem e datas ficariam no
banco, com criação por modal. Notas privadas foram descartadas (ADR-005).

O histórico exibiria as últimas cem tarefas com
`ORDER BY created_at DESC LIMIT 100`. Ficaram fora do MVP recorrências,
múltiplas tarefas simultâneas, papéis diferenciados e notificações por
menção em notas privadas.

## Entrega da etapa 1

O pacote inicial `chatwoot-integration/` incluía `app/main.py`, configurações
Pydantic, cliente httpx, rotas de exploração, diretório de modelos, Dockerfile,
Compose, variáveis de exemplo e dependências. Uvicorn escutava na porta 8000.

Rotas entregues:

- `GET /health`: verifica se o processo responde.
- `GET /debug/custom-attribute-definitions`: inspeciona chaves e tipos exatos.
- `POST /debug/conversations/filter?attribute_key={key}&value={value}`:
  inspeciona o formato das conversas e da paginação.

Para validar, o desenvolvedor deveria criar o bot, obter o token, confirmar
`account_id` na URL do Chatwoot, configurar `.env`, iniciar os contêineres e
consultar os dois exemplos de resposta antes de definir os modelos Pydantic.

## Mapa de etapas registrado

| Etapa | Conteúdo | Estado informado no histórico |
|-------|----------|-------------------------------|
| 0 | Cloudflare Access, JWT e agentes | Parcial; JWT não obrigatório |
| 1 | Leitura e inspeção da API | Concluída |
| 2 | Escrita e webhooks | Concluída |
| 3 | Kanban completo | Concluída nas sessões 003–004 |
| 4 | Tarefas e painel | Concluída na sessão 004 |

## Riscos e contexto de negócio

Os riscos incluíam duplicação de eventos, campos opcionais inconsistentes,
escritas parcialmente concluídas e diferenças entre respostas reais e
formato documentado. As medidas previstas eram idempotência, validação,
novas tentativas e `sync_pendiente`.

A equipe tinha menos de dez agentes em atendimento compartilhado, sem
responsável exclusivo por contato. Usava e-mail corporativo na Hostinger,
sem Google Workspace ou Microsoft 365. O Chatwoot era o CRM central e a
infraestrutura era própria, exposta pelo Cloudflare. A descrição original
de repositório privado sem registro externo foi superada nas sessões seguintes.
