-- Ninguna fila se pierde en plata: tantas filas como vuelo distintos llegaron a bronce.
with bronce as (select count(distinct vuelo) as n from {{ source('bronce', 'parte') }}),
     plata  as (select count(*) as n from {{ ref('stg_parte') }})
select bronce.n as en_bronce, plata.n as en_plata from bronce, plata where bronce.n <> plata.n
