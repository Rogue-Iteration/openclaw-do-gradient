#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
# OpenClaw Docker Entrypoint
# ═══════════════════════════════════════════════════════════════════
# Runs on every container start. On first boot, configures:
# - openclaw.json (models, agents, plugins, Telegram)
# - Agent workspaces with persona files
# - Shared skills in ~/.openclaw/skills/ (OpenClaw-native managed dir)
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
            "reasoning": true,
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
      },
      "heartbeat": {
        "every": "30m",
        "activeHours": { "start": "07:00", "end": "22:00" }
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

  # Let OpenClaw apply any auto-detected fixes (before Telegram config)
  openclaw doctor --fix 2>/dev/null || true

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

    # Build allowFrom list: use TELEGRAM_ALLOWED_IDS if set, otherwise open to all
    if [ -n "${TELEGRAM_ALLOWED_IDS:-}" ]; then
      # Convert comma-separated IDs to JSON array: "123,456" → ["123","456"]
      ALLOW_FROM=$(echo "$TELEGRAM_ALLOWED_IDS" | tr ',' '\n' | jq -R . | jq -s .)
    else
      echo "  ⚠️  TELEGRAM_ALLOWED_IDS not set — bots are open to ALL users"
      ALLOW_FROM='["*"]'
    fi

    jq --argjson accounts "$ACCOUNTS_JSON" --argjson bindings "$BINDINGS_JSON" --argjson allow "$ALLOW_FROM" \
      '.channels.telegram.enabled = true | .channels.telegram.groupPolicy = "open" | .channels.telegram.dmPolicy = "pairing" | .channels.telegram.allowFrom = $allow | .channels.telegram.accounts = $accounts | .channels.telegram.groups = {"*": {"requireMention": true}} | .bindings = $bindings' \
      "$STATE_DIR/openclaw.json" > "$STATE_DIR/openclaw.json.tmp" \
      && mv "$STATE_DIR/openclaw.json.tmp" "$STATE_DIR/openclaw.json"
  fi

  # Configure exec approvals — allow only specific skill scripts, not arbitrary commands
  for pattern in \
    "python3 /app/skills/gradient-research-assistant/scripts/*.py *" \
    "python3 /app/skills/gradient-inference/scripts/*.py *" \
    "python3 /app/skills/gradient-knowledge-base/scripts/*.py *" \
    "python3 /app/skills/gradient-data-gathering/scripts/*.py *" \
    "python3 /root/.openclaw/skills/gradient-research-assistant/scripts/*.py *" \
    "python3 /root/.openclaw/skills/gradient-inference/scripts/*.py *" \
    "python3 /root/.openclaw/skills/gradient-knowledge-base/scripts/*.py *" \
    "python3 /root/.openclaw/skills/gradient-data-gathering/scripts/*.py *" \
    "cat" "ls" "head" "tail" "sqlite3" "sqlite3 *"; do
    openclaw approvals allowlist add --target local --agent '*' --pattern "$pattern" 2>/dev/null || true
  done


  echo "  ✓ openclaw.json created"
fi

# ── 2. Always: sync persona files and skills ─────────────────────
echo "📋 Syncing persona files and skills..."

# Install published skills from ClawHub (force-reinstall every startup)
# If ClawHub install fails (e.g. security scan pending), fall back to local copy
MANAGED_SKILLS_DIR="$STATE_DIR/skills"
mkdir -p "$MANAGED_SKILLS_DIR"
CLAWHUB_SKILLS="gradient-knowledge-base gradient-inference"
for skill in $CLAWHUB_SKILLS; do
  echo "  📦 Installing $skill from ClawHub..."
  INSTALL_OUTPUT=$(npx clawhub@latest install "$skill" --dir "$MANAGED_SKILLS_DIR" --force 2>&1) || true
  if [ -d "$MANAGED_SKILLS_DIR/$skill" ] && [ -f "$MANAGED_SKILLS_DIR/$skill/SKILL.md" ]; then
    echo "  ✓ $skill installed from ClawHub"
  else
    echo "  ⚠️  ClawHub install failed for $skill — using local copy"
    echo "     ($INSTALL_OUTPUT)"
    SKILL_SRC="$APP_DIR/skills/$skill"
    if [ -d "$SKILL_SRC" ]; then
      rm -rf "$MANAGED_SKILLS_DIR/$skill"
      cp -r "$SKILL_SRC" "$MANAGED_SKILLS_DIR/$skill"
    fi
  fi
done

# Copy local-only skills (not published to ClawHub)
for skill in gradient-data-gathering gradient-research-assistant; do
  SKILL_SRC="$APP_DIR/skills/$skill"
  SKILL_DST="$MANAGED_SKILLS_DIR/$skill"
  if [ -d "$SKILL_SRC" ]; then
    rm -rf "$SKILL_DST"
    cp -r "$SKILL_SRC" "$SKILL_DST"
  fi
done

# Per-agent setup (persona files only — skills are loaded from managed dir)
for agent in "${AGENTS[@]}"; do
  AGENT_WS="$STATE_DIR/agents/$agent/agent"
  mkdir -p "$AGENT_WS"

  # Copy persona files (always update from image)
  SRC_DIR="$APP_DIR/data/workspaces/$agent"
  if [ -d "$SRC_DIR" ]; then
    for f in IDENTITY.md AGENTS.md HEARTBEAT.md; do
      [ -f "$SRC_DIR/$f" ] && cp "$SRC_DIR/$f" "$AGENT_WS/$f"
    done
  fi
done

# Shared workspace persona files (default agent fallback)
mkdir -p "$WORKSPACE_DIR"
for f in IDENTITY.md AGENTS.md HEARTBEAT.md; do
  [ -f "$APP_DIR/data/workspace/$f" ] && cp "$APP_DIR/data/workspace/$f" "$WORKSPACE_DIR/$f"
done

echo "  ✓ Agents: Max + Nova + Luna + Ace"

# ── 3. Always: initialize SQLite database ────────────────────────
echo "💾 Initializing research database..."
python3 "$APP_DIR/skills/gradient-research-assistant/scripts/db.py" --init --db "$STATE_DIR/research.db"
echo "  ✓ Database ready"

# ── 4. Always: sync timezone and seed default schedules ──────────
if [ -n "${USER_TIMEZONE:-}" ]; then
  python3 "$APP_DIR/skills/gradient-research-assistant/scripts/schedule.py" \
    --set-timezone "$USER_TIMEZONE" --db "$STATE_DIR/research.db"
  echo "  ✓ Timezone: $USER_TIMEZONE"
fi

python3 "$APP_DIR/skills/gradient-research-assistant/scripts/schedule.py" \
  --seed-defaults --db "$STATE_DIR/research.db"
echo "  ✓ Schedules ready"

# ── 5. Hand off to CMD ───────────────────────────────────────────
echo "🚀 Starting OpenClaw..."
exec "$@"
