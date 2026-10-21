{# Los modelos que empiezan por stg_ van a plata; el resto, a oro. #}
{%- macro external_location(relation, config) -%}
  {%- set capa = 'plata' if relation.identifier.startswith('stg_') else 'oro' -%}
  lakehouse/{{ capa }}/{{ relation.identifier }}.parquet
{%- endmacro -%}
