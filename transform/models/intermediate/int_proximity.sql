-- Intermediate model: proximity features per hex cell
--
-- Wraps the pre-computed cell_proximity table produced by
-- pipeline/aggregation/compute_proximity.py (scipy KDTree
-- with haversine post-correction).
--
-- Two distance features:
--   - dist_to_nearest_whale_km: how far is the nearest whale sighting?
--   - dist_to_nearest_ship_km:  how far is the nearest shipping lane?
--
-- Also derives decay scores (0–1) using an exponential decay
-- with a 10km half-life — turns raw distance into a smooth
-- proximity signal for the risk model.
--
-- Grain: one row per h3_cell.

select
    h3_cell,

    -- Raw distances
    round(dist_to_nearest_whale_km::numeric, 2)  as dist_to_nearest_whale_km,
    round(dist_to_nearest_ship_km::numeric, 2)   as dist_to_nearest_ship_km,

    -- Proximity decay scores (1.0 = on top of feature, → 0 with distance)
    -- Half-life = 10km: at 10km score ≈ 0.5, at 30km score ≈ 0.125
    -- Clamp to floor of 0 for cells >700km away (exp underflows in Postgres)
    case
        when dist_to_nearest_whale_km > 700 then 0.0
        else exp(-0.0693 * dist_to_nearest_whale_km)
    end as whale_proximity_score,
    case
        when dist_to_nearest_ship_km > 700 then 0.0
        else exp(-0.0693 * dist_to_nearest_ship_km)
    end as ship_proximity_score

from {{ source('marine_risk', 'cell_proximity') }}
