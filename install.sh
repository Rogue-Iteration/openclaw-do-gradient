#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
# OpenClaw + Gradient AI — Deploy to DigitalOcean Droplet
# ═══════════════════════════════════════════════════════════════════
#
# Preconditions:
#   1. You have filled out .env (see .env.example)
#   2. doctl is installed (https://docs.digitalocean.com/reference/doctl/how-to/install/)
#
# Usage:
#   bash install.sh              # create Droplet and deploy
#   bash install.sh --dry-run    # validate .env without creating resources
#   bash install.sh --update     # update an existing Droplet
#
# ═══════════════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"
DROPLET_NAME="openclaw-research"
DROPLET_SIZE="s-1vcpu-2gb"
DROPLET_IMAGE="docker-20-04"
REPO_URL="https://github.com/Rogue-Iteration/thebigclaw.git"
REMOTE_DIR="/opt/openclaw"

DRY_RUN=false
UPDATE_ONLY=false

# ── Parse arguments ──────────────────────────────────────────────
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=true ;;
    --update) UPDATE_ONLY=true ;;
  esac
done

# ── Helpers ──────────────────────────────────────────────────────
info()  { echo "  $1"; }
ok()    { echo "  ✓ $1"; }
fail()  { echo "  ✗ $1" >&2; exit 1; }

# ── 1. Validate .env ────────────────────────────────────────────
echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║  OpenClaw + Gradient AI — Deploy                         ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "[1/6] Validating .env..."

if [ ! -f "$ENV_FILE" ]; then
  fail ".env not found. Run: cp .env.example .env"
fi

# Source env file
set -a
source "$ENV_FILE"
set +a

REQUIRED_VARS=(GRADIENT_API_KEY TELEGRAM_BOT_TOKEN DO_API_TOKEN DO_SPACES_ACCESS_KEY DO_SPACES_SECRET_KEY)
MISSING=()
for var in "${REQUIRED_VARS[@]}"; do
  if [ -z "${!var:-}" ]; then
    MISSING+=("$var")
  fi
done

