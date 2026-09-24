# Sessão 031 — Conclusão da Fase 4 e remoção do laboratório

Pedido: concluir a Fase 4 e apagar todo o ambiente de teste, inclusive Docker
instalado no Mac. Código do projeto e Chatwoot local anterior foram preservados.

## Entrega

CLI Swarm install/update/uninstall/status, dry-run e restore do banco Kanban.
Configuração sem segredos, confirmação de rede, manifesto, travas, isolamento por
instalação/conta, backup cifrado, usuário técnico e recursos com propriedade,
segredos Docker, Alembic, API/worker com sondas e labels Traefik Swarm. Sem mudanças
no código/imagem do Chatwoot. `deploy/stack.yml` é referência sem credenciais;
`deploy/installer.example.json` e `docs/fase-4-instalador.md` explicam o uso.

Certificação real: Swarm single-node ARM64 (Colima, 4 CPUs/6 GiB), Docker 29.5.2,
Chatwoot CE 4.18.0 oficial e Traefik 3.7.13. Duas instalações simultâneas saudáveis,
repetição sem duplicações, conflito obrigatório bloqueado sem criar estado,
roteamento por host, detecção de worker desativado e recuperação, atualização
preservando configurações e falha de imagem seguida de restauração comprovada.

Desinstalação revogou token (HTTP 401), manteve a outra instalação saudável,
preservou atributos preexistentes e permitiu repetição. Purge recusado sem
confirmação; confirmado, removeu só próprios. Loader removido ao sair a última
instalação. Reinstalação usando volume preservado voltou saudável; quadro e sessão
humana conferidos no navegador. Evento nativo do Chatwoot recebido/processado pelo
webhook. Backup Chatwoot também restaurado em banco temporário na sessão anterior.

Correções orientadas pelo ensaio: esperar conexão real para evitar corrida de DNS
antes da migração; não misturar labels Docker e Swarm no Traefik; considerar worker
com zero réplicas indisponível mesmo com heartbeat recente; esperar nova tarefa de
migração, sem aceitar uma execução antiga concluída. Ensaio retomado após correções;
resultados e versões preservados em `docs/phase4-evidence.json`.

Gates: Ruff, 146 testes Python no PostgreSQL exclusivo (dois opt-in de outras fases
omitidos), quatro testes Node, sintaxe Ruby/shell e diff sem erros. O ensaio Swarm
foi executado separadamente com `tests/contracts/phase4_swarm.py`.

## Limpeza solicitada

Removidos: VM/perfil `kanban-phase4` e seus containers, imagens, volumes, redes,
configs/secrets, contas e bancos; Docker CLI, Compose, Buildx, Colima e dependência
Lima; diretórios `.docker`, `.colima`, cache Colima e downloads/logs Homebrew novos
desses pacotes; `.local/phase4` e `.local/phase4-cert`, incluindo backups/chaves.
A aba do laboratório foi fechada. Os backups desse ensaio não existem mais, por
solicitação explícita; os exemplos de caminhos da sessão 030 são históricos.

Verificação: nenhum desses binários/pacotes permanece; nenhum runtime Colima/Lima
ativo; diretórios ausentes e porta 18080 fechada. Chatwoot original em
localhost:3000/api respondeu normalmente. PostgreSQL, Redis, Nginx e rbenv anteriores
permanecem instalados. Nenhum commit, push ou publicação foi feito.

## Limites e continuidade

Fase 4 concluída no ambiente certificado. Não inferir multinó/HA, amd64, TLS público,
outra versão de Chatwoot ou instalação por terceiro. Fase 4.2: adaptador
Compose/Nginx. Fase 5: matriz final, restauração operacional externa e publicação
condicionada aos testes do mesmo commit. Licença e canal público seguem o plano.
