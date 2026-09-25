# ADR-043 — Fluxo de ativação e referência visual no Chatwoot 4.18

Estado: aceito em 25/09/2026.
Atualiza a versão de referência dos ADRs 024 e 025; mantém o ADR-020.

## Contexto

A [auditoria de UX](../auditoria-ux-2026-09-25.md) comparou o Pipeline com o
Chatwoot CE 4.18.0. Os ADRs 024 e 025 e `tests/browser/board-design.cjs` foram
validados na 4.16.2. Na ativação, a auditoria encontrou quatro problemas:

- o quadro, os filtros e "Adicionar negociação" ficavam habilitados antes de a
  conta estar pronta (UX-01);
- a engrenagem mostrava o erro cru "Conta não provisionada" (UX-03);
- o texto de ativação misturava "Ativar", "Provisionar conta" e
  "Token de serviço", sem dizer onde obter o token (UX-10 a UX-13);
- o ponto de status ficava amarelo, reconectando, numa conta sem ativação
  (UX-06).

## Decisão

A referência visual e textual passa a ser o **Chatwoot CE 4.18.0**, commit
`9f920b5`: componentes de `components-next`, tokens `n-*` e textos pt-BR. As
decisões dos ADRs 024 e 025 continuam valendo; só a versão usada como referência
e para validação muda.

Enquanto a conta não estiver pronta (`activation_status` diferente de `ready`,
ou conta desativada), o Pipeline mostra **somente o painel de ativação**, abaixo
de um cabeçalho com o título "Pipeline". Barra de ferramentas, resumo, quadro,
engrenagem e ponto de status ficam ocultos, e a conexão em tempo real só abre
quando a conta fica pronta. O painel tem um estado para cada situação:

| Situação | Título | Conteúdo |
|---|---|---|
| Sem ativação, administrador | Ative o Pipeline nesta conta | Campo "Token de acesso", ajuda com o caminho no Chatwoot e botão "Ativar Pipeline" |
| Sem ativação, agente | O Pipeline ainda não está ativo nesta conta | Orientação para pedir a um administrador |
| `pending` sem erro | Configurando o Pipeline… | Indicador de progresso; atualização a cada 5 s |
| `pending` com erro | Não foi possível concluir a configuração | Motivo e aviso de nova tentativa automática; para administrador, "Abrir configurações" e "Tentar novamente" (principal) |
| `failed` | Não foi possível concluir a configuração | Motivo; para administrador, "Tentar novamente" e "Abrir configurações" (principal) |
| Desativada, administrador | Reative o Pipeline nesta conta | O mesmo formulário do token, com botão "Reativar Pipeline"; funis, etapas e negociações continuam salvos. Antes, a janela de configuração abria sozinha |
| Desativada, agente | O Pipeline está desativado nesta conta | Orientação para pedir a reativação a um administrador |

Reativar é só informar o token de novo: `POST /activate` já religa a conta
(`enabled = true`) e refaz a configuração, sem passar pela janela de
configuração. Um 403 recebido ao recarregar o quadro (conta desativada em outra
aba) faz a página consultar `/session` de novo e mostrar o painel, em vez de
exibir a mensagem crua "Conta não habilitada para o Kanban".

O painel segue os componentes do Chatwoot 4.18:

- **Cartão:** `solid-2`, contorno `border-container`, raio de 12 px, largura
  máxima de 512 px, como o `Dialog` `max-w-lg`.
- **Tipografia:** título em `text-heading-1` (18 px, peso 520) e texto em
  14 px `slate-11`.
- **Campo:** 40 px com fundo `black-alpha-2`, como o `Input` `md`.
- **Ajuda e erro:** 12 px abaixo do campo. Erros de token aparecem junto do campo,
  com `aria-invalid`, e não no aviso global.
- **Botões:** 40 px; a principal é azul e fica à direita, como no rodapé do
  `Dialog`.

O erro de contraste usa `ruby-11`, e não o `ruby-9` do `Input`, por
acessibilidade. O contorno de foco de 2 px do Pipeline também continua.

## Consequências

- Não é mais possível abrir janelas, criar negociações ou gerar o erro
  "Conta não provisionada" pela interface antes da ativação.
- "Token de serviço" passa a se chamar "Token de acesso" também na janela de
  configuração. Os textos de "Configuração da conta" (UX-15 e UX-16) continuam
  como estão.
- Os avisos "Provisionamento: …", "Ativação agendada…", "Kanban desativado…" e
  "Peça a um administrador…" deixam de usar `#notice`, que continua para as
  outras mensagens (UX-07).
- `tests/browser/activation.cjs` cobre os estados com a API controlada, e
  `tests/browser/phase2.cjs` passa a esperar o painel. Os testes de design com o
  Chatwoot real (`board-design.cjs` e `sidebar.cjs`) ainda precisam ser rodados
  na 4.18.

Ver [sessão 043](../sesiones/043-2026-09-25-auditoria-ux-pipeline.md).
