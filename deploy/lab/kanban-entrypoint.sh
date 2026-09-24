#!/bin/sh
set -eu
export DATABASE_URL="postgresql://kanban:$(cat /run/secrets/kb_lab_db_password)@kblab_postgres:5432/kanban"
export ENCRYPTION_KEY="$(cat /run/secrets/kb_lab_encryption_key)"
exec "$@"
