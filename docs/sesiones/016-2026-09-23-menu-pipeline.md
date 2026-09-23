# Sessão 016 — Menu Pipeline nativo

Implementação do ADR-024: grupo Pipeline depois de Contatos, filhos Kanban e
Métricas, SVGs Lucide, expansão persistente, destaque ativo/restauração, suporte
recolhido, troca de conta, temas e reinjeção. Nenhuma alteração no código do Chatwoot.
A página Métricas está intencionalmente vazia, com título e botão de fechamento.

Validação automatizada: `tests/browser/sidebar.cjs` usa o Chatwoot 4.16.2 real,
compara medidas e hover com elementos nativos e grava capturas com o painel fechado:
`.local/pipeline-light.png`, `.local/pipeline-dark.png` e versões `-recolhido.png`.
Também verifica estados ativos, restauração, teclado, localStorage, recriação,
fallbacks de posição, duas contas e primeira carga com menu recolhido.

Para repetir, usar `PLAYWRIGHT_MODULE` se Playwright não estiver instalado no projeto.
Opcionalmente `CHATWOOT_BROWSER_STATE` aponta para um storageState local protegido,
evita acumular sessões; o teste não imprime credenciais. Sem ele, usa login do seed
local ou `CHATWOOT_LOGIN_EMAIL`/`CHATWOOT_LOGIN_PASSWORD`.

As suítes anteriores de navegador foram ajustadas para abrir Pipeline quando fechado.

Resultado: testes de navegador aprovados, 20 testes Python e 3 testes JavaScript
aprovados; Ruff e formatação aprovados. Medidas comparadas nos dois temas:
fonte 14 px, linha 20 px, cabeçalho 32 px, espaçamento 8 px, ícones 16 px,
padding 4 × 6 px e raio 8 px. Cor e hover correspondem aos grupos nativos
inativos; o grupo Conversas mantém seu destaque quando a rota dele está ativa.
Foi incluído ResizeObserver para acompanhar o arraste da largura do sidebar.
