#!/usr/bin/env bash
# Register Telegram Bot webhook URL.
#
# Usage:
#   ./scripts/set_webhook.sh                     # Auto-detect ngrok URL
#   ./scripts/set_webhook.sh https://my.domain   # Explicit URL
#   ./scripts/set_webhook.sh --delete             # Remove webhook

set -euo pipefail

# Load .env if present
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

if [ -z "${TELEGRAM_BOT_TOKEN:-}" ]; then
    echo "ERROR: TELEGRAM_BOT_TOKEN is not set. Check your .env file."
    exit 1
fi

API="https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}"
WEBHOOK_PATH="/api/webhook/telegram"

# --- Delete webhook ---
if [ "${1:-}" = "--delete" ]; then
    echo "Deleting webhook..."
    curl -s "${API}/deleteWebhook" | python3 -m json.tool
    exit 0
fi

# --- Determine base URL ---
if [ -n "${1:-}" ]; then
    BASE_URL="$1"
else
    # Auto-detect from ngrok API
    echo "Detecting ngrok tunnel..."
    NGROK_RESPONSE=$(curl -s http://127.0.0.1:4040/api/tunnels 2>/dev/null || true)
    if [ -z "$NGROK_RESPONSE" ]; then
        echo "ERROR: Cannot reach ngrok API at http://127.0.0.1:4040"
        echo "Make sure ngrok is running: ngrok http 8000"
        exit 1
    fi
    BASE_URL=$(echo "$NGROK_RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
tunnels = data.get('tunnels', [])
for t in tunnels:
    if t.get('proto') == 'https':
        print(t['public_url'])
        break
" 2>/dev/null || true)
    if [ -z "$BASE_URL" ]; then
        echo "ERROR: No HTTPS tunnel found in ngrok. Start ngrok first: ngrok http 8000"
        exit 1
    fi
fi

FULL_URL="${BASE_URL}${WEBHOOK_PATH}"

echo "Setting webhook to: ${FULL_URL}"
RESULT=$(curl -s "${API}/setWebhook" \
    -d "url=${FULL_URL}" \
    -d "drop_pending_updates=true" \
    -d "allowed_updates=[\"message\"]")

echo "$RESULT" | python3 -m json.tool

# Verify
echo ""
echo "Verifying..."
curl -s "${API}/getWebhookInfo" | python3 -m json.tool
