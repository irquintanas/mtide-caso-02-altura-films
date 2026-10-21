#!/usr/bin/env python3
"""Resumen del lakehouse en Markdown, para la página de cada ejecución de GitHub Actions.

    python bi/resumen.py >> "$GITHUB_STEP_SUMMARY"

Lee el resultado de la última ejecución de dbt (dbt/target/run_results.json) y la capa plata y oro
(lakehouse/), y escribe tres tablas: los pasos de dbt con su resultado, las filas de cada modelo y
las preguntas que ya existan. GitHub lo enseña en la página de la ejecución, sin descargar nada.
"""
import json
from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parent.parent
RESULTADOS = RAIZ / "dbt" / "target" / "run_results.json"
LAKE = RAIZ / "lakehouse"
ESTADOS = {"pass": "✅ PASS", "fail": "❌ FAIL", "error": "❌ ERROR", "skipped": "⏭️ SKIP", "success": "✅ OK",
           "warn": "⚠️ WARN"}


def tabla(cabecera, filas):
    lineas = ["| " + " | ".join(cabecera) + " |", "|" + "---|" * len(cabecera)]
    lineas += ["| " + " | ".join(str(c).replace("|", "/") for c in f) + " |" for f in filas]
    return "\n".join(lineas)


def pasos():
    print("## Pasos de dbt\n")
    if not RESULTADOS.exists():
        print("No hay resultado de dbt: `dbt build` no llegó a ejecutarse.\n")
        return
    resultados = json.loads(RESULTADOS.read_text(encoding="utf-8"))["results"]
    rango = {"fail": 0, "error": 0, "warn": 1, "skipped": 2}      # primero lo que falla
    resultados.sort(key=lambda r: (rango.get(r["status"], 3), r["unique_id"]))
    filas = []
    for r in resultados:
        fallos = f" ({r['failures']} filas)" if r.get("failures") else ""
        filas.append((r["unique_id"].split(".")[0], f"`{r['unique_id'].split('.')[2]}`",
                      ESTADOS.get(r["status"], r["status"]) + fallos))
    malos = sum(1 for r in resultados if r["status"] in ("fail", "error"))
    saltados = sum(1 for r in resultados if r["status"] == "skipped")
    print(f"**{len(resultados)} pasos:** {len(resultados) - malos - saltados} correctos, {malos} con error, {saltados} saltados.\n")
    print(tabla(["Tipo", "Nombre", "Resultado"], filas) + "\n")


def filas_por_capa():
    print("## Filas de cada modelo\n")
    filas = []
    for capa in ("plata", "oro"):
        for f in sorted((LAKE / capa).glob("*.parquet")):
            n = duckdb.sql(f"select count(*) from read_parquet('{f.as_posix()}')").fetchone()[0]
            filas.append((capa, f"`{f.stem}`", n))
    print(tabla(["Capa", "Modelo", "Filas"], filas) + "\n" if filas else "Todavía no hay modelos construidos.\n")


def preguntas():
    print("## Las preguntas\n")
    hay = False
    for k in range(1, 5):
        f = LAKE / "oro" / f"pregunta_{k}.parquet"
        if not f.exists():
            continue
        hay = True
        rel = duckdb.sql(f"select * from read_parquet('{f.as_posix()}') limit 5")
        print(f"### pregunta_{k}\n")
        print(tabla(rel.columns, [tuple("" if v is None else v for v in r) for r in rel.fetchall()]) + "\n")
    if not hay:
        print("Ninguna construida todavía (o dbt no ha llegado al oro: si un test falla, no construye lo que depende de él).\n")


if __name__ == "__main__":
    pasos()
    filas_por_capa()
    preguntas()
