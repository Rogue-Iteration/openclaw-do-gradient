#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
# OpenClaw + Gradient AI — Deploy Updates (run from repo on Droplet)
# ═══════════════════════════════════════════════════════════════════
set -euo pipefail

STATE_DIR="$HOME/.openclaw"
WORKSPACE_DIR="$HOME/.openclaw/workspace"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENTS=("web-researcher" "fundamental-analyst")

echo "Pulling latest changes..."
git -C "$SCRIPT_DIR" pull origin main

echo "Updating persona files..."

# Per-agent persona files
for agent in "${AGENTS[@]}"; do
  AGENT_WS="$STATE_DIR/agents/$agent/agent"
  SRC_DIR="$SCRIPT_DIR/data/workspaces/$agent"
  if [ -d "$SRC_DIR" ]; then
    mkdir -p "$AGENT_WS"
    for f in IDENTITY.md AGENTS.md HEARTBEAT.md; do
      if [ -f "$SRC_DIR/$f" ]; then
        cp "$SRC_DIR/$f" "$AGENT_WS/$f"
      fi
    done

    # Ensure agent-specific skills symlink exists
    SKILL_DIR="$SCRIPT_DIR/skills/$agent"
    if [ -d "$SKILL_DIR" ] && [ ! -e "$AGENT_WS/skills/$agent" ]; then
      mkdir -p "$AGENT_WS/skills"
      ln -s "$SKILL_DIR" "$AGENT_WS/skills/$agent"
    fi

    # Ensure shared skills symlink exists
    SHARED_SKILL_DIR="$SCRIPT_DIR/skills/gradient-research-assistant"
    if [ -d "$SHARED_SKILL_DIR" ] && [ ! -e "$AGENT_WS/skills/gradient-research-assistant" ]; then
      mkdir -p "$AGENT_WS/skills"
      ln -s "$SHARED_SKILL_DIR" "$AGENT_WS/skills/gradient-research-assistant"
    fi

    echo "  ✓ $agent updated"
  fi
done

# Shared/legacy persona files
for f in IDENTITY.md AGENTS.md HEARTBEAT.md; do
  if [ -f "$SCRIPT_DIR/data/workspace/$f" ]; then
    cp "$SCRIPT_DIR/data/workspace/$f" "$WORKSPACE_DIR/$f"
  fi
done

# ── Update openclaw.json agents config ──
echo "Updating agent config..."
OPENCLAW_JSON="$STATE_DIR/openclaw.json"
if [ -f "$OPENCLAW_JSON" ]; then
  # Add/update agents list with workspace paths
  jq '
    .agents.list = [
      {
        "id": "web-researcher",
        "name": "Nova",
        "default": false,
        "workspace": (env.HOME + "/.openclaw/agents/web-researcher/agent"),
        "model": { "primary": "gradient/openai-gpt-oss-120b" },
        "heartbeat": { "interval": "30m" }
      },
      {
        "id": "fundamental-analyst",
        "name": "Max",
        "default": true,
        "workspace": (env.HOME + "/.openclaw/agents/fundamental-analyst/agent"),
        "model": { "primary": "gradient/openai-gpt-oss-120b" },
        "heartbeat": { "interval": "2h" }
      }
    ]
  ' "$OPENCLAW_JSON" > "$OPENCLAW_JSON.tmp" && mv "$OPENCLAW_JSON.tmp" "$OPENCLAW_JSON"
  echo "  ✓ Agent config updated (Nova + Max)"
fi

echo "Updating Python dependencies..."
pip3 install --break-system-packages -q -r "$SCRIPT_DIR/requirements.txt"

echo "Restarting OpenClaw..."
sudo systemctl restart openclaw

sleep 3
if systemctl is-active --quiet openclaw; then
  echo "✅ OpenClaw restarted with multi-agent config"
  echo "   Agents: Nova (web-researcher) + Max (fundamental-analyst)"
  echo "   Max is default — messages go to Max unless you address Nova"
else
  echo "⚠️  Check logs: journalctl -u openclaw -f"
fi
