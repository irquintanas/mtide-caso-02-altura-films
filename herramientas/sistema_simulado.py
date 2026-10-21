#!/usr/bin/env python3
"""Sistema simulado de la empresa: manda los datos nuevos a la capa bronce cuando el encargo lo pide.

    python herramientas/sistema_simulado.py remesa    # bloque 1: una entrega nueva del parte diario
    python herramientas/sistema_simulado.py fuentes   # bloque 3: una fuente nueva y el registro de eventos del día

Hace lo que haría el sistema real de la empresa: deja ficheros en lakehouse/bronce/, cada entrega
del parte en su carpeta fecha_carga=AAAA-MM-DD. Después declara en dbt todo lo que hay en bronce
(dbt/models/plata/_fuentes.yml), para que puedas leerlo con source('bronce', '<nombre>').

Lo que llega se sube a GitHub como cualquier otro cambio: en tu rama y con tu pull request.
"""
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ENVIOS = Path(__file__).resolve().parent / "envios"
BRONCE = RAIZ / "lakehouse" / "bronce"
FUENTES_YML = RAIZ / "dbt" / "models" / "plata" / "_fuentes.yml"


def declarar_fuentes():
    """Reescribe _fuentes.yml con todo lo que hay en bronce: el parte, cada CSV de referencia y el registro de eventos."""
    tablas = ['''      - name: parte
        description: "El parte diario: una carpeta fecha_carga=AAAA-MM-DD por entrega"
        meta:
          external_location: "read_csv('lakehouse/bronce/parte/fecha_carga=*/*.csv', all_varchar = true, union_by_name = true, hive_partitioning = true, filename = true)"''']
    for csv in sorted(BRONCE.glob("*/*.csv")):
        if csv.parent.name in ("parte", "eventos"):
            continue
        ruta = csv.relative_to(BRONCE).as_posix()
        tablas.append(f'''      - name: {csv.stem}
        description: "Fuente de referencia: {ruta}"
        meta:
          external_location: "read_csv('lakehouse/bronce/{ruta}', header = true)"''')
    if list((BRONCE / "eventos").glob("*.json")):
        tablas.append('''      - name: eventos
        description: "Registro de eventos del día: JSON, una línea por evento"
        meta:
          external_location: "read_json('lakehouse/bronce/eventos/*.json', format = 'newline_delimited')"''')
    FUENTES_YML.write_text(
        "# Lo que hay en bronce, declarado para dbt. Lo reescribe herramientas/sistema_simulado.py cada vez que llegan datos.\n"
        "version: 2\nsources:\n  - name: bronce\n"
        '    description: "Lo que llega, tal cual. Nunca se modifica: los arreglos van en plata."\n'
        "    tables:\n" + "\n".join(tablas) + "\n", encoding="utf-8")


def main():
    envios = sorted(p.name for p in ENVIOS.iterdir() if p.is_dir()) if ENVIOS.exists() else []
    if len(sys.argv) != 2 or sys.argv[1] not in envios:
        sys.exit("Uso: python herramientas/sistema_simulado.py " + " | ".join(envios))
    envio = ENVIOS / sys.argv[1]
    ficheros = sorted(p for p in envio.rglob("*") if p.is_file())
    nuevos = []
    for origen in ficheros:
        destino = BRONCE / origen.relative_to(envio)
        if destino.exists():
            continue
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origen, destino)
        nuevos.append(destino)
    declarar_fuentes()
    if not nuevos:
        print(f"ℹ️  El envío «{sys.argv[1]}» ya había llegado: no hay nada nuevo en bronce.")
        return
    print(f"📦 {'Ha llegado 1 fichero' if len(nuevos) == 1 else f'Han llegado {len(nuevos)} ficheros'} a bronce:")
    for p in nuevos:
        print(f"   {p.relative_to(RAIZ).as_posix()}  ({p.stat().st_size / 1024:,.0f} KB)".replace(",", "."))
    print("   dbt/models/plata/_fuentes.yml  (actualizado: todo lo que hay en bronce, declarado para dbt)")
    print("\nSiguiente paso: dbt build --project-dir dbt --profiles-dir dbt   (y lee tu ENCARGO.md)")


if __name__ == "__main__":
    main()
