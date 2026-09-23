> Atualização da integração: os achados abaixo descrevem a versão anterior.
> Autenticação, isolamento, sincronização, webhooks, vencimentos e publicação foram
> substituídos nesta entrega. Consulte [a validação atual](validacao-integracao.md)
> e os ADRs 020–023 para evidências e limites.

# Auditoria técnica — 23/09/2026

## Resultado e alcance

A interface, as mensagens próprias e a documentação foram adaptadas para
português do Brasil. Foram corrigidas a inserção insegura de dados no HTML
e a interpretação de datas de vencimento na interface. **Permanecem problemas
importantes de autenticação e consistência no servidor.**

Revisão local de aplicação, SQL, testes, configuração Docker, workflows e
documentação. A pasta recebida não possui `.git`; não foi possível conferir
branch, alterações contra o histórico ou regras do repositório remoto.
Não houve implantação nem acesso a dados reais.

As prioridades abaixo indicam urgência técnica: P1 exige tratamento antes de
expor a aplicação sem controles externos confiáveis; P2 representa defeitos
funcionais ou de operação que devem ser corrigidos antes de depender do fluxo.

## Achados pendentes

### P1 — Identidade do agente não é autenticada pela aplicação

**Evidência:** [roteador Kanban](../app/routers/kanban.py), função `_get_actor`,
e [inicialização](../app/main.py). Não há dependência ou middleware de
validação JWT nas rotas. O cabeçalho de e-mail é aceito diretamente; quando
está ausente, a operação usa a identidade do bot, independentemente de `ENV`.
As configurações `CF_ACCESS_TEAM_DOMAIN` e `CF_ACCESS_AUD` não são consumidas
por um verificador.

**Impacto:** quem alcançar a origem pode consultar dados e realizar operações
usando o token do servidor; pode também informar outro e-mail para atribuição.
A exposição real depende das regras externas do Cloudflare e da rede, que
não foram verificadas. Os proxies `/api/*` e as rotas de diagnóstico também
não possuem autorização própria.

**Correção recomendada:** validar assinatura, emissor, audiência e validade
do JWT; derivar a identidade da credencial validada; proteger todas as rotas
sensíveis e restringir o acesso direto à origem. Definir autenticação própria
para chamadas automatizadas e webhooks.

### P1 — Sincronização de tarefas não possui recuperação confiável

**Evidência:** [banco](../app/database.py), `upsert_task`,
`get_pending_sync_tasks` e `cron_tick`; [roteador](../app/routers/kanban.py),
`_bg_sync_task_and_audit`.

- A inserção de uma tarefa usa o padrão `sync_pendiente = false`.
- A tarefa em segundo plano registra falha, mas não marca a linha como pendente.
- Edições e encerramentos marcam pendência; o sucesso em segundo plano não a limpa.
- O agendamento reenvia apenas o vencimento. Não reenvia a mensagem nem limpa
  os atributos de uma tarefa encerrada.
- Auditoria e envio executados após a resposta podem ser perdidos se o processo cair.

**Impacto:** uma criação pode ficar sem sincronização; um encerramento pode
ter sua data reposta no Chatwoot e, numa leitura posterior, voltar a ser ativo.
O sucesso HTTP da operação local não comprova sincronização externa.

**Correção recomendada:** gravar a intenção de envio e auditoria de modo
transacional, reenviar o conjunto completo conforme o estado da tarefa e
confirmar a versão sincronizada. Uma fila persistente ou tabela de saída
precisa suportar repetição segura e ordenação por contato.

### P1 — A leitura do quadro pode sobrescrever alterações locais ainda pendentes

**Evidência:** [roteador](../app/routers/kanban.py), `kanban_board`, e
[banco](../app/database.py), `batch_sync_tasks_from_chatwoot` e
`sync_task_from_chatwoot`.

A consulta do quadro grava os atributos retornados pelo Chatwoot no banco.
A sincronização não verifica `sync_pendiente`, versão ou data da alteração.
Atributos preenchidos reativam a tarefa; vazios podem encerrá-la.

