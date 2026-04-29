#!/usr/bin/env bash
# Register Telegram Bot webhook URL for Production.
# This script reads TELEGRAM_WEBHOOK_URL and TELEGRAM_WEBHOOK_SECRET from the environment or .env file.
#
# Usage:
#   ./scripts/set_webhook_prod.sh

set -euo pipefail

# Load .env if present
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

if [ -z "${TELEGRAM_BOT_TOKEN:-}" ]; then
    echo "ERROR: TELEGRAM_BOT_TOKEN is not set. Check your environment or .env file."
    exit 1
fi

if [ -z "${TELEGRAM_WEBHOOK_URL:-}" ]; then
    echo "ERROR: TELEGRAM_WEBHOOK_URL is not set. Check your environment or .env file."
    echo "Example: TELEGRAM_WEBHOOK_URL=https://api.yourdomain.com/api/webhook/telegram"
    exit 1
fi

API="https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}"

echo "Setting webhook to: ${TELEGRAM_WEBHOOK_URL}"
CURL_ARGS=(
    -d "url=${TELEGRAM_WEBHOOK_URL}"
    -d "drop_pending_updates=true"
    -d "allowed_updates=[\"message\",\"callback_query\"]"
)

if [ -n "${TELEGRAM_WEBHOOK_SECRET:-}" ]; then
    # Telegram requires the secret token to match ^[A-Za-z0-9_-]{1,256}$
    if ! [[ "${TELEGRAM_WEBHOOK_SECRET}" =~ ^[A-Za-z0-9_-]{1,256}$ ]]; then
        echo "ERROR: TELEGRAM_WEBHOOK_SECRET contains invalid characters."
        echo "Only A-Z, a-z, 0-9, _ and - are allowed."
        exit 1
    fi
    CURL_ARGS+=(-d "secret_token=${TELEGRAM_WEBHOOK_SECRET}")
    echo "Using webhook secret token."
else
    echo "WARNING: TELEGRAM_WEBHOOK_SECRET is not set. Webhook will be registered without a secret token."
fi

RESULT=$(curl -s "${API}/setWebhook" "${CURL_ARGS[@]}")

echo "$RESULT" | python3 -m json.tool

# Verify
echo ""
echo "Verifying..."
curl -s "${API}/getWebhookInfo" | python3 -m json.tool
