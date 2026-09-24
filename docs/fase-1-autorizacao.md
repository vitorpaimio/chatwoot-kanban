# Fase 1 — autorização e ativação

Data: 23/09/2026. Implementação do plano 0.2.0 e decisões complementares do mantenedor.
A licença permanece MIT porque o campo de escolha veio sem preenchimento.

## Política implementada

- Sessão humana valida `/profile`; conta ativa no Chatwoot é obrigatória.
- Agente consulta `/inboxes` com seus próprios headers. Cache em memória, por
  conta/usuário/sessão, TTL de 60s contado do início da consulta. Expiração não usa
  resultado antigo diante de timeout, erro HTTP ou resposta inválida: retorna 403.
  Janela documentada de revogação: até 60 segundos; não há fallback para token técnico.
- Administrador vê os cartões da conta. Agente vê cartão cuja conversa vinculada
  esteja em uma caixa permitida. Sem conversa, administrador ou criador podem vê-lo.
  Cartões antigos sem autoria comprovada permanecem restritos ao administrador.
- Movimentos, histórico e agregações de cartões seguem o vínculo **atual**, inclusive
  consultas de períodos históricos. Trocar a conversa pode mudar quem vê o histórico.
- Contatos e tarefa compartilhada seguem a visibilidade CE de contatos da conta.
  Não se inferem permissões de cartão a partir do contato visível. Exportação Kanban
  contém somente agregações autorizadas; não foi criada exportação nativa de contatos.
- IDs inacessíveis e inexistentes retornam a mesma mensagem 404. Conta adulterada
  fora das associações da sessão retorna 403 antes da consulta ao recurso.

As views `kb_visible_cards` e `kb_visible_history` centralizam o filtro SQL.
`connection(user)` configura contexto somente na transação e verifica habilitação;
leituras de quadro, histórico, relatórios e métricas usam essas views. As views não
substituem autenticação nem são políticas RLS de acesso direto ao PostgreSQL.
Acesso SQL privilegiado continua sendo uma operação administrativa.

## Ativação e worker

Migração Alembic `006` adiciona habilitação da conta, solicitação separada de importação,
autoria do cartão e vínculo/fixação de conversa. A migração preserva habilitação das
contas existentes e aproveita conversa/caixa já conhecidas; não importa dados externos.

`PUT /kanban/activation?account=...` recebe `{"enabled": false}` ou `true`, somente
para administrador. Também está disponível na configuração da conta. A desativação
aguarda transações autorizadas em andamento; após confirmar, novas leituras/escritas,
webhooks e unidades de ativação/importação/sincronização/vencimento ficam bloqueadas.
A sessão continua disponível para o administrador consultar e reabilitar a conta.

Ativar provisiona a integração e o funil inicial, sem importar contatos nem criar
cartões. `/import` continua sendo uma ação administrativa separada e importa somente
metadados. Estimativa de volume e retomada detalhada permanecem na Fase 2.

## Conversa vinculada e SSE

O vínculo é por cartão, escolhendo maior `last_activity_at`; empate usa maior ID.
`PUT /cards/{id}/conversation` recebe `conversation_id` e `version`; ID nulo retorna
à seleção automática. O backend confere que a conversa pertence ao contato e à caixa
permitida. Pin não muda com outra conversa mais recente. Se a conversa desaparecer,
o vínculo é limpo de modo conservador; não permanece uma autorização antiga.
Sem conversa, o frontend não mostra canal nem atalho para contato como substituto.

Há um listener PostgreSQL por processo de API. Notificações por conta apenas acordam
assinantes candidatos. Cada stream compara uma revisão calculada sobre dados
visíveis; uma alteração exclusiva de cartão oculto não emite `change`, IDs ou payload.
Revalidação ocorre também no prazo do cache, sem depender de notificações. Desativação
ou falha de autorização encerra o stream. A interface limpa cartões/gráficos em
revogação/expiração; respostas de carregamentos antigos não restauram cartões.

O cálculo da revisão ainda percorre o conjunto visível. Não há certificação de volume:
paginação, coalescência adicional e benchmark continuam na Fase 3. Uma conexão
compartilhada reduz conexões, não comprova capacidade por si só.

## Corte direto de atributos

Código ativo escreve apenas `kanban_etapa`, `kanban_tarefa` e
`kanban_tarefa_vencimento` no contato. Não há segundo espelho na conversa nem escrita
dupla. API de tarefa recebe `descricao` e `vencimento`; GET da tarefa usa as mesmas
chaves. Banco e respostas históricas preservam identificadores internos existentes.

Foi antecipada a retirada do parser de atributos antigos de `refresh_contact`, pois
mantê-lo contrariaria o corte direto solicitado. O refresh atualiza metadados e
vínculos; divergência observada reenfileira o estado local, sem mover etapa ou fechar
tarefa. Reconciliação periódica e catálogo completo/manifesto continuam na Fase 2.

Migração opcional, exclusivamente para desenvolvimento e após backup:

```sh
python -m scripts.migrate_development_attributes --account 1 --dry-run
python -m scripts.migrate_development_attributes --account 1 --apply
```

O script lê as três chaves antigas dos snapshots locais de contatos, produz relatório
por ID sem valores pessoais/segredos e preenche somente lacunas. Conflitos com estado
local são bloqueados; não há sobrescrita automática. Após aplicação bem-sucedida,
remove as chaves antigas apenas do snapshot local e enfileira os espelhos novos;
não apaga definições ou atributos remotos. Repetição não duplica dados. O importador
histórico de banco legado continua separado: seus nomes espanhóis são colunas do
banco antigo, não leitura de espelhos pela aplicação ativa.

## Evidência nas duas versões reais

`tests/contracts/chatwoot_phase0.rb` foi ampliado e executado nas cópias CE isoladas:

