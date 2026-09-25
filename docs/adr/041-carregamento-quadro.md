# ADR-041 — Carregamento rápido do quadro

Estado: aceito em 25/09/2026.
Altera a validação de sessão do ADR-020 e o responsável exibido no cartão.

## Contexto

O quadro demorava a abrir. A medição no Chatwoot local mostrou:

- cada chamada ao Kanban revalidava a sessão em `GET /api/v1/profile`, cerca de
  80% do tempo da chamada;
- a abertura fazia `session`, depois `board?limit=1` sem funil (totalizando todos
  os cartões da conta só para descobrir os funis), depois o quadro do funil;
- o ícone de canal buscava uma conversa no Chatwoot por cartão;
- todos os arquivos saíam com `Cache-Control: no-store`, inclusive `kanban.js` e
  o Chart.js das métricas;
- sair do Kanban destruía o iframe, e voltar recomeçava do zero.

Também foi relatado cartão com responsável antigo: o Kanban usava a conversa com
atividade mais recente, mesmo resolvida.

## Decisão

- Sessão: o perfil do Chatwoot fica em cache por credencial durante
  `SESSION_CACHE_SECONDS` (30 s; 0 desliga). Só respostas válidas são guardadas;
  conta, papel e caixas continuam verificados a cada chamada. Uma sessão encerrada
  no Chatwoot ainda é aceita por até esse prazo, na mesma ordem do cache de caixas
  (60 s) já existente.
- Quadro: sem `funnel_id`, `GET /kanban/board` abre o funil principal e informa
  `funnel_id`. A interface lembra o último funil por conta em `localStorage` (só o
  identificador) e pede quadro e sessão em paralelo na primeira abertura.
- Canal: uma consulta `/inboxes` por abertura, cruzada com `conversation_inbox_id`.
- Arquivos: as páginas citam cada arquivo com `?v=` (data e tamanho); com versão,
  `public, max-age=31536000, immutable`; sem versão e `loader.js`, `no-cache`;
  páginas e API continuam `no-store`.
- Loader: ao sair, o painel é escondido e mantido; voltar à mesma página mostra o
  quadro na hora. Oculto, o Kanban fecha o SSE; ao reaparecer, reconecta e
  atualiza. Só a última página fica guardada.
- Responsável: conversa aberta ou pendente vence a resolvida; depois, atividade
  mais recente.

Dados de contatos não são guardados no navegador.

## Consequências

- Abertura no local: dados do quadro em ~50 ms (antes ~360 ms em cascata);
  reabertura em poucos milissegundos.
- Logout ou perda de acesso no Chatwoot leva até 30 s para valer no Kanban.
- Ao reaparecer, o quadro pode mostrar dados antigos por um instante até a
  atualização.
- Em desenvolvimento, alterar um arquivo estático muda a versão na próxima
  abertura da página.

Ver [sessão 042](../sesiones/042-2026-09-25-carregamento-quadro.md).
