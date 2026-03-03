-- Macro: map a numeric risk score (0–1) to a category label.
-- Thresholds are read from dbt_project.yml vars so all marts
-- stay in sync with pipeline/config.py.
--
-- Usage:  {{ risk_category('risk_score') }}

{% macro risk_category(score_col) %}
case
    when {{ score_col }} >= {{ var('risk_threshold_critical') }} then 'critical'
    when {{ score_col }} >= {{ var('risk_threshold_high') }}     then 'high'
    when {{ score_col }} >= {{ var('risk_threshold_medium') }}   then 'medium'
    when {{ score_col }} >= {{ var('risk_threshold_low') }}      then 'low'
    else 'minimal'
end
{% endmacro %}
