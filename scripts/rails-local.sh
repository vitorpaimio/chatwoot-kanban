#!/bin/sh
set -eu
unset DATABASE_URL ENCRYPTION_KEY PUBLIC_URL CHATWOOT_BASE_URL
export PATH="$HOME/.rbenv/versions/3.4.4/bin:$HOME/.local/bin:/opt/homebrew/bin:$PATH"
export DEFAULT_LOCALE=pt_BR
export SAFE_FETCH_ALLOW_PRIVATE_NETWORK=true
cd "${CHATWOOT_DIR:-$HOME/chatwoot}"
exec bundle exec rails server -p 3001 -b 127.0.0.1 -P tmp/pids/kanban-rails.pid
