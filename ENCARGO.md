# Caso 02 · Altura Films — el encargo

> Negocio y datos **ficticios**, creados para la asignatura. Es tu mismo caso de la J3.

## Qué ha pasado desde la J3

En la J3 limpiaste el parte en un cuaderno y contestaste tres preguntas. Altura Films quiere su parte de vuelos al día y sin tocarlo a mano. Además, la aseguradora pide pruebas de que no se vuela con viento fuerte, y el sistema de los drones ya registra despegues y aterrizajes.

Ahora conviertes aquel cuaderno en un **lakehouse** de verdad, en tu propio repositorio, y publicas un **portal** que
cuenta lo que has hecho. Cómo preparar el repositorio y el ciclo de trabajo de cada bloque: [README.md](README.md).

## Lo que tienes al empezar

- En bronce, el parte de la J3: `lakehouse/bronce/parte/fecha_carga=2026-04-13/`.
- En `dbt/models/plata/stg_parte.sql`, la limpieza que hiciste en la J3, con unos tests básicos (`_plata.yml`, `dbt/tests/`).
- `dbt build` en verde. La capa oro, vacía: la construyes tú.
- En `paginas/`, las cuatro páginas del portal que escribirás, cada una con un guion de lo que debe contar.

**Bronce no se toca nunca**: todo arreglo va en plata.

---

## Bloque 1 · La remesa nueva · rama `remesa`

1. `python herramientas/sistema_simulado.py remesa`: llega una entrega nueva del parte en `bronce/parte/fecha_carga=2026-04-23/` (unos diez días más de vuelos).
2. `dbt build --project-dir dbt --profiles-dir dbt`. Los pilotos estrenan una app que escribe la duración del vuelo «como la diría una persona». `dbt build` ni siquiera llega a los tests.

   > 🔎 **Pista · mirar dentro antes de arreglar.** `dbt build` te dice *dónde* duele, no *por qué*.
   > Para eso tienes `dbt show`: ejecuta una consulta y te enseña el resultado sin construir nada.
   >
   > ```bash
   > dbt show --project-dir dbt --profiles-dir dbt --select <un_test>
   > dbt show --project-dir dbt --profiles-dir dbt --inline "select ... from {{ ref('<modelo>') }} ..."
   > dbt show --project-dir dbt --profiles-dir dbt --inline "select ... from {{ source('bronce', 'parte') }} ..."
   > ```
   >
   > El primero te enseña las filas que un test rechaza. Los otros dos te dejan preguntar lo que quieras
   > a plata o a bronce tal como llegó. Antes de tocar el SQL, intenta contestar tres preguntas:
   > **¿qué filas?**, **¿desde cuándo?** y **¿venía ya así en bronce?** Bronce guarda cada entrega en su
   > carpeta `fecha_carga=…`, y esa columna te deja comparar una entrega con otra.
   >
   > *Aquí el modelo ni se construye: no hay test que consultar y lo que haya en plata es de la ejecución anterior. Lee bien el mensaje de error (te dice la columna y el valor) y pregunta directamente a bronce cuántas filas son así y en qué entrega.*

3. Arregla `dbt/models/plata/stg_parte.sql` hasta que `dbt build` quede en verde y el problema esté resuelto (no siempre hay un test que lo grite: a veces tienes que escribirlo tú). Deja un comentario en el SQL: **qué** venía mal y **por qué** lo arreglas así.
4. Escribe `paginas/1-remesa.md`.
5. Pull request en tu repositorio, Actions en verde y lo fusionas.

## Bloque 2 · El oro · rama `oro`

Crea en `dbt/models/oro/` estos modelos, **con estos nombres exactos** (el portal y la jornada de Visualización los leen así):

| Modelo | Qué tiene |
|---|---|
| `dim_piloto` | una fila por cada valor distinto de `piloto` |
| `dim_dron` | una fila por cada valor distinto de `dron` |
| `dim_encargo` | una fila por cada valor distinto de `encargo` |
| `fact_vuelos` | un vuelo por fila: `vuelo`, `fecha`, `piloto`, `dron`, `encargo`, `minutos_vuelo`, `wh_bateria`, `importe_eur`, `con_incidencia` |
| `pregunta_1` | ¿Qué **tipo de encargo** deja menos ingreso por minuto de vuelo? Una fila por `encargo`, con `encargo` en la primera columna y `ingreso_min` (€/min), de menor a mayor |
| `pregunta_2` | ¿Qué **piloto** gasta más batería por minuto de vuelo? Una fila por `piloto`, con `piloto` en la primera columna y `wh_min` (Wh/min), de mayor a menor |
| `pregunta_3` | ¿Qué **dron** acumula más incidencias por cada 100 minutos de vuelo? Una fila por `dron`, con `dron` en la primera columna y `incidencias_100min` (incidencias por 100 min), de mayor a menor |

