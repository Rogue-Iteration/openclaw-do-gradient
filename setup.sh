#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
# OpenClaw + Gradient AI — Droplet Setup (run once as root)
# ═══════════════════════════════════════════════════════════════════
set -euo pipefail

OPENCLAW_VERSION="2026.2.9"
OPENCLAW_USER="openclaw"
OPENCLAW_HOME="/home/$OPENCLAW_USER"
STATE_DIR="$OPENCLAW_HOME/.openclaw"
WORKSPACE_DIR="$OPENCLAW_HOME/.openclaw/workspace"
REPO_DIR="$OPENCLAW_HOME/openclaw-do-gradient"
ENV_FILE="/etc/openclaw.env"

# Agent workspace layout
AGENTS=("web-researcher" "fundamental-analyst")

echo "╔════════════════════════════════════════════╗"
echo "║  OpenClaw + Gradient AI — Droplet Setup    ║"
echo "╚════════════════════════════════════════════╝"

# ── 0. Validate env file ──────────────────────────────────────────
if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: $ENV_FILE not found."
  echo "Create it first with your secrets. See .env.example."
  exit 1
fi

# Source env vars for use during setup
set -a
source "$ENV_FILE"
set +a

echo "[1/9] Installing system packages..."
apt-get update -qq
apt-get install -y --no-install-recommends \
  ca-certificates curl git jq python3 python3-pip python3-venv build-essential

# ── 1. Create user ────────────────────────────────────────────────
echo "[2/9] Creating $OPENCLAW_USER user..."
if ! id "$OPENCLAW_USER" &>/dev/null; then
  useradd -m -s /bin/bash "$OPENCLAW_USER"
fi

# Ensure exec tool subprocesses get env vars
if ! grep -q "openclaw.env" "$OPENCLAW_HOME/.bashrc" 2>/dev/null; then
  echo '# Load OpenClaw env vars for exec tool subprocesses' >> "$OPENCLAW_HOME/.bashrc"
  echo '[ -f /etc/openclaw.env ] && set -a && source /etc/openclaw.env && set +a' >> "$OPENCLAW_HOME/.bashrc"
fi

