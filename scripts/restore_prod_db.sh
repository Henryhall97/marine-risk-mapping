#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
# Restore a production DB dump on the VM.
#
# Expects:
#   - docker-compose.prod.yml stack with `postgis` service running and healthy
#   - A *.dump file in ./db_dumps/ (mounted into the container as /dumps:ro)
#   - .env with POSTGRES_USER + POSTGRES_DB set
#
# Usage:
#   bash scripts/restore_prod_db.sh
#   bash scripts/restore_prod_db.sh path/to/specific.dump
# ─────────────────────────────────────────────────────────────────
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ -f .env ]]; then
    set -a; source .env; set +a
fi

PG_USER="${POSTGRES_USER:-marine}"
PG_DB="${POSTGRES_DB:-marine_risk}"
CONTAINER="${PG_CONTAINER:-marine_risk_postgis_prod}"
JOBS="${RESTORE_JOBS:-4}"

if [[ $# -ge 1 ]]; then
    DUMP_HOST="$1"
else
    # Pick the most recent dump in db_dumps/.
    DUMP_HOST=$(ls -t db_dumps/marine_risk_prod_*.dump 2>/dev/null | head -1 || true)
fi

if [[ -z "${DUMP_HOST:-}" || ! -f "$DUMP_HOST" ]]; then
    echo "✗ No dump file found. Place one in ./db_dumps/" >&2
    exit 1
fi

DUMP_NAME=$(basename "$DUMP_HOST")
DUMP_IN_CONTAINER="/dumps/${DUMP_NAME}"

echo "▶ Restoring $DUMP_NAME → $PG_DB (jobs=$JOBS)"
echo "  Container: $CONTAINER"

# Confirm container is up + healthy
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo "✗ Container $CONTAINER is not running. Start it first:" >&2
    echo "    docker compose -f docker/docker-compose.prod.yml up -d postgis" >&2
    exit 1
fi

# Wait for ready
for i in {1..30}; do
    if docker exec "$CONTAINER" pg_isready -U "$PG_USER" >/dev/null 2>&1; then
        break
    fi
    echo "  Waiting for Postgres... ($i/30)"
    sleep 2
done

echo "▶ Running pg_restore (this can take 5–10 min)..."
docker exec "$CONTAINER" pg_restore \
    --username="$PG_USER" \
    --dbname="$PG_DB" \
    --jobs="$JOBS" \
    --no-owner --no-acl \
    --verbose \
    "$DUMP_IN_CONTAINER"

echo ""
echo "▶ Sanity checks:"
docker exec "$CONTAINER" psql -U "$PG_USER" -d "$PG_DB" -c \
    "SELECT 'fct_collision_risk' AS table, count(*) FROM fct_collision_risk
     UNION ALL SELECT 'fct_collision_risk_seasonal', count(*) FROM fct_collision_risk_seasonal
     UNION ALL SELECT 'macro_risk_overview', count(*) FROM macro_risk_overview
     UNION ALL SELECT 'species_crosswalk', count(*) FROM species_crosswalk;"

echo ""
echo "✓ Restore complete."
