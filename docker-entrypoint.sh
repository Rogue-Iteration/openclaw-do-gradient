#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
# OpenClaw Docker Entrypoint
# ═══════════════════════════════════════════════════════════════════
# Runs on every container start. On first boot, configures:
# - openclaw.json (models, agents, plugins, Telegram)
# - Agent workspaces with persona files
# - Skill symlinks for each agent
#
# On subsequent starts, updates persona files and skills from the
# latest image without overwriting runtime state (credentials, etc).
# ═══════════════════════════════════════════════════════════════════
set -euo pipefail

STATE_DIR="$HOME/.openclaw"
WORKSPACE_DIR="$STATE_DIR/workspace"
APP_DIR="/app"
AGENTS=("web-researcher" "fundamental-analyst" "social-researcher" "technical-analyst")

# ── 1. First-run: generate openclaw.json ─────────────────────────
if [ ! -f "$STATE_DIR/openclaw.json" ]; then
  echo "🔧 First run — generating openclaw.json..."
  mkdir -p "$STATE_DIR" "$WORKSPACE_DIR"

  cat > "$STATE_DIR/openclaw.json" <<'JSON'
{
  "gateway": {
    "mode": "local"
  },
  "plugins": {
    "enabled": true,
    "entries": {
      "telegram": { "enabled": true }
    }
  },
  "models": {
    "mode": "merge",
    "providers": {
      "gradient": {
        "baseUrl": "https://inference.do-ai.run/v1",
        "api": "openai-completions",
        "models": [
          {
            "id": "openai-gpt-oss-120b",
            "name": "OpenAI GPT OSS 120B",
            "reasoning": false,
            "input": ["text"],
            "contextWindow": 128000,
            "maxTokens": 8192
          },
          {
            "id": "llama3.3-70b-instruct",
            "name": "Llama 3.3 70B Instruct",
            "reasoning": false,
            "input": ["text"],
            "contextWindow": 128000,
            "maxTokens": 8192
          },
          {
            "id": "deepseek-r1-distill-llama-70b",
            "name": "DeepSeek R1 Distill Llama 70B",
            "reasoning": true,
            "input": ["text"],
            "contextWindow": 128000,
            "maxTokens": 8192
          },
          {
            "id": "qwen3-32b",
            "name": "Qwen3 32B",
            "reasoning": false,
            "input": ["text"],
            "contextWindow": 32768,
            "maxTokens": 4096
          }
        ]
      }
    }
  },
  "agents": {
    "defaults": {
      "model": {
        "primary": "gradient/openai-gpt-oss-120b"
      }
    },
    "list": [
      {
        "id": "fundamental-analyst",
        "name": "Max",
        "default": true,
        "workspace": "/root/.openclaw/agents/fundamental-analyst/agent",
        "model": { "primary": "gradient/openai-gpt-oss-120b" }
      },
      {
        "id": "web-researcher",
        "name": "Nova",
        "default": false,
        "workspace": "/root/.openclaw/agents/web-researcher/agent",
        "model": { "primary": "gradient/openai-gpt-oss-120b" }
      },
      {
        "id": "social-researcher",
        "name": "Luna",
        "default": false,
        "workspace": "/root/.openclaw/agents/social-researcher/agent",
        "model": { "primary": "gradient/openai-gpt-oss-120b" }
      },
      {
        "id": "technical-analyst",
        "name": "Ace",
        "default": false,
        "workspace": "/root/.openclaw/agents/technical-analyst/agent",
        "model": { "primary": "gradient/openai-gpt-oss-120b" }
      }
    ]
  },
  "tools": {
    "exec": {
      "security": "allowlist"
    }
  }
}
JSON

  # Generate gateway auth token
  GW_TOKEN=$(head -c 32 /dev/urandom | base64 | tr -d '=/+' | head -c 32)
  jq --arg t "$GW_TOKEN" '.gateway.auth.token = $t | .gateway.auth.mode = "token"' \
    "$STATE_DIR/openclaw.json" > "$STATE_DIR/openclaw.json.tmp" \
    && mv "$STATE_DIR/openclaw.json.tmp" "$STATE_DIR/openclaw.json"

  # Inject Gradient API key if set
  if [ -n "${GRADIENT_API_KEY:-}" ]; then
    jq --arg key "$GRADIENT_API_KEY" '.models.providers.gradient.apiKey = $key' \
      "$STATE_DIR/openclaw.json" > "$STATE_DIR/openclaw.json.tmp" \
      && mv "$STATE_DIR/openclaw.json.tmp" "$STATE_DIR/openclaw.json"
  fi

  # Configure Telegram with per-agent bot accounts
  if [ -n "${MAX_TELEGRAM_BOT_TOKEN:-}" ]; then
    # Build the accounts object with all available bot tokens
    ACCOUNTS_JSON="{}"
    BINDINGS_JSON="[]"

    ACCOUNTS_JSON=$(echo "$ACCOUNTS_JSON" | jq --arg t "$MAX_TELEGRAM_BOT_TOKEN" '.max = {"botToken": $t}')
    BINDINGS_JSON=$(echo "$BINDINGS_JSON" | jq '. + [{"match": {"channel": "telegram", "accountId": "max"}, "agentId": "fundamental-analyst"}]')

    if [ -n "${NOVA_TELEGRAM_BOT_TOKEN:-}" ]; then
      ACCOUNTS_JSON=$(echo "$ACCOUNTS_JSON" | jq --arg t "$NOVA_TELEGRAM_BOT_TOKEN" '.nova = {"botToken": $t}')
      BINDINGS_JSON=$(echo "$BINDINGS_JSON" | jq '. + [{"match": {"channel": "telegram", "accountId": "nova"}, "agentId": "web-researcher"}]')
    fi

    if [ -n "${LUNA_TELEGRAM_BOT_TOKEN:-}" ]; then
      ACCOUNTS_JSON=$(echo "$ACCOUNTS_JSON" | jq --arg t "$LUNA_TELEGRAM_BOT_TOKEN" '.luna = {"botToken": $t}')
      BINDINGS_JSON=$(echo "$BINDINGS_JSON" | jq '. + [{"match": {"channel": "telegram", "accountId": "luna"}, "agentId": "social-researcher"}]')
    fi

    if [ -n "${ACE_TELEGRAM_BOT_TOKEN:-}" ]; then
      ACCOUNTS_JSON=$(echo "$ACCOUNTS_JSON" | jq --arg t "$ACE_TELEGRAM_BOT_TOKEN" '.ace = {"botToken": $t}')
      BINDINGS_JSON=$(echo "$BINDINGS_JSON" | jq '. + [{"match": {"channel": "telegram", "accountId": "ace"}, "agentId": "technical-analyst"}]')
    fi

    jq --argjson accounts "$ACCOUNTS_JSON" --argjson bindings "$BINDINGS_JSON" \
      '.channels.telegram.enabled = true | .channels.telegram.groupPolicy = "open" | .channels.telegram.dmPolicy = "open" | .channels.telegram.accounts = $accounts | .bindings = $bindings' \
      "$STATE_DIR/openclaw.json" > "$STATE_DIR/openclaw.json.tmp" \
      && mv "$STATE_DIR/openclaw.json.tmp" "$STATE_DIR/openclaw.json"
  fi

  # Configure exec approvals
  for pattern in \
    "python3" "/usr/bin/python3" "python3 *" \
    "cat" "python" "/usr/bin/python" "python *" \
    "ls" "head" "tail" "pip3" "sqlite3" "sqlite3 *"; do
    openclaw approvals allowlist add --target local --agent '*' --pattern "$pattern" 2>/dev/null || true
  done

  # Let OpenClaw apply any auto-detected fixes
  openclaw doctor --fix 2>/dev/null || true

  echo "  ✓ openclaw.json created"
