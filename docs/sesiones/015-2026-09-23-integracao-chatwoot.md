# Sessão 015 — Kanban instalado dentro do Chatwoot

Data: 23/09/2026. Objetivo autorizado: integração interna na instalação 4.16.2,
mesmo endereço localhost:3000, português do Brasil, múltiplas contas e funis.

## Implementação

- Backend reestruturado em sessão/autorização, serviços, rotas autenticadas e worker.
- Migrações Alembic 001–003, referências compostas e importação legada com backup obrigatório.
- Loader idempotente e Dashboard App, sem modificações no código do Chatwoot.
- Interface pt-BR com quadros, filtros, tarefas, configuração, histórico e relatórios.
- Webhooks HMAC, deduplicação, reconciliação do estado atual, fila persistente e SSE.
- Nginx/Overmind locais; Swarm/Traefik e publicação multiarch preparados sem implantação.

## Instalação local

Ruby 3.4.4 e dependências do Chatwoot estavam prontos. O banco existente foi preservado,
sem novo seed. Foram criados kanban_development e kanban_test e um backup do Chatwoot.
Duas contas existentes foram ativadas e receberam webhook e Dashboard App sem duplicação.
O token de serviço foi enviado diretamente pela sessão administrativa e guardado cifrado;
a exportação temporária de tokens foi descartada após a revisão automática.

Uma variável DATABASE_URL herdada pelo Overmind inicialmente apontou Rails para o banco
Kanban; os scripts agora removem explicitamente as variáveis Kanban antes de iniciar Rails,
Sidekiq e Vite. Não foi carregado seed/esquema do Chatwoot no banco Kanban.

Conexões SSE revelaram que o encerramento padrão do proxy inicial e Uvicorn poderia
esperar indefinidamente. A execução passou a usar prazos limitados de encerramento e reconexão.

## Evidências

Ver [validação da integração](../validacao-integracao.md), que registra os testes reais,
resultado final e limites da preparação de infraestrutura. Capturas em `.local` são locais,
geradas contra o Chatwoot em execução, sem credenciais e sem dados simulados na API.

O proxy final é Nginx: a versão Caddy 2.11.4 instalada remove cabeçalhos com underscore
antes do roteamento. Para preservar a API original do Chatwoot, Nginx permite esses
cabeçalhos e não possui autenticação delegada que confunda aliases de cabeçalhos.
