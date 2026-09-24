#!/bin/sh
# Instalador para VPS Linux com Chatwoot Docker existente.
set -eu
if [ "$(uname -s)" != Linux ]; then
  echo 'Execute no terminal da VPS Linux que hospeda o Chatwoot.' >&2; exit 2
fi
if [ "$(id -u)" != 0 ]; then
  echo 'Execute como root ou com sudo bash install.sh.' >&2; exit 2
fi
command -v docker >/dev/null 2>&1 || {
  echo 'Docker não encontrado. Este comando integra um Chatwoot Docker já instalado.' >&2
  exit 2
}
# O socket local evita executar em outro servidor por contexto/DOCKER_HOST herdado.
[ -S /var/run/docker.sock ] || { echo 'Socket Docker local não encontrado.' >&2; exit 2; }
export DOCKER_HOST=unix:///var/run/docker.sock
unset DOCKER_CONTEXT DOCKER_TLS_VERIFY DOCKER_CERT_PATH
state=/opt/chatwoot-kanban
[ ! -L "$state" ] || { echo 'Diretório de estado não pode ser link simbólico.' >&2; exit 2; }
umask 077
mkdir -p "$state"
chmod 700 "$state"
image=ghcr.io/vitorpaimio/chatwoot-kanban:installer-master
echo 'Preparando o assistente do Chatwoot Kanban…'
docker pull --quiet "$image" >/dev/null
# Usa o ID obtido do pull, sem resolver novamente uma tag mutável ao executar.
image_id=$(docker image inspect --format '{{.Id}}' "$image")
if [ -t 0 ] && [ -t 1 ]; then
  set -- -it "$@"
else
  set -- -i "$@"
fi
# Separar opção de TTY dos argumentos do instalador.
tty_option=$1
shift
exec docker run --rm "$tty_option" --env TERM="${TERM:-xterm}" --network host \
  --mount type=bind,src=/var/run/docker.sock,dst=/var/run/docker.sock \
  --mount type=bind,src="$state",dst="$state" \
  "$image_id" "$@"
