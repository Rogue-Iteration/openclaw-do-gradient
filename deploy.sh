#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
# OpenClaw + Gradient AI — Deploy Updates
# ═══════════════════════════════════════════════════════════════════
# Run this on the Droplet (or any server) to pull the latest code
# and restart the Docker containers.
#
# Usage:
#   cd /opt/openclaw && bash deploy.sh
#
# For remote deploys from your local machine, use:
#   bash install.sh --update
# ═══════════════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Pulling latest changes..."
git -C "$SCRIPT_DIR" pull origin main

echo "Rebuilding and restarting containers..."
cd "$SCRIPT_DIR"
docker compose up -d --build --remove-orphans

sleep 5
if docker ps --filter name=openclaw-research --format '{{.Status}}' | grep -q "Up"; then
  echo "✅ OpenClaw updated and running"
  echo "   View logs: docker logs -f openclaw-research"
else
  echo "⚠️  Container may not be healthy. Check: docker logs openclaw-research"
fi
