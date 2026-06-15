-- Garrison et al. (2025) speed-lethality logistic.
--
--   P(lethal | speed) = 1 / (1 + exp(-(β₀ + β₁ × speed_knots)))
--
-- This macro emits the SQL expression for that probability given
-- references to the speed column and the β₀ / β₁ coefficient columns.
-- The coefficients live in the garrison_lethality_coeffs seed and are
-- joined onto the data (typically by whale_taxon × size_class) before
-- this macro is called — so the macro genuinely reads seed values
-- rather than hard-coding them.
--
-- Usage (inside int_vtd, joined to the 'generic' seed rows on
-- size_class as alias g):
--
--   {{ garrison_lethality('s.mean_implied_speed_kn', 'g.beta0', 'g.beta1') }}
--
-- speed is coalesced to 0 so a missing speed yields the intercept-only
-- probability rather than NULL.

{% macro garrison_lethality(speed_col, beta0_col='beta0', beta1_col='beta1') %}
(
    1.0
    / (
        1.0
        + exp(
            -1.0 * (
                ({{ beta0_col }})
                + ({{ beta1_col }}) * coalesce({{ speed_col }}, 0)
            )
        )
    )
)
{% endmacro %}
