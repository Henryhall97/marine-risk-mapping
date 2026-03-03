-- Macro: map a month integer (1–12) to a season name.
-- Uses the season definitions from dbt_project.yml vars.
-- Returns a SQL CASE expression that can be embedded in models.
--
-- Usage:  {{ season_from_month('extract(month from my_date)::int') }}

{% macro season_from_month(month_expr) %}
case
    when {{ month_expr }} in ({{ var('season_winter_months') | join(', ') }})
        then 'winter'
    when {{ month_expr }} in ({{ var('season_spring_months') | join(', ') }})
        then 'spring'
    when {{ month_expr }} in ({{ var('season_summer_months') | join(', ') }})
        then 'summer'
    when {{ month_expr }} in ({{ var('season_fall_months') | join(', ') }})
        then 'fall'
end
{% endmacro %}
