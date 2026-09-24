# ADR-035 — Instalador Swarm e ciclo de vida

- Data: 24/09/2026
- Estado: aceito e validado no ambiente definido abaixo.
- Relacionado: ADRs 021, 023, 029 e 033.

## Decisão

O pacote `installer` é uma ferramenta administrativa separada da API. Oferece
install/update/uninstall/status, dry-run e restauração do banco Kanban. Usa um
arquivo JSON sem credenciais, contexto Docker explícito, contas selecionadas e
confirmação nominal da rede overlay (`network_public` por padrão).

Suporte certificado: Swarm de nó único ARM64, PostgreSQL 16, Chatwoot CE 4.18.0
oficial e Traefik 3.7.13 com provider Swarm. A limitação a nó único é verificada no
preflight: volumes locais e `docker exec` não justificam inferir suporte multinó/HA.
A imagem Chatwoot não é reconstruída nem recebe alterações de código.

## Recursos e identidade

O catálogo da Fase 2 determina criação/reutilização/conflito. Conflito obrigatório
bloqueia antes de provisionar. O adaptador Rails realiza usuário, associações,
atributos, webhook e recibo em uma transação com bloqueio consultivo, eliminando a
janela entre criação e registro de propriedade. A seleção de contas é imutável;
instalações diferentes não podem gerenciar a mesma conta simultaneamente.

Cada instalação recebe usuário técnico dedicado, administrador somente nas contas
selecionadas. Não é AgentBot nem substitui a sessão humana. Token transita em
memória/pipes até cifragem no Kanban; não aparece em argv, logs ou temporários.
O recibo remoto `KANBAN_INSTALLER_V1` não contém segredos. A matrícula no Kanban
preserva a propriedade confirmada em `kb_resources` antes de iniciar o worker.

Stacks, volumes, secrets e configs têm identidade própria. Recursos preexistentes
sem propriedade confirmada não são adotados. O loader é compartilhado no Chatwoot:
remover uma instalação não o retira das demais; loader preexistente é preservado.
Na desinstalação, token é revogado imediatamente. Atributos são preservados por
padrão; purge exige confirmação de perda potencial de valores e só remove recursos
próprios que ainda correspondam ao recibo. Volumes e backups permanecem por padrão.

## Operação e recuperação

Manifesto local durável, diretório 0700 e arquivos privados; trava por instalação
impede operações simultâneas no mesmo estado. Backup cifrado do Chatwoot e do
Kanban, quando presente, precede alterações de recursos/esquema. Arquivos em claro
não são produzidos. Chave local de recuperação e cofre cifrado são preservados
junto ao estado; backup externo continua sendo responsabilidade operacional.

Update para a aplicação, espera conexão real de banco, aplica Alembic e aguarda a
nova tarefa de migração concluir. Falha mantém estado e recibos para repetição ou
restore. Restore para a aplicação, faz backup adicional e reconstitui apenas banco
e imagem Kanban. Não reverte automaticamente o Chatwoot compartilhado.
Status combina sonda API, ativação e heartbeat próprio do worker, verificando
inclusive réplicas desejadas iguais a zero para evitar confiar no heartbeat antigo.

`WEBHOOK_BASE_URL` opcional separa callback técnico da origem pública. Sem valor,
usa `PUBLIC_URL`. A validação de sessão/CSRF mantém a origem pública. No Swarm,
callback usa o DNS interno do serviço Kanban; o laboratório Chatwoot autoriza
requisições à rede privada. Labels de Traefik são somente do provider Swarm.

## Validação e limites

Duas instalações reais isoladas; repetição; conflito sem escrita; proxy nas duas
origens; worker parado/recuperado; atualização preservando configuração; imagem
indisponível e restauração; revogação HTTP 401; remoção repetida; purge de próprios
com preservação de preexistentes; reinstalação com volume retido; webhook nativo e
quadro com sessão humana. Evidências em `docs/phase4-evidence.json`.

O ensaio corrigiu corrida de DNS, conflito de labels Docker/Swarm e saúde durante
parada graciosa do worker. O roteiro registra os trechos retomados após correção.
TLS público, multinó, amd64, versão Chatwoot 4.16.2 neste adaptador e instalação por
terceiro não foram certificados aqui. Publicação segue a Fase 5 e Compose/Nginx a
Fase 4.2. Não ampliar a matriz de suporte com base apenas em testes unitários.

Por pedido explícito do mantenedor, o laboratório, backups/chaves de ensaio e os
pacotes Docker/Colima foram removidos após a certificação. Restam código, instruções
e evidências sem credenciais; o Chatwoot local anterior foi preservado.
