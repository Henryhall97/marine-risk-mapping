#!/usr/bin/env bash
# Dump only the climate-projection tables (not part of the main prod dump
# because they're huge — ~10-15 GB compressed).
#
# Usage:
#   ./scripts/dump_projections.sh [output_path]
# Default output: ./db_dumps/marine_risk_projections_<date>.dump
set -euo pipefail

OUT="${1:-./db_dumps/marine_risk_projections_$(date +%Y%m%d).dump}"
mkdir -p "$(dirname "$OUT")"

TABLES=(
    public.fct_collision_risk_ml_projected   # 19 GB / 58 M rows
    public.whale_sdm_projections             # 12 GB / 58 M rows
    public.whale_isdm_projections            # 11 GB / 58 M rows
    public.int_ocean_covariates_projected    #  9 GB / 62 M rows (joined for ocean projection layer)
)

T_ARGS=()
for t in "${TABLES[@]}"; do T_ARGS+=(-t "$t"); done

CONTAINER="${MR_DB_CONTAINER:-marine_risk_postgis}"
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo "ERROR: container '${CONTAINER}' is not running."; exit 1
fi

DUMP_NAME="$(basename "$OUT")"
echo "Dumping ${#TABLES[@]} projection tables to $OUT"
echo "(expect 10-15 GB compressed, 30-60 min)"

docker exec \
    -e PGPASSWORD="${MR_DB_PASSWORD:-marine_dev}" \
    "$CONTAINER" \
    pg_dump \
        --host=localhost \
        --port=5432 \
        --username="${MR_DB_USER:-marine}" \
        --dbname="${MR_DB_NAME:-marine_risk}" \
        --format=custom \
        --compress=9 \
        --no-owner --no-acl \
        "${T_ARGS[@]}" \
        --file="/tmp/${DUMP_NAME}"

docker cp "${CONTAINER}:/tmp/${DUMP_NAME}" "$OUT"
docker exec "$CONTAINER" rm -f "/tmp/${DUMP_NAME}"

echo "✓ Wrote $(ls -lh "$OUT" | awk '{print $5}') to $OUT"
