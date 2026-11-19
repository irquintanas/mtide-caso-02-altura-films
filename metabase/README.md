# Metabase sobre el lakehouse

Conecta [Metabase](https://www.metabase.com/) (edición Open Source) al oro y la plata de este repositorio, sin copiar los
datos y sin bloquear `dbt build`. Probado con Metabase 0.65 y el driver de DuckDB 1.4.1 de MotherDuck.

## Cómo funciona

Metabase no lee Parquet directamente. La conexión es una base **DuckDB en memoria** (`:memory:`) que, cada vez que
Metabase abre una conexión, ejecuta un **Init SQL** que crea una vista por cada fichero de `lakehouse/oro` y
`lakehouse/plata`, en los esquemas `oro` y `plata`. Ese Init SQL lo escribe `init_sql.py`.

No se conecta Metabase al `.duckdb` de dbt: mientras otro proceso lo tiene abierto (aunque sea solo para leer),
`dbt build` falla con «Could not set lock on file».

## Pasos

1. Construye el lakehouse: `dbt build --project-dir dbt --profiles-dir dbt`.
2. Genera el Init SQL:

   ```bash
   python metabase/init_sql.py                          # Metabase en Docker, con lakehouse/ montado en /datos
   python metabase/init_sql.py --ruta "$PWD/lakehouse"  # Metabase con Java (metabase.jar) o la app de Mac
   ```

3. Arranca Metabase con el driver de DuckDB:

   - **Java 21**: `metabase.jar` (descargas de metabase.com) y `plugins/duckdb.metabase-driver.jar` (última *release* de
     `motherduckdb/metabase_duckdb_driver` en GitHub), y `java -jar metabase.jar`.
   - **Docker**: la imagen `ghcr.io/motherduckdb/metabase-duckdb` (la oficial, basada en Alpine, no sirve con este driver):

     ```bash
     docker run -d --name metabase -p 3000:3000 \
       -v "$PWD/lakehouse:/datos" \
       -v "$HOME/metabase-data:/metabase-data" -e MB_DB_FILE=/metabase-data/metabase.db \
       ghcr.io/motherduckdb/metabase-duckdb:latest
     ```

4. En http://localhost:3000: menú de configuración (arriba a la derecha) → **Admin** → **Bases de datos** →
   **Añadir base de datos** → tipo **DuckDB**, *Database file* `:memory:` y el contenido de `metabase/init.sql` en
   **Init SQL**. Guardar.

Si añades modelos a dbt, vuelve a generar el Init SQL, pégalo en la conexión y pulsa **Sincronizar esquema de la base de
datos**. `metabase/init.sql` no se versiona: depende de dónde tengas el repositorio.
