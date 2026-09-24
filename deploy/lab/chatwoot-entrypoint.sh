#!/bin/sh
set -eu
export POSTGRES_PASSWORD="$(cat /run/secrets/cw_lab_db_password)"
export SECRET_KEY_BASE="$(cat /run/secrets/cw_lab_secret_key_base)"
exec "$@"
