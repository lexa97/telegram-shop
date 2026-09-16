#!/usr/bin/env bash
# Per-boot service reconciliation: bring up PostgreSQL and Redis as the
# unprivileged agent user, ensure the app role/database exist, and apply
# migrations. Idempotent: safe to run on every boot and re-entrant.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Load the development configuration so service creds match the app config.
set -a
# shellcheck disable=SC1091
[ -f .env ] && . ./.env
set +a

export PATH="/usr/lib/postgresql/16/bin:${PATH}"

VENV="/opt/venv"
[ -x "$VENV/bin/alembic" ] || VENV="$REPO_ROOT/.venv"

PGDATA="${PGDATA:-$HOME/pgdata}"
PGHOST_SOCK="/tmp"
PGPORT="${DB_PORT:-5432}"
DB_NAME="${POSTGRES_DB:-telegram_shop}"
DB_USER="${POSTGRES_USER:-shop_user}"
DB_PASS="${POSTGRES_PASSWORD:-shop_pass_dev}"
REDIS_PORT="${REDIS_PORT:-6379}"
REDIS_PASSWORD="${REDIS_PASSWORD:-changeme_redis_pass}"

# ---------------------------------------------------------------------------
# PostgreSQL
# ---------------------------------------------------------------------------
if [ ! -s "$PGDATA/PG_VERSION" ]; then
    echo "==> Initializing PostgreSQL cluster at $PGDATA"
    initdb -D "$PGDATA" -U postgres --auth-local=trust --auth-host=md5 >/dev/null
fi

if ! pg_ctl -D "$PGDATA" status >/dev/null 2>&1; then
    echo "==> Starting PostgreSQL on 127.0.0.1:$PGPORT"
    pg_ctl -D "$PGDATA" -w -l "$PGDATA/postgres.log" \
        -o "-c listen_addresses='127.0.0.1' -p $PGPORT -k $PGHOST_SOCK" start
else
    echo "==> PostgreSQL already running"
fi

# Ensure application role and database exist. The role is created as a SUPERUSER
# to mirror the official Postgres Docker image (where POSTGRES_USER is a
# superuser): the app sets the superuser-only "lc_messages" server parameter on
# every connection, so a plain LOGIN role would be rejected.
if ! psql -h "$PGHOST_SOCK" -p "$PGPORT" -U postgres -tAc \
        "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1; then
    echo "==> Creating role $DB_USER"
    psql -h "$PGHOST_SOCK" -p "$PGPORT" -U postgres -c \
        "CREATE ROLE \"$DB_USER\" LOGIN SUPERUSER PASSWORD '$DB_PASS'"
else
    psql -h "$PGHOST_SOCK" -p "$PGPORT" -U postgres -c \
        "ALTER ROLE \"$DB_USER\" LOGIN SUPERUSER PASSWORD '$DB_PASS'" >/dev/null
fi

if ! psql -h "$PGHOST_SOCK" -p "$PGPORT" -U postgres -tAc \
        "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1; then
    echo "==> Creating database $DB_NAME"
    psql -h "$PGHOST_SOCK" -p "$PGPORT" -U postgres -c \
        "CREATE DATABASE \"$DB_NAME\" OWNER \"$DB_USER\""
fi

# ---------------------------------------------------------------------------
# Redis
# ---------------------------------------------------------------------------
if ! redis-cli -p "$REDIS_PORT" -a "$REDIS_PASSWORD" ping 2>/dev/null | grep -q PONG; then
    echo "==> Starting Redis on 127.0.0.1:$REDIS_PORT"
    redis-server --daemonize yes \
        --bind 127.0.0.1 \
        --port "$REDIS_PORT" \
        --requirepass "$REDIS_PASSWORD" \
        --dir "$HOME" \
        --appendonly no \
        --save ""
    # Give the daemon a moment to bind before continuing.
    for _ in $(seq 1 10); do
        redis-cli -p "$REDIS_PORT" -a "$REDIS_PASSWORD" ping 2>/dev/null | grep -q PONG && break
        sleep 0.5
    done
else
    echo "==> Redis already running"
fi

# ---------------------------------------------------------------------------
# Database migrations
# ---------------------------------------------------------------------------
echo "==> Applying database migrations (alembic upgrade head)"
"$VENV/bin/alembic" upgrade head

echo "==> start.sh complete: PostgreSQL + Redis up, schema migrated"
