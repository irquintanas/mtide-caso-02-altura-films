-- PLATA · el parte diario limpio: la limpieza que hiciste en la J3, ahora como modelo dbt.
-- Cada entrega del parte es una carpeta fecha_carga=… en bronce: aquí se leen todas juntas.
with bruto as (
    select *, parse_filename(filename) as archivo
    from {{ source('bronce', 'parte') }}
),
sin_dup as (
    -- una fila por vuelo
    select * from bruto
    qualify row_number() over (partition by vuelo order by fecha_carga desc) = 1
),
mediana_encargo as (
    select encargo, median(minutos_vuelo::integer) as minutos_vuelo_mediana
    from sin_dup
    where minutos_vuelo::integer between 1 and 240
    group by encargo
)
select
    s.vuelo,
    s.fecha::date                                              as fecha,
    upper(trim(s.piloto))                                         as piloto,
    s.dron,
    s.encargo,
    case when s.minutos_vuelo::integer between 1 and 240 then s.minutos_vuelo::integer
         else round(m.minutos_vuelo_mediana)::integer end               as minutos_vuelo,
    not (s.minutos_vuelo::integer between 1 and 240)                   as minutos_vuelo_corregido,
    s.wh_bateria::double                                              as wh_bateria,
    s.importe_eur::double                                      as importe_eur,
    s.incidencia,
    s.archivo,
    s.fecha_carga
from sin_dup s
join mediana_encargo m using (encargo)
