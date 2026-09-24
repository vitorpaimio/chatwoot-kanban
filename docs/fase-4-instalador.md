# Fase 4 — instalador Swarm/Traefik e ciclo de vida

**Concluída no ambiente certificado.** Laboratório e Docker removidos após o ensaio,
conforme [sessão 031](sesiones/031-2026-09-24-conclusao-fase-4.md).

O pacote `installer` oferece `install`, `update`, `status`, `uninstall`, `restore`
e planejamento `--dry-run`. A implementação não altera a imagem/código Chatwoot.
O adaptador é voltado a **Swarm de nó único**, com PostgreSQL 16, Traefik 3 usando
provider Swarm e Rails runner disponível no container local selecionado. Não
inferir suporte multinó/HA, Compose ou outros proxies destes testes.

## Configuração

Instalar os requisitos Python do repositório e copiar
[`deploy/installer.example.json`](../deploy/installer.example.json). Preencher:

- `name`: nome exclusivo da stack Kanban; `context`: contexto Docker explícito.
- `accounts`: IDs das contas selecionadas, sem importação automática.
- `image`: imagem Kanban por digest. `allow_local_image` é exclusivo de ensaios.
- `public_url`: origem pública do Chatwoot, sem caminho; `chatwoot_url`: origem
  interna do Rails. O endereço público continua sendo a origem validada na sessão.
- `chatwoot_service`, `chatwoot_database_service`, `chatwoot_database` e
  `chatwoot_database_user`: serviços e banco existentes a inspecionar/copiar.
- `chatwoot_network`: rede overlay para comunicação técnica. `network` é a rede
  pública do Traefik, com padrão `network_public`; o comando exige confirmação.
- `entrypoint` e `tls`: roteamento já disponível no Traefik. O instalador acrescenta
  labels Swarm próprias; não configura certificados nem edita o proxy existente.
- `rails_wrapper`: opcional, executável e caminhos para carregar secrets antes de
  `bundle exec rails runner`. No laboratório: `sh /run/config/chatwoot-entrypoint.sh`.

O diretório de estado é parte da instalação e deve ser preservado. Sua perda não
permite adotar automaticamente uma stack existente. Nomes, contas, redes e origens
ficam vinculados ao manifesto; somente a imagem muda durante atualização.
O arquivo `deploy/stack.yml` é referência renderizada sem segredos; o CLI gera o
template efetivo de `installer/template.py` e o envia ao Docker por stdin.

## Operação

Exemplos (substituir o arquivo de configuração):

```sh
python -m installer install --config instalacao.json --dry-run \
  --confirm-network network_public
python -m installer install --config instalacao.json \
  --confirm-network network_public
python -m installer status --config instalacao.json
python -m installer update --config instalacao.json --dry-run \
  --confirm-network network_public
python -m installer update --config instalacao.json \
  --confirm-network network_public
python -m installer uninstall --config instalacao.json --dry-run \
  --confirm-network network_public
python -m installer uninstall --config instalacao.json \
  --confirm-network network_public
```

`--state-dir` escolhe outro diretório; o padrão é `.local/installations/<name>`.
Dry-run/status não criam estado local nem recursos remotos. O plano identifica por
conta os atributos a criar, reutilizar ou bloquear; opcionais ficam desativados.
Saída 0 indica sucesso; 2 indica bloqueio, falha ou serviço indisponível. Saídas
remotas potencialmente sensíveis nunca são reproduzidas nos diagnósticos.

Install repetido retoma recibos e não duplica usuário, atributos, webhook ou loader.
Uma trava local impede duas operações no mesmo estado, e uma transação Rails com
bloqueio consultivo serializa propriedade entre instalações. Duas instalações não
podem gerenciar a mesma conta simultaneamente. Cada uma usa banco/volumes próprios.
O loader compartilhado é removido apenas ao sair a última instalação, e somente
quando criado pelo instalador. Um loader preexistente é preservado.

