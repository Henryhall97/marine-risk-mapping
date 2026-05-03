#!/usr/bin/env bash
# Dump only the tables the production API queries.
# Skips:
#   - Climate-projection marts (42 GB) — not used in v1 demo
#   - Raw AIS pings (5 GB) — already aggregated into ais_h3_summary
#   - Heavy intermediate tables that the API doesn't read directly
#
# Result is a ~3 GB compressed custom-format dump suitable for
# scp + pg_restore on the production VM.
#
# Usage:
#   ./scripts/dump_prod_db.sh [output_path]
# Default output: ./db_dumps/marine_risk_prod_<date>.dump

set -euo pipefail

OUT="${1:-./db_dumps/marine_risk_prod_$(date +%Y%m%d).dump}"
mkdir -p "$(dirname "$OUT")"

# Tables the live FastAPI queries (mart layer + a few intermediates +
# raw zone tables). Audit with: grep -rh "FROM \w" backend/services/
TABLES=(
    # ── Marts (read directly by API) ────────────────────────
    public.fct_collision_risk
    public.fct_collision_risk_seasonal
    public.fct_collision_risk_ml
    public.fct_monthly_traffic
    public.fct_species_risk
    public.fct_whale_sdm_seasonal
    public.fct_whale_sdm_training
    public.fct_strike_risk_training

    # ── Pre-aggregated overview ─────────────────────────────
    public.macro_risk_overview

    # ── Intermediates the layer endpoints query ─────────────
    public.int_hex_grid
    public.int_bathymetry
    public.int_proximity
    public.int_ml_whale_predictions
    public.int_sdm_whale_predictions
    public.int_ocean_covariates
    public.int_ocean_covariates_seasonal
    public.int_vessel_traffic_seasonal
    public.int_nisi_reference_risk
    public.int_mpa_coverage
    public.int_speed_zone_coverage
    public.int_speed_zone_coverage_seasonal
    public.int_cetacean_density
    public.int_cetacean_density_seasonal
    public.int_ship_strike_density

    # ── ML prediction grids ─────────────────────────────────
    public.ml_whale_predictions
    public.ml_sdm_predictions

    # ── Reference / zones (small, all needed) ───────────────
    public.species_crosswalk
    public.cetacean_sightings
    public.cetacean_sighting_h3
    public.ship_strikes
    public.ship_strike_h3
    public.marine_protected_areas
    public.right_whale_speed_zones
    public.seasonal_management_areas
    public.cetacean_bia
    public.whale_critical_habitat
    public.shipping_lanes
    public.right_whale_slow_zones

    # ── User-generated content (created at API runtime) ─────
    public.users
    public.sighting_submissions
    public.sighting_verifications
    public.community_events
    public.event_members
    public.event_comments
    public.event_sightings
    public.violations
    public.media_files
    public.user_credentials
    public.reputation_events
    public.user_vessels
)

# Build -t flags
T_ARGS=()
for t in "${TABLES[@]}"; do
    T_ARGS+=(-t "$t")
done

echo "Dumping ${#TABLES[@]} tables to $OUT"
echo "(skipping climate projections, raw AIS, and unused intermediates)"

# Run pg_dump inside the running PostGIS container so we don't need
# postgresql-client installed on the host. The dump is written to a
# path inside the container then copied out.
CONTAINER="${MR_DB_CONTAINER:-marine_risk_postgis}"

if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo "ERROR: container '${CONTAINER}' is not running."
    echo "Start it with: cd docker && docker compose up -d"
    exit 1
fi

DUMP_NAME="$(basename "$OUT")"
echo "Running pg_dump inside container '${CONTAINER}'..."

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
        --no-owner \
        --no-acl \
        --verbose \
        "${T_ARGS[@]}" \
        -f "/tmp/${DUMP_NAME}"

echo "Copying dump out of container..."
docker cp "${CONTAINER}:/tmp/${DUMP_NAME}" "$OUT"
docker exec "$CONTAINER" rm -f "/tmp/${DUMP_NAME}"

echo
echo "Done: $OUT"
ls -lh "$OUT"