fi

# ── 2. Always: sync persona files and skills ─────────────────────
echo "📋 Syncing persona files and skills..."

# Per-agent setup
for agent in "${AGENTS[@]}"; do
  AGENT_WS="$STATE_DIR/agents/$agent/agent"
  mkdir -p "$AGENT_WS/skills"

  # Copy persona files (always update from image)
  SRC_DIR="$APP_DIR/data/workspaces/$agent"
  if [ -d "$SRC_DIR" ]; then
    for f in IDENTITY.md AGENTS.md HEARTBEAT.md; do
      [ -f "$SRC_DIR/$f" ] && cp "$SRC_DIR/$f" "$AGENT_WS/$f"
    done
  fi

  # Symlink agent-specific skills
  SKILL_DIR="$APP_DIR/skills/$agent"
  if [ -d "$SKILL_DIR" ] && [ ! -e "$AGENT_WS/skills/$agent" ]; then
    ln -s "$SKILL_DIR" "$AGENT_WS/skills/$agent"
  fi

  # Symlink shared skills
  SHARED_SKILL_DIR="$APP_DIR/skills/gradient-research-assistant"
  if [ -d "$SHARED_SKILL_DIR" ] && [ ! -e "$AGENT_WS/skills/gradient-research-assistant" ]; then
    ln -s "$SHARED_SKILL_DIR" "$AGENT_WS/skills/gradient-research-assistant"
  fi
done

# Shared workspace persona files (default agent fallback)
mkdir -p "$WORKSPACE_DIR"
for f in IDENTITY.md AGENTS.md HEARTBEAT.md; do
  [ -f "$APP_DIR/data/workspace/$f" ] && cp "$APP_DIR/data/workspace/$f" "$WORKSPACE_DIR/$f"
done

# Shared workspace skills symlink
if [ ! -e "$WORKSPACE_DIR/skills" ]; then
  ln -s "$APP_DIR/skills" "$WORKSPACE_DIR/skills"
fi

echo "  ✓ Agents: Max + Nova + Luna + Ace"

# ── 3. Always: initialize SQLite database ────────────────────────
echo "💾 Initializing research database..."
python3 "$APP_DIR/skills/gradient-research-assistant/db.py" --init --db "$STATE_DIR/research.db"
echo "  ✓ Database ready"

# ── 4. Always: sync timezone and seed default schedules ──────────
if [ -n "${USER_TIMEZONE:-}" ]; then
  python3 "$APP_DIR/skills/gradient-research-assistant/schedule.py" \
    --set-timezone "$USER_TIMEZONE" --db "$STATE_DIR/research.db"
  echo "  ✓ Timezone: $USER_TIMEZONE"
fi

python3 "$APP_DIR/skills/gradient-research-assistant/schedule.py" \
  --seed-defaults --db "$STATE_DIR/research.db"
echo "  ✓ Schedules ready"

# ── 5. Hand off to CMD ───────────────────────────────────────────
echo "🚀 Starting OpenClaw..."
exec "$@"
