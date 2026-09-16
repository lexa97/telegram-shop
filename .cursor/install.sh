#!/usr/bin/env bash
# Repo bootstrap: install Python dependencies and seed a development .env.
# Idempotent and safe to re-run.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

VENV="/opt/venv"
PIP="$VENV/bin/pip"

# Fall back to a repo-local venv when the image-provided one is unavailable
# (e.g. running install.sh outside the Cloud Agent image).
if [ ! -x "$PIP" ]; then
    PYTHON="$(command -v python3.11 || command -v python3)"
    "$PYTHON" -m venv "$REPO_ROOT/.venv"
    VENV="$REPO_ROOT/.venv"
    PIP="$VENV/bin/pip"
    "$PIP" install --upgrade pip
fi

echo "==> Installing Python dependencies into $VENV"
"$PIP" install -r requirements.txt

# Seed a development .env wired to the bundled Postgres/Redis if one is absent.
# The bot module reads these at import time, so the file must exist before the
# test suite or the app can run. Real Telegram credentials are placeholders here;
# supply your own TOKEN/OWNER_ID to run the live bot.
if [ ! -f .env ]; then
    echo "==> Creating development .env"
    cat > .env <<'ENVEOF'
# Auto-generated development configuration (Cloud Agent).
# Placeholder Telegram credentials — replace TOKEN/OWNER_ID to run the live bot.
TOKEN=0000000000:DEV_PLACEHOLDER_TOKEN_REPLACE_ME
OWNER_ID=123456789

# Payments (disabled in dev)
TELEGRAM_PROVIDER_TOKEN=
CRYPTO_PAY_TOKEN=
STARS_PER_VALUE=0.91
PAY_CURRENCY=RUB
REFERRAL_PERCENT=0
PAYMENT_TIME=1800
MIN_AMOUNT=20
MAX_AMOUNT=10000

# Links / UI
CHANNEL_URL=
CHANNEL_ID=
HELPER_ID=
RULES="1. Be respectful\n2. No spam\n3. Follow Telegram ToS"

# Locale & logging
BOT_LOCALE=ru
BOT_LOGFILE=logs/bot.log
BOT_AUDITFILE=logs/audit.log
LOG_TO_STDOUT=1
LOG_TO_FILE=1
DEBUG=0
REVIEWS_ENABLED=1

# Redis (bundled service)
REDIS_ENABLED=1
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=changeme_redis_pass

# PostgreSQL (bundled service)
POSTGRES_DB=telegram_shop
POSTGRES_USER=shop_user
POSTGRES_PASSWORD=shop_pass_dev
POSTGRES_HOST=127.0.0.1
DB_PORT=5432
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20

# Admin web panel (loopback-only in dev, so default creds are allowed)
ADMIN_HOST=127.0.0.1
ADMIN_PORT=9090
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin
SECRET_KEY=dev-secret-key-not-for-production
ADMIN_COOKIE_SECURE=0

# Webhook mode off (polling)
WEBHOOK_ENABLED=0
WEBHOOK_URL=
WEBHOOK_PATH=/webhook
WEBHOOK_SECRET=
WEBHOOK_HOST=127.0.0.1
WEBHOOK_PORT=8080

# Cleanup
AUDIT_RETENTION_DAYS=90
PAYMENTS_RETENTION_DAYS=90
ENVEOF
else
    echo "==> .env already present, leaving it untouched"
fi

mkdir -p logs data

echo "==> install.sh complete"
