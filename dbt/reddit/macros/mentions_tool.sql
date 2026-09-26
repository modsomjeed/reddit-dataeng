{#
    True when `text` mentions the tool in the current `tools` row, as a whole word.
    Phrases in exclude_pattern are blanked out first, because they reuse the tool's
    word for something else (e.g. "sql server agent" for AI Agent). dbt-clickhouse
    loads empty seed cells as '', not NULL, hence the coalesce.
#}
{% macro mentions_tool(text) %}
    match(
        if(
            coalesce(tools.exclude_pattern, '') = '',
            {{ text }},
            replaceRegexpAll({{ text }}, concat('\\b(', tools.exclude_pattern, ')\\b'), ' ')
        ),
        concat('\\b(', tools.pattern, ')\\b')
    )
{% endmacro %}
