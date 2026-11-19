#!/usr/bin/env python3
"""Genera el «Init SQL» para conectar Metabase (en Docker) al lakehouse con DuckDB.

    python metabase/init_sql.py

Metabase corre en Docker con la carpeta que contiene tus repositorios montada en /datos
(-v "$PWD:/datos" al arrancar el contenedor desde esa carpeta). Por eso el lakehouse de este repositorio está, para
Metabase, en /datos/<nombre-de-este-repositorio>/lakehouse: el script lo calcula solo. Si lo montaste de otra forma,
indica la ruta tal y como la ve el contenedor con --ruta.

Escribe metabase/init.sql y lo muestra por pantalla: es lo que se pega en el campo «Init SQL» de la conexión DuckDB.
Crea una vista por cada fichero Parquet de lakehouse/oro y lakehouse/plata, en los esquemas «oro» y «plata»,
dentro de una base en memoria (:memory:). Así Metabase ve las tablas del lakehouse sin abrir el fichero .duckdb de dbt,
que quedaría bloqueado y no dejaría ejecutar dbt build mientras Metabase está en marcha.

Si añades modelos nuevos a dbt, vuelve a ejecutarlo, pega el resultado y pulsa «Sincronizar» en Metabase.
"""
import argparse
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
LAKE = RAIZ / "lakehouse"
CAPAS = ("oro", "plata")


def init_sql(ruta):
    lineas = [
        "-- Init SQL de Metabase (generado por metabase/init_sql.py): una vista por modelo del lakehouse",
        f"SET file_search_path = '{ruta}';",
    ]
    for capa in CAPAS:
        ficheros = sorted((LAKE / capa).glob("*.parquet"))
        if not ficheros:
            continue
        lineas.append(f"CREATE SCHEMA IF NOT EXISTS {capa};")
        for f in ficheros:
            lineas.append(f"CREATE OR REPLACE VIEW {capa}.{f.stem} AS SELECT * FROM read_parquet('{capa}/{f.name}');")
    return "\n".join(lineas) + "\n"


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    por_defecto = f"/datos/{RAIZ.name}/lakehouse"
    p.add_argument("--ruta", default=por_defecto,
                   help=f"carpeta del lakehouse tal y como la ve el contenedor de Metabase (por defecto {por_defecto})")
    args = p.parse_args()
    if not any((LAKE / c).glob("*.parquet") for c in CAPAS):
        raise SystemExit("No hay Parquet en lakehouse/oro ni en lakehouse/plata: ejecuta antes "
                         "dbt build --project-dir dbt --profiles-dir dbt")
    sql = init_sql(args.ruta.rstrip("/\\").replace("\\", "/"))
    (RAIZ / "metabase" / "init.sql").write_text(sql, encoding="utf-8")
    print(sql)
    vistas = sql.count("CREATE OR REPLACE VIEW")
    print(f"-- {vistas} vistas. Copiado en metabase/init.sql: pégalo en «Init SQL» de la conexión DuckDB.")


if __name__ == "__main__":
    main()
