# Plano da release pública 0.2.0

Data: 23/09/2026. Decisões do mantenedor incorporadas antes da Fase 0.
Não reutilizar tags anteriores. Este plano não altera a versão publicada do pacote.

## Contratos aprovados

- Sessão humana do Chatwoot identifica o autor. Usuário de serviço autentica apenas
  operações técnicas e não é AgentBot nem substituto da identidade humana.
- Administradores veem a conta inteira. Agentes só poderão acessar cartões cuja
  conversa vinculada esteja em caixas autorizadas obtidas com sua própria sessão.
  Validar se `GET /inboxes` realmente retorna esse conjunto nas duas versões.
  Se o contrato falhar, a 0.2.0 será restrita a administradores.
- A autorização abrange leitura, escrita, exportação, histórico, métricas e SSE.
  Cache proposto: cinco minutos, por conta e usuário. Definir revogação e acesso a
  tarefas compartilhadas antes da Fase 1. Cartão sem conversa não satisfaz a
  política de acesso de agentes; administrador pode vê-lo.
- Conversa vinculada: maior atividade, salvo fixação explícita por cartão.
  Sem conversa: sem canal e sem atalho. Não substituir por atalho ao contato.
- Etapa e tarefa têm autoridade exclusivamente local. Atributos são espelhos;
  divergências reenfileiram a projeção, sem movimentar cartão ou fechar tarefa.
- Criação manual por padrão. Importação opcional, separada, com estimativa prévia;
  distinguir importar metadados de criar cartões e registrar a escolha.
- Uma tarefa ativa por contato/conta; responsável inicial é o criador, editável.
  Alteração do responsável da conversa não reatribui automaticamente a tarefa.
- Primeiro adaptador: Docker Swarm + Traefik, rede padrão `network_public`
  configurável. Segundo: Compose + Nginx. Portainer é gerenciador da stack.
- Instalador cria usuário de serviço dedicado, administrador somente nas contas
  selecionadas; plano explícito, manifesto e revogação na desinstalação.
  Token cifrado no Kanban, nunca em logs, argumentos ou temporários.
- Brasília e BRL. Certificação: 20.000 contatos, 5.000 cartões por conta e 30
  usuários simultâneos. Cenário de carga deve incluir agentes e administradores.

## Fases e critérios de conclusão

### Fase 0: contratos, evidências e correções imediatas

Escopo desta sessão. Ler os contratos oficiais das tags 4.16.2 e 4.18.0 e testar
na instância real quando disponível. Separar evidência estática de prova operacional.

Itens: sessão, `/profile`, `/inboxes` com sessão de agente, atributos, webhooks,
`DASHBOARD_SCRIPTS`, prioridade, automações com atributos de contato e provisionamento
de usuário. G5/G6, Q3/Q5/Q6/Q9 e preparação de N1–N3.

Correções autorizadas: retirar storageState persistido de board-design; retirar
credenciais fixas de README/testes; declarar SQLAlchemy e retirar httpx duplicado;
retirar AUTH duplicado; atualizar SECURITY e CONTRIBUTING.

Arquivos: requisitos, `app/routers/workspace.py`, `tests/browser/*`, README,
SECURITY, CONTRIBUTING, este plano, relatório de contratos, ADR e sessão.
Pronto: evidências identificadas por versão, lacunas explícitas e Ruff/pytest/JS
aprovados. Falta de instância real não pode ser apresentada como contrato validado.
Não implementar nesta fase autorização nova, espelhos novos, instalador ou healthchecks.

### Fase 1: autorização, ativação e vínculo de conversa

Itens: G5/G6, Q3/Q6/Q9. Implementar somente a política aprovada após o gate da Fase 0.
Arquivos: `app/security.py`, `app/routers/workspace.py`, `app/routers/metrics.py`,
`app/services.py`, interface e nova migração de habilitação/vínculo.
Pronto: conta desativada bloqueia dados e trabalho; autorização cobre todos os
recursos; conversa fixada não muda por nova atividade; tarefas não vazam entre funis.
Testes: duas contas, caixas disjuntas, revogação, usuário suspenso, escrita/CSV/
histórico/métricas/SSE e cartões sem conversa. Cache nunca usa token de serviço
para descobrir permissões do agente.

### Fase 2: autoridade, recuperação e provisionamento de atributos por conta

Itens: G6, base de G4/G7 e de A1 futuro. Separar provisionar, importar e habilitar.
Arquivos: `app/services.py`, `app/worker.py`, `app/chatwoot_client.py`,
`app/database.py`, novas migrações, configurações da conta e métricas.

Criar nesta fase `app/provisioning/attributes.py` como catálogo único: chave,
modelo, tipo, nome exibido, descrição e obrigatoriedade. Contato obrigatório:
`kanban_etapa` (texto, Funil / Etapa), `kanban_tarefa` (texto),
`kanban_tarefa_vencimento` (data). Contato opcional: `origem`, `campanha` (texto),
`temperatura` (lista Frio/Morno/Quente). Conversa opcional: `kanban_etapa` (texto),
dependente da decisão sobre o segundo espelho.

