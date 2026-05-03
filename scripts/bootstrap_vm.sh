#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
# One-shot VM bootstrap for Marine Risk Mapping production deploy.
#
# Run as root on a fresh Ubuntu 24.04 VM (Hetzner / DO / EC2):
#
#     curl -fsSL https://raw.githubusercontent.com/Henryhall97/marine-risk-mapping/main/scripts/bootstrap_vm.sh | bash
#
# Or after `git clone`:
#     bash scripts/bootstrap_vm.sh
#
# What it does:
#   1. apt update + install Docker, git, ufw
#   2. Configure firewall (22, 80, 443)
#   3. Clone the repo to /opt/marine-risk-mapping (if not already there)
#   4. Print next-step instructions
# ─────────────────────────────────────────────────────────────────
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "Run as root (or with sudo)." >&2
    exit 1
fi

REPO_URL="${REPO_URL:-https://github.com/Henryhall97/marine-risk-mapping.git}"
INSTALL_DIR="${INSTALL_DIR:-/opt/marine-risk-mapping}"

echo "▶ Updating system packages..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get -y -qq upgrade
apt-get -y -qq install ca-certificates curl gnupg git ufw

echo "▶ Installing Docker..."
if ! command -v docker >/dev/null 2>&1; then
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
        | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
        > /etc/apt/sources.list.d/docker.list
    apt-get update -qq
    apt-get -y -qq install \
        docker-ce docker-ce-cli containerd.io \
        docker-buildx-plugin docker-compose-plugin
else
    echo "  Docker already installed, skipping."
fi

echo "▶ Configuring firewall..."
ufw allow 22/tcp >/dev/null
ufw allow 80/tcp >/dev/null
ufw allow 443/tcp >/dev/null
ufw --force enable >/dev/null

echo "▶ Cloning repo to $INSTALL_DIR..."
if [[ ! -d "$INSTALL_DIR/.git" ]]; then
    git clone "$REPO_URL" "$INSTALL_DIR"
else
    echo "  Repo already present, pulling latest."
    git -C "$INSTALL_DIR" pull --ff-only
fi

mkdir -p "$INSTALL_DIR/db_dumps"

cat <<EOF

═══════════════════════════════════════════════════════════════
✓ VM bootstrap complete.

Next steps:

  1. Create .env from the template:
       cd $INSTALL_DIR
       cp .env.prod.example .env
       # Generate secrets:
       echo "POSTGRES_PASSWORD=\$(openssl rand -base64 32)"
       echo "MR_JWT_SECRET=\$(openssl rand -hex 32)"
       nano .env

  2. From your LOCAL machine, scp the DB dump up:
       scp -C db_dumps/marine_risk_prod_*.dump \\
           root@<this-vm-ip>:$INSTALL_DIR/db_dumps/

  3. Start Postgres and restore:
       cd $INSTALL_DIR
       docker compose -f docker/docker-compose.prod.yml up -d postgis
       sleep 15  # let it become healthy
       bash scripts/restore_prod_db.sh

  4. Bring up the full stack:
       docker compose -f docker/docker-compose.prod.yml up -d --build

  5. Verify:
       curl https://api.whalewatch.uk/health

═══════════════════════════════════════════════════════════════
EOF