**Impacto:** atualizar o quadro enquanto uma escrita externa está em andamento
ou falhou pode restaurar dados antigos, reabrir tarefas ou encerrar uma criação.

**Correção recomendada:** definir a autoridade dos dados e um protocolo de
reconciliação, respeitando alterações locais ainda não confirmadas e versões
externas. Evitar que uma simples leitura apague uma escrita mais recente.

### P1 — Garantias de autenticidade e processamento dos webhooks são incompletas

**Evidência:** [webhooks](../app/routers/webhooks.py), `_verify_signature`
e `contact_updated`.

Sem segredo configurado, a verificação retorna verdadeiro. O arquivo de
exemplo deixa o segredo vazio. Além disso, quando os dois atributos são
limpos, a condição que chama a sincronização não é satisfeita. O evento é
inserido antes de sincronizar; uma falha é registrada, mas a resposta continua
sendo de sucesso, e uma repetição é tratada como duplicada.

**Impacto:** eventos sem autenticação são aceitos quando a rota está acessível;
limpezas e falhas podem deixar a tarefa local desatualizada até outra leitura.

**Correção recomendada:** exigir a configuração apropriada no ambiente
exposto, validar o formato real dos eventos da versão integrada, processar
limpeza explícita e distinguir recebimento, processamento e falha para
permitir novas tentativas. A compatibilidade da assinatura com uma instância
real não foi validada nesta auditoria.

### P2 — O agendamento marca tarefas do dia como vencidas na mesma chamada

**Evidência:** [banco](../app/database.py), `cron_tick`, a partir da linha 324.
O primeiro UPDATE muda tarefas ativas com vencimento `<= CURRENT_DATE` para
`tarea_hoy`; o UPDATE seguinte transforma todas as `tarea_hoy` em
`tarea_vencida`, sem condição de data ou horário.

**Impacto:** chamar a rota no início do dia já marca essas tarefas como vencidas;
repetições não respeitam uma janela explícita. O cron externo às 23h30 não
está incluído no projeto, apenas descrito nos documentos.

**Correção recomendada:** definir o fuso e a regra de corte no servidor, testar
antes/no/depois do vencimento e separar tarefas do dia das efetivamente vencidas.

### P2 — Recriar tarefa encerrada preserva o estado de encerramento

**Evidência:** [banco](../app/database.py), `upsert_task`, a partir da linha 195.
A busca considera qualquer tarefa do contato, mas o UPDATE altera apenas
mensagem, data, conversa e pendência. Não redefine `estado`, `cerrado_por`
ou `cerrado_en`. A rota, por outro lado, decide entre criação e sobrescrita
usando `get_active_task`, que ignora encerradas e vencidas.

**Impacto:** uma solicitação anunciada como nova pode atualizar uma linha ainda
encerrada, com autoria antiga, e depender da leitura externa para reativá-la.

**Correção recomendada:** definir se a operação reabre, substitui ou cria novo
registro e atualizar estado, autoria e auditoria consistentemente.

### P2 — Operações concorrentes podem violar unicidade ou perder eventos

**Evidência:** [banco](../app/database.py), `get_or_create_agent`, `upsert_task`
e `batch_sync_tasks_from_chatwoot`; [webhooks](../app/routers/webhooks.py),
busca de duplicados seguida de INSERT.

Esses fluxos fazem SELECT e depois INSERT sem resolução atômica de conflito.
Duas chamadas podem observar ausência e competir pela mesma chave única.
A sincronização também pode adquirir outra conexão para criar o bot enquanto
já mantém uma conexão; com várias etapas simultâneas, isso pode saturar o pool.

**Correção recomendada:** usar transações e `INSERT ... ON CONFLICT` adequados,
reutilizar a conexão quando necessário e testar concorrência com PostgreSQL real.

### P2 — Publicação não depende dos testes em pushes diretos

**Evidência:** [.github/workflows/test.yml](../.github/workflows/test.yml) usa
`pull_request`; os dois workflows de publicação usam `push` e não dependem
do resultado dos testes.

**Impacto:** um envio direto para `develop` pode publicar código que não passou
pelas verificações. A afirmação antiga de que todo envio roda testes antes
da imagem não corresponde aos arquivos presentes.

