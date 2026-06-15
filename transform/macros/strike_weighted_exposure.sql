-- Strike-weighted whale exposure macro (Phase 1b item G).
--
-- Builds a species-vulnerability-weighted whale exposure index:
--
--     Σ  P_i  ×  vuln_i        over the 6 ensembled species
--
-- where P_i is the ensembled per-species presence probability (the
-- *_whale_prob column aliases produced upstream) and vuln_i is the
-- relative lethal-strike vulnerability var `strike_vuln_<species>`.
--
-- Why this exists:
--   The whale×traffic interaction sub-score previously multiplied
--   traffic by `any_whale_prob`, which treats every species as equally
--   strike-prone.  Observed strike records are dominated by slow,
--   surface-active coastal baleen whales (North Atlantic right, fin,
--   humpback), while deep-diving sperm whales and small fast minke are
--   struck far less often.  Weighting each species' presence by its
--   vulnerability concentrates collision risk where the most
--   strike-prone whales actually are (Rockwood 2017/2021; IWC strike
--   database).  `any_whale_prob` is retained as a diagnostic column.
--
-- Requires the following per-species probability columns to be in
-- scope (they are emitted by the ensemble_prob() macro upstream):
--   right_whale_prob, fin_whale_prob, humpback_whale_prob,
--   blue_whale_prob, sperm_whale_prob, minke_whale_prob,
--   gray_whale_prob, rices_whale_prob

{% macro strike_weighted_exposure() %}
(
      {{ var('strike_vuln_right') }}    * coalesce(right_whale_prob, 0)
    + {{ var('strike_vuln_fin') }}      * coalesce(fin_whale_prob, 0)
    + {{ var('strike_vuln_humpback') }} * coalesce(humpback_whale_prob, 0)
    + {{ var('strike_vuln_blue') }}     * coalesce(blue_whale_prob, 0)
    + {{ var('strike_vuln_sperm') }}    * coalesce(sperm_whale_prob, 0)
    + {{ var('strike_vuln_minke') }}    * coalesce(minke_whale_prob, 0)
    + {{ var('strike_vuln_gray') }}     * coalesce(gray_whale_prob, 0)
    + {{ var('strike_vuln_rices') }}    * coalesce(rices_whale_prob, 0)
)
{% endmacro %}