| Versão | Commit | Resultado |
|---|---|---|
| 4.16.2 | `70e284a044f00326725f65f703162745371075ec` | 10 grupos aprovados |
| 4.18.0 | `9f920b549c14491a4e587687a3eed5d21c6ccc7d` | 10 grupos aprovados |

Nova prova: agente lista e consulta um contato identificado ligado a caixa da qual
não é membro, mas recebe 401 na conta alheia. A listagem normal distingue contatos
identificados de visitantes anônimos; isso é um filtro de produto, não ACL por caixa.
A tarefa compartilhada **não precisou adotar a regra do cartão**.

Fontes oficiais:
[ContactPolicy 4.16.2](https://github.com/chatwoot/chatwoot/blob/70e284a044f00326725f65f703162745371075ec/app/policies/contact_policy.rb),
[ContactsController 4.16.2](https://github.com/chatwoot/chatwoot/blob/70e284a044f00326725f65f703162745371075ec/app/controllers/api/v1/accounts/contacts_controller.rb),
[ContactPolicy 4.18.0](https://github.com/chatwoot/chatwoot/blob/9f920b549c14491a4e587687a3eed5d21c6ccc7d/app/policies/contact_policy.rb),
[ContactsController 4.18.0](https://github.com/chatwoot/chatwoot/blob/9f920b549c14491a4e587687a3eed5d21c6ccc7d/app/controllers/api/v1/accounts/contacts_controller.rb).

Os contratos usam Rails/PostgreSQL reais em modo test; não certificam proxy/Sidekiq
ou a instalação inteira. O novo teste Chrome do frontend usa API controlada,
explicitamente sem fingir ser certificação end-to-end do Chatwoot.

## Testes e decisões de implementação

A suíte negativa cobre GET/PATCH de cartão, criação/posição/vínculo indevidos,
histórico, relatórios, oito blocos de métricas em JSON e CSV, opções de caixa,
conta adulterada, conta desativada, webhooks, worker, cache, sessão, SSE, pin e tarefa.
Também cobre migração dry-run/conflito/repetição e ativação sem importação implícita.

Decisões tomadas na implementação: desempate de conversa por ID; preservar como
administrativos os cartões sem criador recuperável; rejeitar conflitos na migração;
aguardar unidades em andamento ao desativar; migrar o parser antigo junto do corte;
criar o GitHub privado até decisão de publicação. Não foram alteradas fontes do
Chatwoot, licença, tags ou manifests de implantação.

Repositório: [vitorpaimio/chatwoot-kanban](https://github.com/vitorpaimio/chatwoot-kanban).
Private Vulnerability Reporting foi escolhido, mas só pode ser habilitado quando
público; o TODO e o link de relato estão no SECURITY. Nenhuma release foi publicada.

Validação final: Ruff aprovado; **71 testes Python** aprovados em `kanban_test`;
**3 testes Node** aprovados; sintaxe de todos os JS/CJS aprovada; Chrome aprovou
cartão sem canal e limpeza da interface após revogação/expiração. A suíte Rails
real aprovou 10 grupos em cada versão CE. Fontes do Chatwoot permaneceram intactas.

## Arquivos alterados nesta sessão

- [CONTRIBUTING.md](../CONTRIBUTING.md)
- [README.md](../README.md)
- [SECURITY.md](../SECURITY.md)
- [app/database.py](../app/database.py)
- [app/events.py](../app/events.py)
- [app/main.py](../app/main.py)
- [app/metrics/queries.py](../app/metrics/queries.py)
- [app/metrics/service.py](../app/metrics/service.py)
- [app/reporting.py](../app/reporting.py)
- [app/routers/metrics.py](../app/routers/metrics.py)
- [app/routers/workspace.py](../app/routers/workspace.py)
- [app/security.py](../app/security.py)
- [app/services.py](../app/services.py)
- [app/static/kanban.js](../app/static/kanban.js)
- [app/static/metricas.js](../app/static/metricas.js)
- [app/worker.py](../app/worker.py)
- [docs/README.md](../docs/README.md)
- [docs/adr/030-autorizacao-caixas-ativacao.md](../docs/adr/030-autorizacao-caixas-ativacao.md)
- [docs/adr/README.md](../docs/adr/README.md)
- [docs/fase-1-autorizacao.md](../docs/fase-1-autorizacao.md)
- [docs/plano-0.2.0.md](../docs/plano-0.2.0.md)
- [docs/sesiones/023-2026-09-23-fase-1-autorizacao.md](../docs/sesiones/023-2026-09-23-fase-1-autorizacao.md)
- [docs/sesiones/README.md](../docs/sesiones/README.md)
- [migrations/versions/006_authorization.py](../migrations/versions/006_authorization.py)
- [scripts/migrate_development_attributes.py](../scripts/migrate_development_attributes.py)
- [tests/browser/authorization.cjs](../tests/browser/authorization.cjs)
- [tests/browser/live.cjs](../tests/browser/live.cjs)
- [tests/browser/outage.py](../tests/browser/outage.py)
- [tests/contracts/chatwoot_phase0.rb](../tests/contracts/chatwoot_phase0.rb)
- [tests/test_authorization.py](../tests/test_authorization.py)
- [tests/test_workspace.py](../tests/test_workspace.py)

## Ajustes após validação manual

A [sessão 024](sesiones/024-2026-09-23-correcoes-validacao-fase-1.md) e o
[ADR-031](adr/031-negociacoes-multiplas-edicao.md) acrescentam negociações múltiplas
por contato/funil, autorização de histórico por cartão, seleção de conversas sem
entrada de ID e estabilidade de edição durante SSE. A tarefa segue compartilhada
por contato/conta. A migração 007 é obrigatória antes de reiniciar os processos.
