# Sessão 040 — Funil / Etapa como lista editável

O mantenedor pediu que o atributo de contato "Funil / Etapa" fosse uma lista e
que trocar a opção no Chatwoot movesse o contato no Kanban. Decisão registrada no
[ADR-039](../adr/039-etapa-lista-editavel.md).

## Alterações

- `app/provisioning/attributes.py`: `kanban_etapa` passa a ser lista dinâmica;
  o plano aceita a definição antiga em texto.
- `app/services.py`: `stage_options`, `sync_stage_options` e `apply_remote_stage`;
  `refresh_contact` aplica a escolha somente quando chamado por webhook.
- `app/worker.py`: sincroniza as opções a cada ciclo e aplica a etapa nas entregas.
- `installer/resources.rb`: converte a definição em texto na instalação e na
  atualização.
- `tests/test_stage_list.py`: conversão, opções, movimento, criação, perda, eco,
  alteração local pendente e valor desconhecido.

## Validação

- Ruff e 202 testes Python aprovados no banco exclusivo (dois opt-in omitidos);
  testes JavaScript aprovados.
- Chatwoot local: a definição da conta 1 foi convertida para lista com 11 opções.
  Alterar o contato para `Funil principal / Ganho` pela API moveu a negociação,
  registrou `cartao_movido` com autor Chatwoot e deixou a sincronização em `synced`.
  Contato sem negociação ativa recebeu uma nova negociação na etapa escolhida.

## Próximos passos

- Validar a lista na tela do contato em homologação.
- Ensaiar a atualização do instalador numa instalação com a definição em texto.

## Menu de etapa da negociação

O campo "Etapa" da janela do cartão trocou o `<select>` nativo por um menu próprio
(`stageField` em `app/static/kanban.js`): cor da etapa, etapa atual marcada e selo
de Ganho/Perdido quando o nome não repete o tipo. Teclado: setas, Enter e Esc.
Validado no Chatwoot local movendo uma negociação de Ganho para Proposta enviada.

## Janela Gerenciar funil

A janela de gestão virou um painel: resumo do funil com Editar/Arquivar, lista de
etapas com cor, tipo, setas de ordem, editar e arquivar, criação rápida de etapa
(nome + Enter) e rodapé com Novo funil, Motivos de perda e Configuração da conta.
A edição de etapa usa paleta de cores com opção livre e seletor segmentado de tipo;
os campos numéricos de "Ordem" saíram das janelas de funil e etapa. Após salvar uma
etapa ou o funil, a janela de gestão reabre. Ações dentro dela forçam a recarga do
quadro, pois `load()` adia atualizações enquanto há janela aberta. Validado no
Chatwoot local: criar, reordenar, recolorir e arquivar uma etapa de teste.