Update para API/worker, faz backup, aplica Alembic e aguarda uma **nova** tarefa de
migração concluir; um job antigo concluído não satisfaz o gate. Espera pela conexão
real evita falha de DNS na inicialização. Status verifica API, ativação por conta e
heartbeat próprio do worker, inclusive quando as réplicas foram reduzidas a zero.

## Credenciais, manifesto e backup

Usuário de serviço dedicado: administrador somente nas contas selecionadas; não é
AgentBot nem identidade humana. Token passa por memória/pipes para `kb_accounts`
cifrado. Segredos Docker fornecem banco e chave de cifragem aos processos. Nenhum
token é colocado em argumentos, logs ou arquivos temporários. O manifesto Rails
`KANBAN_INSTALLER_V1` guarda IDs e propriedade, sem token; `kb_resources` recebe os
recibos antes do worker para não perder a origem dos recursos.

Antes de alterar os recursos, o instalador gera dumps cifrados do Chatwoot e, quando
presente, Kanban. Dumps e cofre ficam cifrados em `.fernet`; `recovery.key` é a chave
local de recuperação. Diretório 0700 e arquivos 0600. Preservar arquivos e chave;
esta cópia local não substitui backup externo. Não há dump em claro no disco.
Os dumps são mantidos em memória durante a operação; dimensionar RAM para o banco.

Falha deixa estado e recibos disponíveis para diagnóstico e repetição. Não há
rollback automático de um banco compartilhado do Chatwoot. Para restaurar **somente
o Kanban**, com API/worker parados e backup adicional do estado atual:

```sh
python -m installer restore --config instalacao.json \
  --backup backup-AAAA.fernet --confirm-network network_public
python -m installer status --config instalacao.json
```

O backup precisa pertencer à mesma instalação e conter o banco Kanban. A imagem
anterior é reaplicada. Recursos remotos Chatwoot não são revertidos por esse comando;
reversão de mudanças incompatíveis no Chatwoot exige manutenção coordenada e uso do
dump Chatwoot separado. A Fase 4 não promete downgrade automático de qualquer schema.

## Desinstalação

Revoga imediatamente o token e remove o usuário técnico próprio, webhooks próprios,
serviços e secrets/configs do instalador. Preserva volumes, backups e atributos por
padrão. Repetir a remoção não duplica efeitos. Recursos preexistentes ou que não
correspondem mais aos IDs/definições registrados não são apagados.

**Remover definições próprias pode causar perda de valores dos contatos.** Somente
com confirmação explícita de ambos os argumentos:

```sh
python -m installer uninstall --config instalacao.json \
  --confirm-network network_public --purge-attributes --confirm-attribute-data-loss
```

Mesmo com purge, atributos preexistentes são preservados. A exclusão de volumes e
de Docker/Colima é uma operação administrativa separada; não integra uninstall.

## Evidências e limites

O ensaio real está em `tests/contracts/phase4_swarm.py`, protegido por
`PHASE4_DISPOSABLE_SWARM=colima-kanban-phase4`. Usa duas configurações/estados em
`.local/phase4-cert`, conta 1 e uma segunda conta descartável com conflito controlado.
Não executar contra instalações pessoais ou de produção. O roteiro pode retomar
após a preparação com `PHASE4_RESUME_AFTER_SETUP=1` e o recibo local dessa etapa.

Ambiente: Mac ARM64, Colima (4 CPUs/6 GiB), Swarm de nó único, Chatwoot CE 4.18.0
oficial por digest e Traefik 3. O relatório final é `docs/phase4-evidence.json`.
A certificação não se estende automaticamente a Swarm multinó, amd64, TLS público,
outras versões do Chatwoot, terceiro instalador ou imagens publicadas. Esses gates
seguem na Fase 5; Compose/Nginx tem certificação separada na [Fase 4.2](fase-4.2-compose.md).

O mantenedor solicitou apagar integralmente o laboratório e Docker após o ensaio.
Os caminhos e endereços locais das sessões anteriores são históricos; consultar a
sessão de conclusão para o resultado da limpeza. Código, documentação e evidências
sem credenciais permanecem no repositório.
