# Metabase sobre el lakehouse

Conecta [Metabase](https://www.metabase.com/) (edición Open Source), en Docker, al oro y la plata de este repositorio,
sin copiar los datos y sin bloquear `dbt build`.

## Cómo funciona

Metabase no lee Parquet directamente. La conexión es una base **DuckDB en memoria** (`:memory:`) que, cada vez que
Metabase abre una conexión, ejecuta un **Init SQL** que crea una vista por cada fichero de `lakehouse/oro` y
`lakehouse/plata`, en los esquemas `oro` y `plata`. Ese Init SQL lo escribe `init_sql.py`.

No se conecta Metabase al `.duckdb` de dbt: mientras otro proceso lo tiene abierto (aunque sea solo para leer),
`dbt build` falla con «Could not set lock on file».

## Pasos

1. Ten este repositorio dentro de una carpeta de trabajo con tus demás repositorios (por ejemplo, `mtide/`).
2. Construye el lakehouse: `dbt build --project-dir dbt --profiles-dir dbt`.
3. Genera el Init SQL: `python metabase/init_sql.py`. Escribe `metabase/init.sql`, con las rutas tal y como las ve el
   contenedor (`/datos/<este-repositorio>/lakehouse`).
4. Arranca Metabase en Docker **desde la carpeta de trabajo** (la que contiene los repositorios), con la imagen que
   trae el driver de DuckDB (la oficial `metabase/metabase`, basada en Alpine, no sirve con este driver):

   ```bash
   docker run -d --name metabase -p 3000:3000 \
     -v "$PWD:/datos" \
     -v "$PWD/metabase-data:/metabase-data" -e MB_DB_FILE=/metabase-data/metabase.db \
     ghcr.io/motherduckdb/metabase-duckdb:latest
   ```

   En PowerShell, en una sola línea y con `${PWD}`. Después, `docker stop metabase` y `docker start metabase`; lo que
   crees en Metabase se guarda en `metabase-data/`.

5. En http://localhost:3000: menú de configuración (arriba a la derecha) → **Admin** → **Bases de datos** →
   **Añadir base de datos** → tipo **DuckDB**, *Database file* `:memory:` y el contenido de `metabase/init.sql` en
   **Init SQL**. Guardar.

Si añades modelos a dbt, vuelve a generar el Init SQL, pégalo en la conexión y pulsa **Sincronizar esquema de la base de
datos**. `metabase/init.sql` no se versiona: depende de cómo hayas montado la carpeta.
