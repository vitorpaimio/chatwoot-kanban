#!/bin/sh
set -eu
unset DATABASE_URL ENCRYPTION_KEY PUBLIC_URL CHATWOOT_BASE_URL
export PATH="$HOME/.rbenv/versions/3.4.4/bin:$HOME/.local/bin:/opt/homebrew/bin:$PATH"
cd "${CHATWOOT_DIR:-$HOME/chatwoot}"
exec bin/vite dev
