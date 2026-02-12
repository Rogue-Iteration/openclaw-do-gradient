FROM ubuntu:noble

# Use bash for the shell
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ARG TARGETARCH=amd64
ARG OPENCLAW_VERSION=2026.2.9
ARG S6_OVERLAY_VERSION=3.2.1.0
ARG RESTIC_VERSION=0.17.3
ARG YQ_VERSION=4.44.3
ARG OPENCLAW_STATE_DIR=/data/.openclaw
ARG OPENCLAW_WORKSPACE_DIR=/data/workspace

ENV OPENCLAW_STATE_DIR=${OPENCLAW_STATE_DIR}
ENV OPENCLAW_WORKSPACE_DIR=${OPENCLAW_WORKSPACE_DIR}
ENV NODE_ENV=production
ENV DEBIAN_FRONTEND=noninteractive
ENV S6_KEEP_ENV=1
ENV S6_BEHAVIOUR_IF_STAGE2_FAILS=2
ENV S6_CMD_WAIT_FOR_SERVICES_MAXTIME=0
ENV S6_LOGGING=0

# Install OS deps + Python + restic + s6-overlay
RUN set -eux; \
  apt-get update; \
  apt-get install -y --no-install-recommends \
  ca-certificates \
  wget \
  unzip \
  vim \
  curl \
  git \
  gh \
  gnupg \
  openssl \
  jq \
  sudo \
  bzip2 \
  cron \
  build-essential \
  procps \
  xz-utils \
  python3 \
  python3-pip \
  python3-venv; \
  # Install restic
  RESTIC_ARCH="$( [ "$TARGETARCH" = "arm64" ] && echo arm64 || echo amd64 )"; \
  wget -q -O /tmp/restic.bz2 \
  https://github.com/restic/restic/releases/download/v${RESTIC_VERSION}/restic_${RESTIC_VERSION}_linux_${RESTIC_ARCH}.bz2; \
  bunzip2 /tmp/restic.bz2; \
  mv /tmp/restic /usr/local/bin/restic; \
  chmod +x /usr/local/bin/restic; \
  # Install yq for YAML parsing
  YQ_ARCH="$( [ "$TARGETARCH" = "arm64" ] && echo arm64 || echo amd64 )"; \
  wget -q -O /usr/local/bin/yq \
  https://github.com/mikefarah/yq/releases/download/v${YQ_VERSION}/yq_linux_${YQ_ARCH}; \
  chmod +x /usr/local/bin/yq; \
  # Install s6-overlay
  S6_ARCH="$( [ "$TARGETARCH" = "arm64" ] && echo aarch64 || echo x86_64 )"; \
  wget -O /tmp/s6-overlay-noarch.tar.xz \
  https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-noarch.tar.xz; \
  wget -O /tmp/s6-overlay-arch.tar.xz \
  https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-${S6_ARCH}.tar.xz; \
  tar -C / -Jxpf /tmp/s6-overlay-noarch.tar.xz; \
  tar -C / -Jxpf /tmp/s6-overlay-arch.tar.xz; \
  rm /tmp/s6-overlay-*.tar.xz; \
  # Cleanup
  apt-get clean; \
  rm -rf /var/lib/apt/lists/*

# Install Python dependencies for the research skill
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages -r /tmp/requirements.txt && rm /tmp/requirements.txt

# Apply rootfs overlay early - allows user creation to use existing home directories
COPY rootfs/ /

# Apply build-time permissions from config
RUN source /etc/s6-overlay/lib/env-utils.sh && apply_permissions

# Create non-root user (using existing home directory from rootfs)
RUN useradd -m -s /bin/bash openclaw \
  && mkdir -p "${OPENCLAW_STATE_DIR}" "${OPENCLAW_WORKSPACE_DIR}" \
  && ln -s ${OPENCLAW_STATE_DIR} /home/openclaw/.openclaw \
  && chown -R openclaw:openclaw /data \
  && chown -R openclaw:openclaw /home/openclaw

# Create pnpm directory (nvm/pnpm paths are set in openclaw user's .bashrc, not globally)
RUN mkdir -p /home/openclaw/.local/share/pnpm && chown -R openclaw:openclaw /home/openclaw/.local

USER openclaw

# Install nvm, Node.js LTS, pnpm, and openclaw
RUN export SHELL=/bin/bash  && export NVM_DIR="$HOME/.nvm" \
  && curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash \
  && . "$NVM_DIR/nvm.sh" \
  && nvm install --lts \
  && nvm use --lts \
  && nvm alias default lts/* \
  && npm install -g pnpm \
  && pnpm setup \
  && export PNPM_HOME="/home/openclaw/.local/share/pnpm" \
  && export PATH="$PNPM_HOME:$PATH" \
  && pnpm add -g "openclaw@${OPENCLAW_VERSION}"

# Switch back to root for final setup
USER root

# Fix ownership for any files in home directories (in case ubuntu user exists)
RUN if [ -d /home/ubuntu ]; then chown -R ubuntu:ubuntu /home/ubuntu; fi

# Generate initial package selections list (for restore capability)
RUN dpkg --get-selections > /etc/openclaw/dpkg-selections

# s6-overlay init (must run as root, services drop privileges as needed)
ENTRYPOINT ["/init"]
