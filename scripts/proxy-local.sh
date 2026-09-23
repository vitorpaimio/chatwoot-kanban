#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
mkdir -p .local/nginx/logs
exec nginx -p "$PWD/.local/nginx" -c "$PWD/nginx.local.conf" -g 'daemon off;'
