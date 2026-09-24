# Instalação avançada por configuração

Para o comando automático na VPS, consulte o [README](../README.md).
**A release 0.2.0 ainda está em preparação.** Os ensaios completos dos adaptadores
cobrem **Chatwoot CE 4.18.0, ARM64**, com os limites abaixo. Consulte a
[matriz de compatibilidade](compatibilidade-0.2.0.md) antes de instalar.

| Sua instalação atual | Adaptador | Requisitos específicos |
| --- | --- | --- |
| Docker Swarm + Traefik 3 | `swarm` | Manager de nó único; Rails/PostgreSQL locais; redes overlay existentes; origem e entrypoint já configurados no Traefik |
| Docker Compose + Nginx | `compose` | Daemon local; plugin Compose; redes bridge existentes; gateway Nginx próprio em porta livre; HTTP local |

Execute no host Docker com acesso administrativo, Git e Python 3.12. O Chatwoot
precisa estar funcionando, com Rails runner disponível e PostgreSQL 16 permitindo
`pg_dump` pelo usuário configurado no container. Reserve espaço para backups e RAM
para os dumps, que são cifrados antes de gravar. Não execute uma atualização do
Chatwoot ao mesmo tempo. O instalador cria um banco Kanban separado, aplica as
migrações e provisiona as contas selecionadas; não precisa criar `.env` nem executar
Alembic manualmente para este caminho.

## Baixar o instalador

O repositório e as imagens GHCR são públicos; clone e pull não exigem login.

```sh
git clone --branch master https://github.com/vitorpaimio/chatwoot-kanban.git
cd chatwoot-kanban
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m installer --help
mkdir -p .local
chmod 700 .local
```

## 2. Obter a imagem do commit aprovado