> 🔎 **Pista · un modelo, un fichero.** Cada modelo de la tabla es un fichero `.sql` en `dbt/models/oro/`
> con su mismo nombre (`dim_encargo.sql`, `fact_vuelos.sql`…). Dentro va **un solo `select`**, sin
> `create table`: dbt se encarga de guardarlo como Parquet en `lakehouse/oro/`. Las dimensiones y el hecho
> leen de plata con `{{ ref('stg_parte') }}`; las preguntas leen del hecho con `{{ ref('fact_vuelos') }}`.
> Así dbt sabe en qué orden construirlos.
>
> Ve de uno en uno: escribes el modelo, lo construyes solo a él y miras lo que ha salido.
>
> ```bash
> dbt build --project-dir dbt --profiles-dir dbt --select dim_encargo
> dbt show  --project-dir dbt --profiles-dir dbt --select dim_encargo
> ```
>
> Antes de pasar al siguiente, comprueba que el resultado tiene sentido: ¿cuántas filas salen?
> (`dbt show` enseña cinco; `--limit` te deja ver más, y en el bloque 1 ya viste cómo preguntar lo que quieras con `--inline`),
> ¿hay alguna repetida o vacía?, ¿las columnas se llaman exactamente como pide la tabla? Para `_oro.yml`, toma como
> plantilla `dbt/models/plata/_plata.yml`: ahí está la forma de escribir un test con `arguments:`.

En un `_oro.yml`, sus tests: en las dimensiones, `unique` y `not_null`; en el hecho, `unique` en `vuelo` y `relationships` con cada dimensión.

Escribe `paginas/2-oro.md`: tu estrella y las tres respuestas. Con la remesa nueva (un 25 % más de datos), ¿siguen saliendo las mismas que en la J3? Pull request, verde, fusionas.

## Bloque 3 · Fuentes nuevas · rama `fuentes`

1. `python herramientas/sistema_simulado.py fuentes`: llegan estos ficheros a bronce y quedan declarados en `dbt/models/plata/_fuentes.yml`.

| Fichero | Qué es | Columnas |
|---|---|---|
| `bronce/meteo/meteo_diaria.csv` | viento medio y rachas máximas (km/h) de cada día | fecha, viento_medio_kmh, rachas_kmh |
| `bronce/eventos/eventos_vuelo_2026-04-25.json` | El sistema de los drones exporta un registro con un evento al despegar y otro al aterrizar. | evento_id, vuelo_id, dron, tipo (despegue / aterrizaje), ts |

2. **El giro.** Hay vuelos que **despegan y nunca registran el aterrizaje** (batería agotada, señal perdida…). Un vuelo es un par de eventos: piensa cómo encontrar los que se quedan cojos.
3. Modelos de plata: `stg_meteo_diaria` y `stg_eventos` (el registro lo lees con `source('bronce', 'eventos')`).
4. **Test protagonista.** La normativa no permite volar con **rachas de más de 50 km/h**. Escribe un test singular que cruce el parte con la meteo y devuelva los vuelos hechos en esos días, con `severity: warn`: no es un error del dato, es un **hallazgo de negocio** que el build tiene que enseñar sin pararse. En el memo explica por qué lo has dejado en *warn*.
5. **Pregunta 4** (`dbt/models/oro/pregunta_4.sql`): ¿Qué dron tiene **más vuelos sin aterrizaje registrado** (en proporción)? ¿Coincide con el de la pregunta 3?
6. Escribe `paginas/3-fuentes.md`. Pull request, verde, fusionas.

## Bloque 4 · El memo · rama `memo`

Escribe `paginas/memo.md`: el memo para la dirección de Altura Films, con las cuatro respuestas citadas con marcas. La comprobación exige que existan `pregunta_1` a `pregunta_4`. Repasa el portal entero antes de fusionar.

---

## Lo que se entrega

- Tu repositorio en tu cuenta, con los cuatro pull requests fusionados y la última ejecución de `main` en verde.
- Tu portal publicado, con sus cuatro páginas escritas, y tu `dbt-docs`.
- La presentación oral (5 minutos): con tu portal en pantalla, el problema de calidad, tu test protagonista, las cuatro respuestas y tu recomendación.
