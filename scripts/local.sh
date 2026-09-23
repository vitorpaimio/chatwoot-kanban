#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
export PATH="$HOME/.rbenv/versions/3.4.4/bin:$HOME/.local/bin:/opt/homebrew/bin:$PATH"
export OVERMIND_SOCKET="$PWD/.overmind-kanban.sock"
case "${1:-start}" in
 start)
   if overmind status >/dev/null 2>&1; then
     overmind status
     exit 0
   fi
   .venv/bin/alembic upgrade head
   if lsof -nP -iTCP:3036 -sTCP:LISTEN >/dev/null 2>&1; then
     export OVERMIND_IGNORED_PROCESSES=vite
   fi
   overmind start -f Procfile.local -D
   .venv/bin/python scripts/wait_local.py
   ;;
 stop)
   overmind quit
   local_attempt=0
   while [ -S "$OVERMIND_SOCKET" ] && [ "$local_attempt" -lt 40 ]; do
     sleep 1
     local_attempt=$((local_attempt + 1))
   done
   ;;
 restart) overmind restart ;;
 status) overmind status ;;
 *) echo 'Uso: scripts/local.sh start|stop|restart|status'; exit 1 ;;
esac
