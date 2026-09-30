# Sessão 048 — Contato removido e disponibilidade da API

## Problema

Relatório de produção: um contato apagado com sincronização pendente recebia 404
indefinidamente; a degradação de `/health` causava reinícios da API pelo Swarm e
indisponibilidade de todas as contas. A intervenção manual não removia o card órfão.

## Avanços

- Sonda da imagem em `/health/live`, independente de falhas de negócio.
- Confirmação de contato ausente por GET e validação de acesso à conta antes de
  remover cartões do quadro, fechar tarefas e encerrar filas em `gone`.
- Limite de dez falhas nas filas de sincronização e entregas, estado `dead`,
  histórico e retomada manual explícita. Estados terminais não são reprocessados.
- Reconciliação remove cartões órfãos com preservação do histórico. Não foi adicionada
  assinatura `contact_deleted`, não suportada pelo modelo Webhook do Chatwoot local.
- ADRs 022 e 023 atualizados; esquema preservado e código do Chatwoot inalterado.

## Validação

- Ruff: aprovado em app, instalador, migrations, scripts, tests e deploy.
- Validação final com PostgreSQL exclusivo `kanban_test` e os dois cenários Rails:
  253 testes passaram; um contrato opt-in de outro ambiente foi ignorado.
- Contrato Rails real executado separadamente em `kanban_phase0_cw4162_test`, com
  remoção do contato, PATCH/GET reais retornando 404, estado `gone` e card excluído.
  As fixtures Rails são revertidas por rollback.
- Sintaxe JavaScript aprovada; cinco testes da interface passaram.
- Regressões incluem isolamento entre contas, falha na confirmação, limite de
  tentativas, retomada manual, conversa ausente e rollback da limpeza se o histórico falhar.

## Próximos passos

Publicar e implantar a imagem testada pelo fluxo do projeto. Após implantação,
confirmar a nova sonda no Swarm e a limpeza do card órfão pela reconciliação.
A produção não foi alterada nesta sessão. A observação sobre usuário técnico na
conta 9 permanece fora desta correção e exige investigação própria.

## Complemento — identificação por e-mail no widget

O usuário relatou dois cartões, um após a mensagem inicial e outro após informar
o e-mail. O contrato Rails reproduziu um mecanismo compatível: a ação
`ContactIdentifyAction` une o contato temporário a um contato com e-mail existente,
remove o temporário e copia os atributos do Kanban. Ao processar o contato definitivo,
o atributo de etapa pode gerar seu cartão, coexistindo com o cartão órfão antigo.

Foi acrescentada uma variante ao contrato real: comprova os dois cartões antes da
reconciliação e somente um cartão ativo depois, mantendo o histórico do anterior.
As duas variantes Rails (exclusão e identificação) passaram. Não houve nova mudança
no produto: a correção de reconciliação desta sessão cobre esse caso. A duplicação
pode ser transitória até a varredura; não se deduplicam contatos por nome/e-mail nem
se promete eliminação imediata. Confirmar os IDs/eventos da conta afetada continua
necessário para atribuir o incidente de produção a esse mecanismo.