Abra [Actions → Validar e publicar](https://github.com/vitorpaimio/chatwoot-kanban/actions/workflows/test.yml)
e escolha uma execução **concluída com sucesso** da branch `master`. No resumo do
job de publicação, copie o commit testado e a referência
`ghcr.io/vitorpaimio/chatwoot-kanban@sha256:...`. Ela também está em
`image-digest.txt`, no artefato `image-digest-<commit>`. Se a publicação ainda não
terminou ou falhou, aguarde uma execução aprovada; não use o digest de zeros dos
exemplos.

Use o instalador do mesmo commit da imagem:

```sh
git checkout SHA_DO_COMMIT_APROVADO
.venv/bin/pip install -r requirements.txt
# Substitua pelo contexto e pela referência completos obtidos acima.
docker --context default pull ghcr.io/vitorpaimio/chatwoot-kanban@sha256:DIGEST_REAL
```

O pull deve passar no mesmo contexto usado pelo instalador, inclusive no Swarm
de nó único. Não coloque token no JSON, no comando ou em arquivos do repositório.

## 3. Configurar o ambiente escolhido

Copie **um** exemplo:

```sh
# Swarm/Traefik:
cp deploy/installer.example.json .local/instalacao.json
# OU Compose/Nginx:
# cp deploy/installer.compose.example.json .local/instalacao.json
```

Edite `.local/instalacao.json`. Todos os nomes e digests dos exemplos precisam
corresponder ao seu ambiente:

| Campo | Como preencher |
| --- | --- |
| `name` | Nome exclusivo para a instalação Kanban; no Compose, diferente do projeto Chatwoot |
| `context` | Contexto mostrado por `docker context ls`, normalmente `default` |
| `accounts` | IDs numéricos das contas que receberão Kanban; aparecem em `/app/accounts/ID` na URL do Chatwoot |
| `image` | Referência completa por digest copiada da CI e baixada no passo 2 |
| `public_url` | Origem usada pela equipe para abrir o Chatwoot, sem caminho, por exemplo `https://chat.example.com` |
| `chatwoot_url` | Endereço interno do Rails acessível pela rede Docker, por exemplo `http://rails:3000` |
| `chatwoot_service` / `chatwoot_database_service` | No Swarm, nomes completos de `docker service ls`; no Compose, chaves dos serviços, como `rails` e `postgres` |
| `chatwoot_database` / `chatwoot_database_user` | Nome do banco e usuário existentes no container PostgreSQL do Chatwoot |
| `chatwoot_network` | Rede existente que permite acessar o Rails; confira com `docker network ls` |
| `network` | Rede existente do Traefik no Swarm; rede bridge compartilhada no Compose |

**Swarm:** confirme `entrypoint` e `tls` conforme o Traefik existente. Se Rails
precisa de um wrapper para carregar segredos, preencha `rails_wrapper` conforme o
[guia Swarm](fase-4-instalador.md). O instalador não configura certificados.

**Compose:** mantenha `adapter: "compose"` e informe `chatwoot_project` com o nome
mostrado por `docker compose ls`. `chatwoot_url` precisa usar um alias real do Rails
na rede selecionada. O exemplo usa `public_url: "http://localhost:18080"`,
`listen_host: "127.0.0.1"`, `listen_port: 18080` e `tls: false`. Acesse o Chatwoot
por essa mesma origem; ela encaminha Chatwoot e Kanban juntos. Para um servidor
remoto, abra um túnel `ssh -L 18080:127.0.0.1:18080 usuario@servidor` e use
`http://localhost:18080` no navegador. Ajuste a origem configurada no Chatwoot quando
necessário. TLS público não foi certificado neste adaptador; ele não reescreve seu
Nginx anterior. Veja o [guia Compose](fase-4.2-compose.md).

## 4. Conferir o plano e instalar

Defina `KANBAN_NETWORK` com o valor exato de `network` no JSON. Exemplo Swarm:
`network_public`; exemplo Compose: `chatwoot_default`.

```sh
KANBAN_NETWORK=network_public
.venv/bin/python -m installer install --config .local/instalacao.json \
  --dry-run --confirm-network "$KANBAN_NETWORK"
```

Confira contas, rede e atributos a criar/reutilizar. Só prossiga se o plano retornar
`"blocked": false` e código de saída 0. Conflito obrigatório de atributo bloqueia a
instalação; não apague definições existentes para contornar o diagnóstico.

```sh
.venv/bin/python -m installer install --config .local/instalacao.json \
  --confirm-network "$KANBAN_NETWORK"
.venv/bin/python -m installer status --config .local/instalacao.json
```

O resultado esperado de `status` é `"healthy": true` e código 0. Entre no Chatwoot
pela `public_url`, selecione uma conta incluída e abra **Pipeline → Kanban** ou
**Pipeline → Métricas**. A instalação não importa contatos nem cria cartões
automaticamente. Crie uma negociação ou solicite importação separadamente na
configuração da conta. Código 2 indica bloqueio, falha ou indisponibilidade;
consulte o diagnóstico antes de repetir.

## 5. Preservar, atualizar ou remover

Mantenha `.local/instalacao.json` e **todo** o diretório
`.local/installations/<name>`; proteja também uma cópia externa dos backups e da
`recovery.key`. No Compose, `mounts/` precisa permanecer acessível ao daemon durante
a execução. Não apague o clone nem o estado após instalar. O token técnico é
provisionado automaticamente e cifrado; não copie tokens de usuários humanos.

Para atualizar, baixe a nova imagem por digest, use o instalador do commit
correspondente e altere somente `image` no JSON. Preserve nomes, redes, contas,
origens e diretório de estado. Depois:

```sh
.venv/bin/python -m installer update --config .local/instalacao.json \
  --dry-run --confirm-network "$KANBAN_NETWORK"
.venv/bin/python -m installer update --config .local/instalacao.json \
  --confirm-network "$KANBAN_NETWORK"
.venv/bin/python -m installer status --config .local/instalacao.json
```

Update faz backup antes de aplicar alterações. Para restaurar, consulte o
[procedimento de recuperação](fase-4-instalador.md#credenciais-manifesto-e-backup):
`restore` recupera o Kanban, sem reverter automaticamente o banco compartilhado do
Chatwoot. Para remover a integração preservando dados e atributos:

```sh
.venv/bin/python -m installer uninstall --config .local/instalacao.json \
  --dry-run --confirm-network "$KANBAN_NETWORK"
.venv/bin/python -m installer uninstall --config .local/instalacao.json \
  --confirm-network "$KANBAN_NETWORK"
```

A remoção revoga o usuário técnico próprio e remove os recursos gerenciados.
No Compose, também remove o gateway criado; retome o acesso anterior ao Chatwoot.
Volumes, backups e atributos são preservados por padrão.

