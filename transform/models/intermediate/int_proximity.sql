-- Intermediate model: proximity features per hex cell
--
-- Wraps the pre-computed cell_proximity table produced by
-- pipeline/aggregation/compute_proximity.py (scipy KDTree
-- with haversine post-correction).
--
-- Four distance features:
--   - dist_to_nearest_whale_km:      nearest whale sighting
--   - dist_to_nearest_ship_km:       nearest shipping lane
--   - dist_to_nearest_strike_km:     nearest historical strike
--   - dist_to_nearest_protection_km: nearest SMA / speed zone
--
-- Also derives exponential decay scores (0–1) for each,
-- turning raw distance into a smooth proximity signal.
--
-- Grain: one row per h3_cell.

select
    h3_cell,

    -- Raw distances
    round(dist_to_nearest_whale_km::numeric, 2)      as dist_to_nearest_whale_km,
    round(dist_to_nearest_ship_km::numeric, 2)        as dist_to_nearest_ship_km,
    round(dist_to_nearest_strike_km::numeric, 2)      as dist_to_nearest_strike_km,
    round(dist_to_nearest_protection_km::numeric, 2)  as dist_to_nearest_protection_km,

    -- Whale proximity (half-life = 10km: ln(2)/10 ≈ 0.0693)
    case
        when dist_to_nearest_whale_km > 700 then 0.0
        else exp(-0.0693 * dist_to_nearest_whale_km)
    end as whale_proximity_score,

    -- Ship proximity (half-life = 10km)
    case
        when dist_to_nearest_ship_km > 700 then 0.0
        else exp(-0.0693 * dist_to_nearest_ship_km)
    end as ship_proximity_score,

    -- Strike proximity (half-life = 25km: ln(2)/25 ≈ 0.0277)
    -- Broader half-life because 67 cells is sparse coverage
    case
        when dist_to_nearest_strike_km > 700 then 0.0
        else exp(-0.0277 * dist_to_nearest_strike_km)
    end as strike_proximity_score,

    -- Protection proximity (half-life = 50km: ln(2)/50 ≈ 0.01386)
    -- Broad radius — zones have wide spatial influence
    case
        when dist_to_nearest_protection_km > 1000 then 0.0
        else exp(-0.01386 * dist_to_nearest_protection_km)
    end as protection_proximity_score

from {{ source('marine_risk', 'cell_proximity') }}