# ── 2. Install Node.js + pnpm + OpenClaw ──────────────────────────
echo "[3/9] Installing Node.js, pnpm, and OpenClaw..."
sudo -iu "$OPENCLAW_USER" bash <<NODEEOF
  set -eo pipefail
  export SHELL=/bin/bash
  export OPENCLAW_VERSION="${OPENCLAW_VERSION}"

  # nvm
  if [ ! -d "\$HOME/.nvm" ]; then
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
  fi
  export NVM_DIR="\$HOME/.nvm"
  . "\$NVM_DIR/nvm.sh"
  nvm install --lts
  nvm use --lts
  nvm alias default lts/*

  # pnpm
  npm install -g pnpm
  pnpm setup
  export PNPM_HOME="\$HOME/.local/share/pnpm"
  export PATH="\$PNPM_HOME:\$PATH"

  # openclaw
  pnpm add -g "openclaw@\${OPENCLAW_VERSION}"
  echo "OpenClaw version: \$(openclaw --version)"
NODEEOF

# ── 3. Clone repo ────────────────────────────────────────────────
echo "[4/9] Cloning project repo..."
if [ ! -d "$REPO_DIR" ]; then
  sudo -u "$OPENCLAW_USER" git clone https://github.com/Rogue-Iteration/openclaw-do-gradient.git "$REPO_DIR"
else
  sudo -u "$OPENCLAW_USER" git -C "$REPO_DIR" pull origin main
fi

# ── 4. Install Python dependencies ──────────────────────────────
echo "[5/9] Installing Python dependencies..."
pip3 install --break-system-packages -r "$REPO_DIR/requirements.txt"

# ── 5. Configure OpenClaw ────────────────────────────────────────
echo "[6/9] Configuring OpenClaw..."
sudo -iu "$OPENCLAW_USER" bash <<CFGEOF
  set -euo pipefail
  export NVM_DIR="\$HOME/.nvm"
  . "\$NVM_DIR/nvm.sh"
  export PNPM_HOME="\$HOME/.local/share/pnpm"
  export PATH="\$PNPM_HOME:\$PATH"

  STATE_DIR="$STATE_DIR"
  WORKSPACE_DIR="$WORKSPACE_DIR"
  REPO_DIR="$REPO_DIR"

  mkdir -p "\$STATE_DIR" "\$WORKSPACE_DIR"

  # ── Write openclaw.json ──
  cat > "\$STATE_DIR/openclaw.json" <<'JSON'
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
        "apiKey": "\${GRADIENT_API_KEY}",
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
        "id": "web-researcher",
        "name": "Nova",
        "default": false,
        "workspace": "\\$HOME/.openclaw/agents/web-researcher/agent",
        "model": {
          "primary": "gradient/openai-gpt-oss-120b"
        }
      },
      {
        "id": "fundamental-analyst",
        "name": "Max",
        "default": true,
        "workspace": "\\$HOME/.openclaw/agents/fundamental-analyst/agent",
        "model": {
          "primary": "gradient/openai-gpt-oss-120b"
        }
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

  # ── Fix variable interpolation in apiKey (openclaw reads \${} from env) ──
  # The JSON above has a literal \${GRADIENT_API_KEY} which openclaw expands at runtime.

  # ── Generate gateway auth token ──
  GW_TOKEN=\$(head -c 32 /dev/urandom | base64 | tr -d '=/+' | head -c 32)
  jq --arg t "\$GW_TOKEN" '.gateway.auth.token = \$t | .gateway.auth.mode = "token"' \
    "\$STATE_DIR/openclaw.json" > "\$STATE_DIR/openclaw.json.tmp" \
    && mv "\$STATE_DIR/openclaw.json.tmp" "\$STATE_DIR/openclaw.json"
  echo "  ✓ Gateway token generated"

  # ── Telegram config ──
  if [ -n "${TELEGRAM_BOT_TOKEN:-}" ]; then
    jq --arg token "$TELEGRAM_BOT_TOKEN" \
      '.channels.telegram.enabled = true | .channels.telegram.botToken = \$token' \
      "\$STATE_DIR/openclaw.json" > "\$STATE_DIR/openclaw.json.tmp" \
      && mv "\$STATE_DIR/openclaw.json.tmp" "\$STATE_DIR/openclaw.json"
    echo "  ✓ Telegram configured"

    # Telegram sender allowlist
    if [ -n "${TELEGRAM_ALLOWED_IDS:-}" ]; then
      CREDS_DIR="\$STATE_DIR/credentials"
      mkdir -p "\$CREDS_DIR"
      echo "$TELEGRAM_ALLOWED_IDS" | tr ',' '\n' | jq -R . | jq -s '{version:1,allowFrom:.}' \
        > "\$CREDS_DIR/telegram-allowFrom.json"
      echo "  ✓ Telegram allowlist: $TELEGRAM_ALLOWED_IDS"
    fi
  fi

  # ── Exec approvals ──
  for pattern in \
    "python3" \
    "/usr/bin/python3" \
    "python3 *" \
    "cat" \
    "python" \
    "/usr/bin/python" \
    "python *" \
    "ls" \
    "head" \
    "tail" \
    "pip3"; do
    openclaw approvals allowlist add --target local --agent '*' --pattern "\$pattern" 2>/dev/null || true
  done
  echo "  ✓ Exec approvals configured"

  # ── Copy persona files for each agent ──
  for agent in ${AGENTS[@]}; do
    AGENT_WS="\$STATE_DIR/agents/\$agent/agent"
    mkdir -p "\$AGENT_WS"
    SRC_DIR="\$REPO_DIR/data/workspaces/\$agent"
    if [ -d "\$SRC_DIR" ]; then
      for f in IDENTITY.md AGENTS.md HEARTBEAT.md; do
        if [ -f "\$SRC_DIR/\$f" ]; then
          cp "\$SRC_DIR/\$f" "\$AGENT_WS/\$f"
        fi
      done
      echo "  ✓ Persona files copied for \$agent"
    fi
  done

  # ── Also copy shared persona files to root workspace (legacy compat) ──
  for f in IDENTITY.md AGENTS.md HEARTBEAT.md; do
    if [ -f "\$REPO_DIR/data/workspace/\$f" ]; then
      cp "\$REPO_DIR/data/workspace/\$f" "\$WORKSPACE_DIR/\$f"
    fi
  done
  echo "  ✓ Shared persona files copied"

  # ── Symlink skills for each agent ──
  for agent in ${AGENTS[@]}; do
    AGENT_WS="\$STATE_DIR/agents/\$agent/agent"
    SKILL_DIR="\$REPO_DIR/skills/\$agent"
    SHARED_SKILL_DIR="\$REPO_DIR/skills/gradient-research-assistant"

    # Agent-specific skills
    if [ -d "\$SKILL_DIR" ] && [ ! -e "\$AGENT_WS/skills/\$agent" ]; then
      mkdir -p "\$AGENT_WS/skills"
      ln -s "\$SKILL_DIR" "\$AGENT_WS/skills/\$agent"
    fi

    # Shared skills (so both agents can access common tools)
    if [ -d "\$SHARED_SKILL_DIR" ] && [ ! -e "\$AGENT_WS/skills/gradient-research-assistant" ]; then
      mkdir -p "\$AGENT_WS/skills"
      ln -s "\$SHARED_SKILL_DIR" "\$AGENT_WS/skills/gradient-research-assistant"
    fi
  done

  # ── Symlink shared skills (legacy compat) ──
  if [ ! -e "\$WORKSPACE_DIR/skills" ]; then
    ln -s "\$REPO_DIR/skills" "\$WORKSPACE_DIR/skills"
  fi
  echo "  ✓ Skills symlinked"
CFGEOF

# ── 6. Create systemd service ───────────────────────────────────
echo "[7/9] Creating systemd service..."
cat > /etc/systemd/system/openclaw.service <<EOF
[Unit]
Description=OpenClaw Gateway
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$OPENCLAW_USER
EnvironmentFile=$ENV_FILE
WorkingDirectory=$OPENCLAW_HOME

# Load nvm + pnpm in the service environment
ExecStart=/bin/bash -lc 'source \$HOME/.nvm/nvm.sh && export PNPM_HOME="\$HOME/.local/share/pnpm" && export PATH="\$PNPM_HOME:\$PATH" && exec openclaw gateway'

Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# ── 7. Start service ─────────────────────────────────────────────
echo "[8/9] Enabling and starting OpenClaw..."
systemctl daemon-reload
systemctl enable openclaw
systemctl start openclaw

# ── 8. Verify ─────────────────────────────────────────────────────
echo "[9/9] Verifying..."
sleep 5
if systemctl is-active --quiet openclaw; then
  echo ""
  echo "╔════════════════════════════════════════════╗"
  echo "║  ✅ OpenClaw is running!                   ║"
  echo "╚════════════════════════════════════════════╝"
  echo ""
  echo "Check status:    systemctl status openclaw"
  echo "View logs:       journalctl -u openclaw -f"
  echo "Deploy updates:  cd $REPO_DIR && bash deploy.sh"
else
  echo "⚠️  OpenClaw may not have started yet. Check: journalctl -u openclaw -f"
fi