if [ ${#MISSING[@]} -gt 0 ]; then
  echo "  Missing required variables in .env:"
  for var in "${MISSING[@]}"; do
    echo "    - $var"
  done
  fail "Fill in these values in .env and try again."
fi
ok "All required variables set"

if $DRY_RUN; then
  echo ""
  echo "✅ Dry run passed — .env is valid."
  echo "   Run without --dry-run to deploy."
  exit 0
fi

# ── 2. Check doctl ──────────────────────────────────────────────
echo ""
echo "[2/6] Checking doctl..."

if ! command -v doctl &>/dev/null; then
  echo "  doctl is not installed."
  echo ""
  echo "  Install it:"
  echo "    macOS:  brew install doctl"
  echo "    Linux:  snap install doctl"
  echo "    Other:  https://docs.digitalocean.com/reference/doctl/how-to/install/"
  fail "Install doctl and try again."
fi
ok "doctl found"

# ── 3. Authenticate with DigitalOcean ───────────────────────────
echo ""
echo "[3/6] Authenticating with DigitalOcean..."

doctl auth init -t "$DO_API_TOKEN" 2>/dev/null
ok "Authenticated"

# ── 4. Handle update vs fresh deploy ────────────────────────────
if $UPDATE_ONLY; then
  echo ""
  echo "[4/6] Updating existing Droplet..."

  DROPLET_IP=$(doctl compute droplet list --format Name,PublicIPv4 --no-header | grep "^$DROPLET_NAME" | awk '{print $2}')
  if [ -z "$DROPLET_IP" ]; then
    fail "Droplet '$DROPLET_NAME' not found. Run without --update to create it."
  fi
  ok "Found Droplet at $DROPLET_IP"

  echo ""
  echo "[5/6] Deploying update..."
  scp -o StrictHostKeyChecking=no "$ENV_FILE" "root@$DROPLET_IP:$REMOTE_DIR/.env"
  ssh -o StrictHostKeyChecking=no "root@$DROPLET_IP" \
    "cd $REMOTE_DIR && git pull origin main && docker compose up -d --build"
  ok "Update deployed"

  echo ""
  echo "[6/6] Verifying..."
  sleep 5
  if ssh -o StrictHostKeyChecking=no "root@$DROPLET_IP" "docker ps --filter name=openclaw-research --format '{{.Status}}'" | grep -q "Up"; then
    echo ""
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║  ✅ Update deployed successfully!                        ║"
    echo "╚════════════════════════════════════════════════════════════╝"
  else
    echo "⚠️  Container may not be healthy. Check:"
    echo "   ssh root@$DROPLET_IP docker logs openclaw-research"
  fi
  exit 0
fi

# ── 4. Create Droplet ────────────────────────────────────────────
echo ""
echo "[4/6] Creating Droplet..."

# Check if Droplet already exists
EXISTING_IP=$(doctl compute droplet list --format Name,PublicIPv4 --no-header | grep "^$DROPLET_NAME" | awk '{print $2}')
if [ -n "$EXISTING_IP" ]; then
  echo "  Droplet '$DROPLET_NAME' already exists at $EXISTING_IP"
  echo "  Use --update to deploy changes, or delete and re-run."
  fail "Droplet already exists."
fi

# Pick region
echo "  Available regions: nyc1 nyc3 sfo3 ams3 lon1 fra1 sgp1 blr1 tor1"
read -rp "  Region [nyc3]: " REGION
REGION="${REGION:-nyc3}"

# SSH key
SSH_KEYS=$(doctl compute ssh-key list --format ID,Name --no-header)
if [ -z "$SSH_KEYS" ]; then
  echo "  No SSH keys found in your DO account."
  echo "  Add one: doctl compute ssh-key import my-key --public-key-file ~/.ssh/id_rsa.pub"
  fail "Add an SSH key to DigitalOcean and try again."
fi

echo "  Your SSH keys:"
echo "$SSH_KEYS" | while IFS= read -r line; do echo "    $line"; done
read -rp "  SSH key ID to use: " SSH_KEY_ID

info "Creating $DROPLET_NAME ($DROPLET_SIZE in $REGION)..."
doctl compute droplet create "$DROPLET_NAME" \
  --image "$DROPLET_IMAGE" \
  --size "$DROPLET_SIZE" \
  --region "$REGION" \
  --ssh-keys "$SSH_KEY_ID" \
  --wait

DROPLET_IP=$(doctl compute droplet get "$DROPLET_NAME" --format PublicIPv4 --no-header)
ok "Droplet created at $DROPLET_IP"

# ── 5. Wait for SSH and deploy ──────────────────────────────────
echo ""
echo "[5/6] Deploying to Droplet..."

info "Waiting for SSH to become available..."
for i in $(seq 1 30); do
  if ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 "root@$DROPLET_IP" true 2>/dev/null; then
    break
  fi
  sleep 5
done
ok "SSH connected"

# Clone repo, copy .env, start containers
info "Cloning repository..."
ssh -o StrictHostKeyChecking=no "root@$DROPLET_IP" \
  "git clone $REPO_URL $REMOTE_DIR 2>/dev/null || (cd $REMOTE_DIR && git pull origin main)"

info "Uploading .env..."
scp -o StrictHostKeyChecking=no "$ENV_FILE" "root@$DROPLET_IP:$REMOTE_DIR/.env"

info "Starting Docker containers..."
ssh -o StrictHostKeyChecking=no "root@$DROPLET_IP" \
  "cd $REMOTE_DIR && docker compose up -d --build"
ok "Containers started"

# ── 6. Verify ───────────────────────────────────────────────────
echo ""
echo "[6/6] Verifying..."
sleep 10

if ssh -o StrictHostKeyChecking=no "root@$DROPLET_IP" "docker ps --filter name=openclaw-research --format '{{.Status}}'" | grep -q "Up"; then
  echo ""
  echo "╔════════════════════════════════════════════════════════════╗"
  echo "║  ✅ OpenClaw is running!                                  ║"
  echo "╚════════════════════════════════════════════════════════════╝"
  echo ""
  echo "  Droplet IP:    $DROPLET_IP"
  echo "  SSH access:    ssh root@$DROPLET_IP"
  echo "  View logs:     ssh root@$DROPLET_IP docker logs -f openclaw-research"
  echo "  Update:        bash install.sh --update"
  echo ""
  echo "  📱 NEXT STEP: Pair your Telegram account."
  echo "     1. Send a message to your bot on Telegram"
  echo "     2. It will reply with a pairing code"
  echo "     3. Run: ssh root@$DROPLET_IP docker exec openclaw-research openclaw pairing approve telegram <CODE>"
  echo ""
else
  echo "⚠️  Container may not be healthy yet. Check:"
  echo "   ssh root@$DROPLET_IP docker logs openclaw-research"
fi
