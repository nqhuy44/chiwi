#!/usr/bin/env bash
# Deploy ChiWi to VM.
# Run from the repo root on the VM: bash deploy/deploy.sh

set -euo pipefail

DEPLOY_DIR="/home/nqhuy/chiwi"

echo "==> Pulling latest code..."
git -C "$DEPLOY_DIR" pull origin main

echo "==> Installing dependencies..."
"$DEPLOY_DIR"/.venv/bin/pip install -r "$DEPLOY_DIR"/requirements.txt -q

echo "==> Restarting services..."
sudo systemctl restart chiwi-api chiwi-worker

echo "==> Status:"
sudo systemctl status chiwi-api chiwi-worker --no-pager -l
