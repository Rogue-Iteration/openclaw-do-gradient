# ═══════════════════════════════════════════════════════════════════
# OpenClaw + Gradient AI — Docker Image
# ═══════════════════════════════════════════════════════════════════
# Multi-stage build: Node.js (OpenClaw gateway) + Python (skill scripts)
#
# Build:  docker build -t openclaw-research .
# Run:    docker compose up -d
# ═══════════════════════════════════════════════════════════════════

# ── Stage 1: Node.js + OpenClaw ──────────────────────────────────
FROM node:22-slim AS base
# Install git + SSL certs (needed by openclaw dependency: baileys → libsignal-node)
RUN apt-get update -qq && apt-get install -y --no-install-recommends git ca-certificates && \
  apt-get clean && rm -rf /var/lib/apt/lists/*

# Install pnpm and OpenClaw globally
RUN corepack enable && corepack prepare pnpm@latest --activate
ENV PNPM_HOME="/root/.local/share/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
RUN mkdir -p "$PNPM_HOME"
ARG OPENCLAW_VERSION=2026.2.9
RUN pnpm add -g "openclaw@${OPENCLAW_VERSION}"

# ── Stage 2: Add Python + skill dependencies ────────────────────
FROM base AS runtime

# System packages: Python 3, pip, and build tools for native deps
RUN apt-get update -qq && \
  apt-get install -y --no-install-recommends \
  python3 python3-pip python3-venv build-essential jq && \
  apt-get clean && \
  rm -rf /var/lib/apt/lists/*

# Install Python dependencies (production only)
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --break-system-packages --no-cache-dir -r /tmp/requirements.txt && \
  rm /tmp/requirements.txt

# ── App files ────────────────────────────────────────────────────
WORKDIR /app
COPY skills/ ./skills/
COPY data/ ./data/

# ── Entrypoint setup script ─────────────────────────────────────
# This script configures OpenClaw on first run (agent workspaces,
# persona files, skill symlinks, openclaw.json) then starts the gateway.
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# OpenClaw state directory — mount a volume here for persistence
# OpenClaw uses ~/.openclaw/ by default (= /root/.openclaw/ as root)
VOLUME /root/.openclaw

EXPOSE 3120

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["openclaw", "gateway"]