Consultar definições por conta antes de escrever. Registrar cada recurso no
manifesto como criado ou preexistente. Reutilizar apenas modelo/tipo compatíveis;
conflito obrigatório falha a ativação da conta com diagnóstico; conflito opcional
pede mapeamento ou desliga o recurso. Não alterar definições alheias.
Mapeamentos opcionais configuráveis por conta, usados por importação, snapshots e
métricas. Distinguir a mesma chave permitida nos modelos contato e conversa de
uma definição encontrada apenas no modelo errado. Nenhuma renomeação na Fase 0.

Pronto: divergência externa só reescreve espelho; webhook perdido converge;
importação retoma; ativação repetida não duplica recursos. Health de API verifica
banco e estado da fila; heartbeat próprio permite detectar worker parado sem
confundir fila vazia com falha. Implementar limites de processamento por conta.
Testes: conta vazia, definições iguais, conflito obrigatório/opcional, mapeamento,
repetição, falhas parciais, credencial revogada, 429, 404, eco e recuperação.

### Fase 3: quadro mínimo, métricas locais e capacidade

Itens: Q1–Q4, Q6–Q10, A7, G3/G4/G7. Q5 pode seguir como melhoria posterior.
Arquivos: interface, consultas W/M, eventos, índices e testes de carga.
Pronto: paginação/filtros no servidor, totais completos, tempo na etapa, responsável
da tarefa editável, SSE com orçamento de conexões e invalidação autorizada;
certificação medida no volume aprovado. Estabelecer hardware e metas de latência
antes do ensaio. Sem replicar atendimento nativo não certificado.
Testes: teclado/toque, conflito, reconexão, rascunhos, carga por conta e 30 sessões,
consistência de totais e métricas. Se acesso direto móvel for aprovado, tema padrão
fora de iframe e navegação própria entram aqui.

### Fase 4: instalador Swarm/Traefik e ciclo de vida

Itens N1/N2/N3/G6. Arquivos novos de instalador/adaptadores/manifesto e templates;
`deploy/stack.yml`, scripts de provisionamento administrativo e documentação.
Pronto: install/update/uninstall/status e dry-run idempotentes; backup antes de
escrever; usuário de serviço registrado/revogado; healthchecks de API e worker;
rede `network_public` detectada e confirmada, sem alterar imagem do Chatwoot.
Dry-run lista por conta atributos criados, reutilizados ou bloqueados.
Uninstall preserva atributos por padrão; nunca apaga preexistentes. Somente
`--purge-attributes` confirmado pode remover definições próprias, informando perda
potencial de valores. Não imprimir nem serializar tokens em temporários.
Testes: Swarm real descartável, duas instalações, repetição, backup/restauração,
falha intermediária, proxy, health do worker, atualização e desinstalação.
Compose/Nginx é o próximo adaptador, sem atrasar certificação do primeiro.

### Fase 5: gate e publicação 0.2.0

Arquivos: workflows, Dockerfile, versão do pacote, CHANGELOG, README, SECURITY,
licença, guias e matriz de compatibilidade.
Pronto: testes do mesmo commit, imagens por digest, release nova, restauração
ensaiada e instalação por terceiro em ambiente suportado. Não declarar contrato
real validado com base somente em testes simulados ou leitura de código.
Testes: Ruff, PostgreSQL exclusivo, JS, navegador CE nas duas versões, Swarm,
arquiteturas publicadas e carga certificada. Licença/canal privado resolvidos.

## Roadmap após 0.2.0

1. **A1 primeiro:** card automático opt-in por funil/caixa, sem retroatividade implícita.
2. Q5 e modelos G1; segundo adaptador Compose/Nginx.
3. A2 via Dashboard App, I2 API pública e I1 webhooks de saída com fila própria.
4. G2 em demonstração isolada, I3 e exemplos externos I4.
5. A3 somente com contrato de resolução/reabertura; A4 continua fora do núcleo.
A5 foi substituído pela decisão de responsável inicial ser o criador. A6 permanece
nativo; não criar rodízio. Outros ambientes dependem de adaptadores certificados.

## Pendências não bloqueantes da Fase 0

| Pendência | Fases dependentes |
|---|---|
| Manter MIT ou adotar AGPL-3.0; verificar direitos sobre contribuições anteriores | 5 |
| E-mail privado ou GitHub Security Advisories e canal efetivamente habilitado | 5 |
| Dispensar atributo de conversa após verificar automações de contato | 2, 4 |
| Hardware, metas de latência e duração dos ensaios de carga | 3, 5 |
| Acesso móvel só documentado ou URL direta com tema padrão | 3, 5 |
| Usuário de serviço por API de plataforma ou rails runner | 4 |
| Revogação durante cache de cinco minutos e tarefa compartilhada entre escopos | 1 |

Evidências e encaminhamentos serão registrados em `fase-0-contratos-0.2.0.md`.
