-- wh_bateria tiene que estar en un rango creíble para este negocio (16.55 a 378.8).
select vuelo, wh_bateria from {{ ref('stg_parte') }}
where wh_bateria not between 16.55 and 378.8
