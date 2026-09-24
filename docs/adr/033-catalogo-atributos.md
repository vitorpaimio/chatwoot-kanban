# ADR-033 — Provisionamento e recuperação por conta

Estado: aceito e implementado na Fase 2, 23/09/2026.
Complementa ADR-022, ADR-029 e ADR-030.

## Decisão

`app/provisioning/attributes.py` é o catálogo único dos três espelhos obrigatórios
(etapa, tarefa, vencimento) e três dimensões opcionais (origem, campanha,
temperatura). Cada definição inclui modelo, tipo, chave, nome, descrição,
obrigatoriedade e valores permitidos de lista. Identidade inclui conta e modelo.

O provisionador consulta definições e valida todos os obrigatórios antes de criar
recursos. Reutiliza tipos/modelos compatíveis sem modificar metadados preexistentes.
Uma chave em contato e conversa é válida se a definição de contato é compatível;
somente em conversa bloqueia a chave obrigatória. Lista de temperatura exige
Frio/Morno/Quente, preservando valores extras de uma definição compatível.

Novas contas começam com opcionais desligados. Contas anteriores preservam os
mapeamentos canônicos que já eram lidos pelas métricas. Administradores podem
configurar outra chave ou desligar cada dimensão. Conflito opcional desliga a
dimensão e registra diagnóstico, sem modificar a definição remota. Os triggers
consultam o mapeamento ao importar/atualizar contatos e capturar eventos de cartões;
eventos históricos permanecem imutáveis. A reconciliação atualiza dimensões dos
cartões existentes em lotes após uma mudança de mapeamento.

## Manifesto e falhas parciais

`kb_resources` registra ID remoto, tipo, chave, definição sem segredos e propriedade
`created`/`preexisting`. Cada atributo confirmado é persistido separadamente;
webhook/segredo cifrado são confirmados antes da limpeza da antiga Dashboard App.
Falha posterior não desfaz o manifesto já confirmado. Repetição consulta o remoto
novamente e não duplica atributos, webhook ou funil.

Falha de transporte entre criação remota e confirmação local não permite provar
propriedade: ao reencontrar o recurso sem recibo, registrar como preexistente.
Também perder propriedade quando um ID remoto é substituído. Isso privilegia
preservação em eventual desinstalação. Nenhuma definição é apagada nesta fase.

## Estados, importação e autoridade

Habilitação, provisionamento e importação têm controles separados. Conta desativada
não processa trabalho; conta com provisionamento pendente/falho não libera dados.
Provisionamento não importa contatos nem cria negociações.

Importação exige estimativa prévia, modo explícito (metadados, padrão; ou criação
de negociações ausentes no funil/etapa aberta escolhidos) e registra autor/destino.
Guarda página e IDs recebidos antes de processar. `kb_import_seen` confirma um recibo
por contato junto com as mutações locais, histórico e fila. O resumo da conta é
atualizado depois do commit, evitando inversão entre bloqueios da conta e contato.
Se houver queda nesse intervalo, repetir o ID consulta o recibo e recompõe o total.
Não recriar negociações excluídas: existência anterior no funil já impede duplicação.
Um 404 registra ausência e deixa a importação continuar; não exclui estado local.

A paginação usa criação em ordem crescente e elimina IDs repetidos. É leitura de
uma lista viva, não snapshot remoto: exclusões concorrentes podem deslocar páginas;
nova importação explícita cobre contatos que ficaram fora do percurso. Não há
importação automática de todo o diretório pelo GET do quadro.

Etapa e tarefa são exclusivamente locais. A reconciliação percorre contatos locais
em lotes, com cursor, e reinicia cinco minutos após terminar uma passagem. Webhook
perdido converge mesmo sem nova entrega. Divergência reenfileira projeção; eco
compatível não altera etapa/tarefa nem reenfileira. Inclui tarefa sem cartão.

## Operação

Um advisory lock por conta serializa workers e alterações de configuração; cada
contato usa a ordem de bloqueios de funil/contato e transação local. Orçamento padrão
é dez unidades por fila e conta por ciclo, configurável entre 1 e 100. Vencimentos,
webhooks, importação, reconciliação e projeções respeitam esse limite.

Retentativa usa atraso exponencial limitado. 429 respeita Retry-After (segundos ou
data HTTP, limitado a uma hora); 401/403 pausam chamadas remotas da conta por cinco
minutos, com diagnóstico para troca do token. Outras contas continuam. Trocar o
token limpa a pausa. Não registrar corpo HTTP, headers ou mensagens que contenham
credenciais.

`/health` verifica banco, filas pendentes/falhas/atrasos e heartbeat. `/health/worker`
expõe apenas disponibilidade; `python -m app.health worker` verifica o próprio
host/container. Heartbeat vence após 120 segundos e é renovado entre unidades,
inclusive com fila vazia. Compose e stack usam a sonda própria do worker.

## Migração e verificação

Alembic 009–011 adiciona manifesto, estados, checkpoints, mapeamentos e heartbeat;
não cria tabelas no startup nem remove dados legados. Downgrade de 009 exige backup,
pois remover manifesto/checkpoints perde informação operacional. Mantenha as
adições ao reverter o aplicativo; não reimplante um worker antigo em importação ativa.

Ver [evidências da Fase 2](../fase-2-provisionamento-recuperacao.md) e
[sessão 028](../sesiones/028-2026-09-23-conclusao-fase-2.md).