**Correção recomendada:** fazer a publicação depender de testes do mesmo commit,
ou exigir PR e verificações obrigatórias para todas as branches publicadas.
As regras externas do GitHub não foram consultadas.

### P2 — Migração antiga, limites e histórico precisam de revisão

**Evidência:** [banco](../app/database.py), `_migrate_schema` e
`get_audit_history`; [roteador](../app/routers/kanban.py),
`kanban_stats_history`; [painel](../app/templates/dashboard.html).

A migração adiciona `contact_id`, mas não preenche a associação de tarefas
antigas; as rotas `/migrate/*` citadas no histórico estão ausentes. O parâmetro
`limit` do histórico não possui limite máximo nem validação de valor negativo.
O painel ainda mostra `conversation_id`, embora tarefas novas sejam de contatos.

**Correção recomendada:** recuperar e validar a migração antes de atualizar
uma base antiga, limitar paginação e incluir o contato no histórico.

## Corrigido nesta sessão

- **Injeção de HTML:** nomes de contatos, etapas, mensagens, imagens e links
  tinham inserções sem escape adequado. As inserções tratadas agora escapam
  aspas e caracteres HTML; URLs aceitam somente HTTP/HTTPS. Testes com conteúdo
  malicioso confirmaram ausência de atributos executáveis nesses caminhos.
- **Datas brasileiras:** `YYYY-MM-DD` era interpretado como UTC e podia virar
  o dia anterior em São Paulo. Datas de tarefa agora são construídas como
  calendário local e exibidas em `pt-BR`.
- **Erros da interface:** configuração e painel verificam o status HTTP;
  atualizar sem quadro montado não tenta acessar um elemento ausente.
- **Dependência visual:** removido o script CDN Tailwind sem uso no Kanban.
- **Segredo em documentação:** removido da sessão de 20/07. Caso ainda seja
  usado, é necessário substituí-lo no emissor e no receptor; não houve acesso
  a esses serviços para fazer a substituição.
- **Documentação:** corrigidas alegações de JWT implementado, testes antes
  de qualquer publicação, implantação para múltiplas arquiteturas e
  disponibilidade da demonstração completa. O README ausente foi criado.

## Tradução e compatibilidade

Textos da interface, mensagens próprias, resumos de rotas, instruções,
convenções, ADRs, sessões e legendas foram revisados em português. Cinco
capturas foram regeneradas. Nomes técnicos, contratos externos e valores
persistidos foram preservados. Dados cadastrados no Chatwoot não foram alterados.
Mensagens de terceiros podem continuar em outro idioma.

## Evidências de validação

- Python 3.12 em ambiente temporário: **31 testes pytest aprovados**.
- Node.js: **5 testes aprovados**, incluindo regressões de data e escape HTML.
  Os testes de escape e estado do dia reproduziram falhas antes da correção.
- `ruff check .` e `ruff format --check .`: aprovados.
- Navegador Chromium/Chrome isolado: quadro com oito contatos, modal e painel,
  temas claro e escuro, cinco capturas; nenhum erro JavaScript nos fluxos
  verificados e nenhuma execução do conteúdo malicioso usado no teste.
- Respostas de API no navegador foram simuladas. Não houve PostgreSQL real,
  Chatwoot real, Docker, Cloudflare ou Arcane durante a verificação.

Os testes existentes substituem banco e API por simulações; não comprovam as
propriedades transacionais ou a recuperação de falhas apontadas acima.
Há avisos de descontinuação de configuração do Pydantic, integração do
TestClient com httpx e configuração do escopo de fixtures assíncronas.

## Limitações e sequência recomendada

Não foi feita varredura de vulnerabilidades das dependências, teste de carga
nem revisão de permissões e exposição do ambiente remoto. `LICENSE` está
ausente, embora o histórico declare intenção de licença MIT; é preciso
recuperar o documento original e sua atribuição antes de redistribuir.

A próxima etapa técnica deve priorizar autenticação, sincronização durável
e testes de integração com PostgreSQL e a versão efetivamente usada do Chatwoot.
