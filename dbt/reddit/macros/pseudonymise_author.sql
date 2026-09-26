{#
    Usernames are personal data: keep a salted hash so authors can still be
    counted and grouped, but not looked up. '[deleted]' accounts get no id.
#}
{% macro pseudonymise_author(column) %}
    if(
        {{ column }} = '[deleted]',
        null,
        lower(hex(SHA256(concat('{{ env_var("PII_HASH_SALT") }}', {{ column }}))))
    )
{% endmacro %}
