#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# Sync large/copyrighted assets to the production VM.
#
# These files are gitignored (and must stay so):
#   - frontend/public/models/    Whale 3D models (GLB)        ~47 MB
#   - frontend/public/species/   Species reference photos     ~447 MB
#   - frontend/public/wizard/    ID wizard images             ~25 MB
#   - data/processed/ml/photo_classifier/   EfficientNet-B4   ~68 MB
#   - data/processed/ml/audio_classifier/   XGBoost + CNN     ~44 MB
#
# Caddy on the VM serves /srv/static/* (== frontend/public/*) over HTTPS,
# and the backend bind-mounts /app/data/processed/ml from the host.
#
# Usage:
#   scripts/upload_assets.sh [user@host]
#
# Defaults to root@135.181.108.104 (Hetzner).
# ─────────────────────────────────────────────────────────────
set -euo pipefail

REMOTE="${1:-root@135.181.108.104}"
REMOTE_ROOT="/opt/marine-risk-mapping"

# rsync flags:
#   -a  archive (preserve perms/times)
#   -v  verbose
#   -z  compress in flight (big speedup on photos/JSON, mild for GLB/PT)
#   -h  human-readable sizes
#   --progress  per-file progress (works with macOS's ancient rsync 2.6.9
#               which lacks --info=progress2; install rsync via Homebrew
#               for a nicer single-bar UI: `brew install rsync`)
#   --delete  remove files on remote that no longer exist locally (safe within these dirs)
RSYNC=(rsync -avzh --progress --delete)

# Pre-create destination parent directories on the remote (rsync won't
# auto-create more than the final leaf dir).
ssh "${REMOTE}" "mkdir -p \
    ${REMOTE_ROOT}/frontend/public \
    ${REMOTE_ROOT}/data/processed/ml \
    ${REMOTE_ROOT}/data/uploads"

echo "→ Syncing frontend public assets to ${REMOTE}:${REMOTE_ROOT}/frontend/public/"
"${RSYNC[@]}" \
    frontend/public/models/ \
    "${REMOTE}:${REMOTE_ROOT}/frontend/public/models/"

"${RSYNC[@]}" \
    frontend/public/species/ \
    "${REMOTE}:${REMOTE_ROOT}/frontend/public/species/"

"${RSYNC[@]}" \
    frontend/public/wizard/ \
    "${REMOTE}:${REMOTE_ROOT}/frontend/public/wizard/"

echo "→ Syncing ML classifier artefacts to ${REMOTE}:${REMOTE_ROOT}/data/processed/ml/"
"${RSYNC[@]}" \
    data/processed/ml/photo_classifier/ \
    "${REMOTE}:${REMOTE_ROOT}/data/processed/ml/photo_classifier/"

"${RSYNC[@]}" \
    data/processed/ml/audio_classifier/ \
    "${REMOTE}:${REMOTE_ROOT}/data/processed/ml/audio_classifier/"

echo "→ Syncing user-uploaded media (sighting photos, avatars, event covers, vessel photos)"
# NOTE: no --delete on the uploads tree so we never wipe production-only
# uploads that aren't on this laptop.
rsync -avzh --progress \
    data/uploads/ \
    "${REMOTE}:${REMOTE_ROOT}/data/uploads/"

echo "✓ Done. Restart the stack on the VM if it was already running:"
echo "  ssh ${REMOTE} 'cd ${REMOTE_ROOT} && docker compose -f docker/docker-compose.prod.yml restart backend caddy'"
