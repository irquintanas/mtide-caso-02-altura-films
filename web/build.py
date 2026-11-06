#!/usr/bin/env python3
"""Portal de datos del caso: genera la web en _site/ con tus páginas y las cifras del lakehouse.

    python web/build.py           # comprueba y genera _site/  (abre _site/index.html en el navegador)
    python web/build.py --check   # solo comprueba: es lo que hace GitHub con cada pull request

Las páginas las escribes tú en paginas/ (Markdown). Las cifras no se escriben a mano: una marca como
{{ pregunta_1.ingreso_min[0] }} se sustituye por el valor de la columna ingreso_min, fila 0, del modelo
pregunta_1 (se busca en lakehouse/oro/ y, si no está, en lakehouse/plata/). {{ stg_parte.filas }} da el
número de filas de un modelo.

Una página que todavía empieza por la línea <!-- pendiente … --> sale en el portal como «pendiente» y no se
comprueba. En cuanto borras esa línea, la comprobación exige que no quede ninguna línea del guion («> ✏️ …»)
y que todas sus marcas tengan valor.

Bloque 5 (la historia): paginas/historia.md pasa a ser la portada en cuanto deja de estar pendiente, y las
páginas del ejercicio del lakehouse quedan agrupadas y plegadas. En cualquier página puedes usar dos bloques:
```grafico (cinco tipos: barras, linea, histograma, calor y eje; cómo se escribe cada uno, en web/graficos.py y en
el README) y ```cifras (líneas «cifra | qué es»). Los gráficos leen los datos del lakehouse: ninguna cifra se
escribe a mano.
"""
import html
from decimal import Decimal
import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent))
import graficos  # noqa: E402  (los gráficos del portal, en web/graficos.py)

RAIZ = Path(__file__).resolve().parent.parent
CASO = json.loads((RAIZ / "web" / "caso.json").read_text(encoding="utf-8"))
PAGINAS = RAIZ / "paginas"
LAKE = RAIZ / "lakehouse"
TARGET = RAIZ / "dbt" / "target"
SITE = RAIZ / "_site"
PENDIENTE = "<!-- pendiente"
GUION = "> ✏️"
BITACORA = [("1-remesa", "1 · La remesa"), ("2-oro", "2 · El oro"), ("3-fuentes", "3 · Fuentes nuevas"),
            ("memo", "Memo para la dirección")]
HISTORIA = [("historia", "La historia"), ("historia-pasos", "Cómo se construyó la historia")]
LAKEHOUSE = [("montaje", "Cómo está montado")] + BITACORA + [("datos", "Datos abiertos")]
MARCA = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)(?:\[(\d+)\])?\s*\}\}")
e = html.escape


# ─────────────────────────── datos del lakehouse ───────────────────────────
def parquet(modelo):
    for capa in ("oro", "plata"):
        ruta = LAKE / capa / f"{modelo}.parquet"
        if ruta.exists():
            return ruta
    return None


def leer(modelo, limite=None):
    """Columnas y filas de un modelo, o None si no existe."""
    ruta = parquet(modelo)
    if ruta is None:
        return None
    rel = duckdb.sql(f"select * from read_parquet('{ruta.as_posix()}')")
    filas = (rel.limit(limite) if limite else rel).fetchall()
    # un modelo vacío se escribe con una fila de nulos: se trata como vacío
    if len(filas) == 1 and all(v is None for v in filas[0]):
        filas = []
    return rel.columns, filas


def num_filas(modelo):
    datos = leer(modelo)
    return None if datos is None else len(datos[1])


def formato(v):
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "sí" if v else "no"
    if isinstance(v, Decimal):   # las columnas DECIMAL de DuckDB llegan así: se formatean como cualquier número
        v = int(v) if v == v.to_integral_value() else float(v)
    if isinstance(v, int):
        return f"{v:,}".replace(",", ".")
    if isinstance(v, float):
        if v.is_integer() and abs(v) < 1e15:
            return f"{int(v):,}".replace(",", ".")
        decimales = 2 if abs(v) >= 1 else 3
        texto = f"{v:,.{decimales}f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return texto.rstrip("0").rstrip(",") if "," in texto else texto
    return str(v)


def valor_marca(m):
    """Valor de una marca {{ modelo.columna[i] }} o {{ modelo.filas }}; si no se puede, (None, motivo)."""
    modelo, columna, i = m.group(1), m.group(2), int(m.group(3) or 0)
    datos = leer(modelo)
    if datos is None:
        return None, f"el modelo {modelo} no existe (¿has ejecutado dbt build?)"
    if columna == "filas" and m.group(3) is None:
        return formato(len(datos[1])), None
    cols, filas = datos
    if columna not in cols:
        return None, f"{modelo} no tiene la columna {columna} (tiene: {', '.join(cols)})"
    if i >= len(filas):
        return None, f"{modelo} solo tiene {len(filas)} filas: no hay fila {i}"
    return formato(filas[i][cols.index(columna)]), None


# ─────────────────────────── bloques ```grafico y ```cifras ───────────────────────────
def bloques(texto, tipo):
    """(línea de inicio, líneas del cuerpo) de cada bloque ```tipo del texto."""
    lineas, out, i = texto.splitlines(), [], 0
    while i < len(lineas):
        if lineas[i].strip() == f"```{tipo}":
            j = i + 1
            while j < len(lineas) and not lineas[j].startswith("```"):
                j += 1
            out.append((i + 1, lineas[i + 1:j]))
            i = j
        i += 1
    return out


def preparar_grafico(cuerpo):
    return graficos.preparar(cuerpo, leer, formato)


def grafico_html(cuerpo):
    return graficos.dibujar(cuerpo, leer, formato)[0]


def cifras_html(cuerpo):
    tarjetas = []
    for l in cuerpo:
        if "|" in l:
            valor, _, etiqueta = l.partition("|")
            tarjetas.append(f'<div class="cifra"><span class="v">{e(valor.strip())}</span><span class="t">{e(etiqueta.strip())}</span></div>')
    return f'<div class="cifras">{"".join(tarjetas)}</div>'


# ─────────────────────────── páginas del alumno ───────────────────────────
def leer_pagina(nombre):
    ruta = PAGINAS / f"{nombre}.md"
    texto = ruta.read_text(encoding="utf-8") if ruta.exists() else ""
    return texto, (not texto.strip()) or texto.lstrip().startswith(PENDIENTE)


TIPOS_USADOS = set()


def comprobar():
    errores = []
    for nombre, titulo in BITACORA + HISTORIA:
        texto, pendiente = leer_pagina(nombre)
        if pendiente:
            continue
        for n, linea in enumerate(texto.splitlines(), 1):
            if linea.strip().startswith(GUION):
                errores.append(f"paginas/{nombre}.md, línea {n}: queda una línea del guion sin sustituir («{linea.strip()[:60]}»)")
        for m in MARCA.finditer(texto):
            _, motivo = valor_marca(m)
            if motivo:
                linea = texto[:m.start()].count("\n") + 1
                errores.append(f"paginas/{nombre}.md, línea {linea}: la marca {m.group(0)} no tiene valor: {motivo}")
        for inicio_bloque, cuerpo in bloques(texto, "grafico"):
            g, fallos = preparar_grafico([MARCA.sub(lambda m: valor_marca(m)[0] or "", l) for l in cuerpo])
            if g and nombre in dict(HISTORIA):
                TIPOS_USADOS.add(g["tipo"])
            errores += [f"paginas/{nombre}.md, gráfico de la línea {inicio_bloque}: {f}" for f in fallos]
        for inicio_bloque, cuerpo in bloques(texto, "cifras"):
            if not any("|" in l for l in cuerpo):
                errores.append(f"paginas/{nombre}.md, cifras de la línea {inicio_bloque}: cada línea es «cifra | qué es»")
        if nombre == "historia":
            primera = next((l for l in texto.splitlines() if l.strip()), "")
            if not primera.startswith("# "):
                errores.append("paginas/historia.md: la primera línea tiene que ser el titular («# …»)")
            elif not MARCA.search(primera):
                errores.append("paginas/historia.md: el titular afirma con una cifra del lakehouse: pon al menos una marca {{ … }} en él")
        if nombre == "memo":
            for k in range(1, 5):
                if parquet(f"pregunta_{k}") is None:
                    errores.append(f"paginas/memo.md: el memo necesita las cuatro preguntas y falta el modelo pregunta_{k}")
    return errores


def md_a_html(texto):
    """Markdown sencillo: títulos, párrafos, listas, tablas, citas, **negrita**, *cursiva*, `código` y [enlaces](url)."""
    def enlinea(t):
        partes = re.split(r"(`[^`]+`)", t)
        out = []
        for p in partes:
            if p.startswith("`") and p.endswith("`") and len(p) > 1:
                out.append(f"<code>{e(p[1:-1])}</code>")
                continue
            p = e(p)
            p = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", p)
            p = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", p)
            p = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', p)
            out.append(p)
        return "".join(out)

    out, lineas, i = [], texto.splitlines(), 0
    while i < len(lineas):
        l = lineas[i]
        if not l.strip():
            i += 1
            continue
        if l.strip() in ("```grafico", "```cifras"):
            j = i + 1
            while j < len(lineas) and not lineas[j].startswith("```"):
                j += 1
            cuerpo = lineas[i + 1:j]
            out.append(grafico_html(cuerpo) if l.strip() == "```grafico" else cifras_html(cuerpo))
            i = j + 1
            continue
        if l.startswith("```"):
            j = i + 1
            while j < len(lineas) and not lineas[j].startswith("```"):
                j += 1
            out.append("<pre><code>" + e("\n".join(lineas[i + 1:j])) + "</code></pre>")
            i = j + 1
            continue
        if l.startswith("#"):
            nivel = min(len(l) - len(l.lstrip("#")), 3)
            out.append(f"<h{nivel}>{enlinea(l.lstrip('#').strip())}</h{nivel}>")
            i += 1
            continue
        bloque = []
        while i < len(lineas) and lineas[i].strip() and not lineas[i].startswith(("#", "```")):
            bloque.append(lineas[i])
            i += 1
        if all(b.lstrip().startswith("|") for b in bloque) and len(bloque) >= 2:
            celdas = [[c.strip() for c in b.strip().strip("|").split("|")] for b in bloque]
            cuerpo = [c for c in celdas[1:] if not all(re.fullmatch(r":?-{2,}:?", x) for x in c)]
            out.append("<table><tr>" + "".join(f"<th>{enlinea(c)}</th>" for c in celdas[0]) + "</tr>" +
                       "".join("<tr>" + "".join(f"<td>{enlinea(c)}</td>" for c in f) + "</tr>" for f in cuerpo) + "</table>")
        elif all(re.match(r"\s*[-*] ", b) for b in bloque):
            items = [enlinea(re.sub(r"^\s*[-*] ", "", b)) for b in bloque]
            out.append("<ul>" + "".join("<li>" + x + "</li>" for x in items) + "</ul>")
        elif all(re.match(r"\s*\d+\. ", b) for b in bloque):
            items = [enlinea(re.sub(r"^\s*\d+\. ", "", b)) for b in bloque]
            out.append("<ol>" + "".join("<li>" + x + "</li>" for x in items) + "</ol>")
        elif all(b.startswith(">") for b in bloque):
            out.append("<blockquote>" + enlinea(" ".join(b.lstrip(">").strip() for b in bloque)) + "</blockquote>")
        else:
            out.append(f"<p>{enlinea(' '.join(b.strip() for b in bloque))}</p>")
    return "\n".join(out)


def sustituir_marcas(texto):
    def cambio(m):
        valor, motivo = valor_marca(m)
        return valor if motivo is None else f"⚠️ {m.group(0)}"
    return MARCA.sub(cambio, texto)


# ─────────────────────────── piezas de la web ───────────────────────────
def tabla_modelo(modelo, limite=8):
    datos = leer(modelo)
    if datos is None:
        return None
    cols, filas = datos
    if not filas:
        return '<p class="vacio">El modelo existe pero está vacío.</p>'
    cab = "".join(f"<th>{e(c)}</th>" for c in cols)
    cuerpo = "".join("<tr>" + "".join(f"<td>{e(formato(v))}</td>" for v in f) + "</tr>" for f in filas[:limite])
    resto = f'<p class="nota">… y {len(filas) - limite} filas más.</p>' if len(filas) > limite else ""
    return f'<div class="scroll"><table><tr>{cab}</tr>{cuerpo}</table></div>{resto}'


def base_publica():
    """URL de la web publicada (en GitHub Actions) o None (en tu portátil)."""
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        return None
    dueno, nombre = repo.split("/")
    return f"https://{dueno.lower()}.github.io/{nombre}/"


def resultados_dbt():
    ruta = TARGET / "run_results.json"
    if not ruta.exists():
        return {}
    return {r["unique_id"]: r for r in json.loads(ruta.read_text(encoding="utf-8"))["results"]}


def manifiesto():
    ruta = TARGET / "manifest.json"
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else None


ESTADOS = {"pass": ("ok", "PASS"), "success": ("ok", "OK"), "fail": ("mal", "FAIL"), "error": ("mal", "ERROR"),
           "skipped": ("salta", "SKIP"), "warn": ("aviso", "WARN")}


def estado(r):
    if r is None:
        return '<span class="estado">—</span>'
    clase, txt = ESTADOS.get(r["status"], ("", r["status"]))
    fallos = f" · {r['failures']} filas" if r.get("failures") else ""
    return f'<span class="estado {clase}">{txt}{fallos}</span>'


def enlace(nombre, titulo, actual):
    if nombre in dict(BITACORA + HISTORIA) and leer_pagina(nombre)[1]:
        return f'<a href="{nombre}.html" class="pendiente{" activa" if nombre == actual else ""}">{e(titulo)}</a>'
    clase = ' class="activa"' if nombre == actual else ""
    return f'<a href="{nombre}.html"{clase}>{e(titulo)}</a>'


def menu(actual):
    historia_lista = not leer_pagina("historia")[1]
    enlaces = [enlace("index", "Inicio · la historia" if historia_lista else "Inicio", actual)]
    if not historia_lista:
        enlaces.append(enlace("historia", "La historia", actual))
    enlaces.append(enlace("historia-pasos", "Cómo se construyó la historia", actual))
    dentro = actual in dict(LAKEHOUSE)
    grupo = "".join(enlace(n, t, actual) for n, t in LAKEHOUSE)
    activa = ' class="activa"' if dentro else ""
    return (f'<nav>{"".join(enlaces)}<span class="sep"></span><details class="grupo"{" open" if dentro else ""}>'
            f'<summary{activa}>Ejercicio lakehouse <span class="cuenta">{len(LAKEHOUSE)}</span></summary>'
            f'<div class="desplegable">{grupo}</div></details></nav>')


def pagina(nombre, titulo, cuerpo):
    ahora = datetime.now().strftime("%d/%m/%Y %H:%M")
    commit = os.environ.get("GITHUB_SHA", "")[:7]
    repo = os.environ.get("GITHUB_REPOSITORY")
    pie_repo = f' · <a href="https://github.com/{e(repo)}">repositorio</a>' if repo else " · vista previa en tu portátil"
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(titulo)} · {e(CASO['empresa'])}</title><link rel="stylesheet" href="estilo.css"></head>
<body>
<header><a href="index.html" class="marca">{e(CASO['empresa'])} <b>Datos</b></a>
<span class="sub">{e(CASO['subtitulo'])}</span></header>
{menu(nombre)}
<main>{cuerpo}</main>
<footer>MTIDE 3.1 · caso {CASO['num']:02d} · empresa ficticia{pie_repo}{' · commit <code>' + e(commit) + '</code>' if commit else ''} · generado el {ahora}</footer>
</body></html>"""


def lakehouse_resumen():
    """Las cuatro preguntas y la bitácora del ejercicio del lakehouse."""
    tarjetas = []
    for k, q in enumerate(CASO["preguntas"], 1):
        datos = leer(f"pregunta_{k}", 1)
        if datos and datos[1]:
            cols, filas = datos
            resp = " · ".join(f"<b>{e(formato(v))}</b>" if j == 0 else e(formato(v)) for j, v in enumerate(filas[0]))
            cuerpo = f'<p class="resp">{resp}</p><p class="nota">{e(" · ".join(cols))}</p>'
            clase = "hecha"
        else:
            cuerpo, clase = '<p class="resp vacio">Pendiente: el modelo <code>pregunta_' + str(k) + '</code> aún no existe.</p>', "pendiente"
        tarjetas.append(f'<div class="tarjeta {clase}"><span class="num">Pregunta {k}</span><p class="q">{md_a_html(q)[3:-4]}</p>{cuerpo}</div>')
    respondidas = sum(1 for t in tarjetas if "tarjeta hecha" in t)
    return tarjetas, respondidas


def lista_estados(paginas):
    return '<ul class="lista">' + "".join(
        f'<li><a href="{n}.html">{e(t)}</a> <span class="estado {"salta" if leer_pagina(n)[1] else "ok"}">'
        f'{"pendiente" if leer_pagina(n)[1] else "escrita"}</span></li>' for n, t in paginas) + "</ul>"


def inicio():
    tarjetas, respondidas = lakehouse_resumen()
    texto, pendiente = leer_pagina("historia")
    if not pendiente:
        escritas = sum(1 for n, _ in BITACORA if not leer_pagina(n)[1])
        return f"""<article class="historia">{md_a_html(sustituir_marcas(texto))}</article>
<details class="plegable"><summary><span>Ejercicio lakehouse: las cuatro preguntas y la bitácora</span>
<span class="nota">{respondidas} de 4 preguntas con respuesta · {escritas} de {len(BITACORA)} páginas escritas</span></summary>
<div class="dentro"><div class="rejilla">{''.join(tarjetas)}</div>{lista_estados(BITACORA)}</div></details>"""
    return f"""<section class="hero"><p class="eyebrow">Portal de datos · caso {CASO['num']:02d}</p>
<h1>{e(CASO['empresa'])}</h1><p>{md_a_html(CASO['contexto'])[3:-4]}</p></section>
<section><h2>Las cuatro preguntas de la dirección</h2><div class="rejilla">{''.join(tarjetas)}</div>
<p class="nota">Cada respuesta es la primera fila de su modelo de oro, leída del lakehouse al generar esta web.</p></section>
<section><h2>Bitácora del equipo de datos</h2>{lista_estados(BITACORA)}</section>
<section><h2>Bloque 5 · La historia</h2>{lista_estados(HISTORIA)}
<p class="nota">Cuando escribas <code>paginas/historia.md</code>, tu historia pasará a ser la portada de este portal.</p></section>"""


def montaje():
    res, man = resultados_dbt(), manifiesto()
    # bronce
    filas_b = []
    for f in sorted(p for p in (LAKE / "bronce").rglob("*") if p.is_file() and not p.name.startswith(".")):
        filas_b.append(f"<tr><td><code>{e(f.relative_to(LAKE).as_posix())}</code></td><td>{'menos de 1' if f.stat().st_size < 1024 else formato(round(f.stat().st_size / 1024))} KB</td></tr>")
    bronce = "<table><tr><th>Fichero</th><th>Tamaño</th></tr>" + "".join(filas_b) + "</table>"
    # modelos y tests
    if man is None:
        modelos = tests = '<p class="vacio">Todavía no hay resultado de dbt: ejecuta <code>dbt build --project-dir dbt --profiles-dir dbt</code>.</p>'
    else:
        filas_m, filas_t = [], []
        for uid, n in sorted(man["nodes"].items(), key=lambda x: (not x[1]["name"].startswith("stg_"), x[1]["name"])):
            if n["resource_type"] == "model":
                capa = "plata" if n["name"].startswith("stg_") else "oro"
                nf = num_filas(n["name"])
                deps = ", ".join(d.split(".")[-1] for d in n["depends_on"]["nodes"])
                filas_m.append(f"<tr><td><span class='capa {capa}'>{capa}</span></td><td><code>{e(n['name'])}</code></td>"
                               f"<td>{'—' if nf is None else formato(nf)}</td><td>{e(deps)}</td><td>{estado(res.get(uid))}</td></tr>")
            elif n["resource_type"] == "test":
                tipo = "singular" if "singular" in uid or n.get("test_metadata") is None else "genérico"
                filas_t.append(f"<tr><td><code>{e(n['name'][:70])}</code></td><td>{tipo}</td><td>{estado(res.get(uid))}</td></tr>")
        modelos = ("<table><tr><th>Capa</th><th>Modelo</th><th>Filas</th><th>Lee de</th><th>Estado</th></tr>" + "".join(filas_m) + "</table>")
        tests = ("<table><tr><th>Test</th><th>Tipo</th><th>Resultado</th></tr>" + "".join(filas_t) + "</table>")
    docs = ('<p>El linaje completo (qué modelo lee de cuál) y la ficha de cada modelo y test están en la '
            '<a href="dbt-docs/index.html">documentación de dbt</a>.</p>' if base_publica() else
            '<p class="nota">En la web publicada, aquí hay un enlace a la documentación de dbt con el linaje. '
            'En tu portátil: <code>dbt docs generate --project-dir dbt --profiles-dir dbt</code> y '
            '<code>dbt docs serve --project-dir dbt --profiles-dir dbt</code>.</p>')
    return f"""<h1>Cómo está montado</h1>
<p class="intro">El lakehouse de {e(CASO['empresa'])}: lo que llega se guarda tal cual en <b>bronce</b>, dbt lo limpia en
<b>plata</b> y lo resume en <b>oro</b>, y los tests paran cualquier dato malo antes de que llegue a las conclusiones.</p>
<section><h2>Bronce · lo que ha llegado</h2>{bronce}</section>
<section><h2>Plata y oro · los modelos de dbt</h2>{modelos}{docs}</section>
<section><h2>Los tests</h2>{tests}</section>"""


def bitacora(nombre, titulo):
    texto, pendiente = leer_pagina(nombre)
    if pendiente:
        return (f'<h1>{e(titulo)}</h1><p class="vacio">Pendiente. Esta página se escribe en <code>paginas/{nombre}.md</code> '
                'y se publica al fusionar el bloque correspondiente.</p>')
    return md_a_html(sustituir_marcas(texto))


def datos():
    base = base_publica()
    filas = []
    for capa in ("plata", "oro"):
        for f in sorted((LAKE / capa).glob("*.parquet")):
            ruta = f"lakehouse/{capa}/{f.name}"
            url = (base + ruta) if base else ruta
            nf = num_filas(f.stem)
            filas.append(f"<tr><td><span class='capa {capa}'>{capa}</span></td><td><a href='{e(ruta)}'>{e(f.name)}</a></td>"
                         f"<td>{'—' if nf is None else formato(nf)}</td><td><code>{e(url)}</code></td></tr>")
    ejemplo = (base or "") + "lakehouse/oro/pregunta_1.parquet"
    tabla = ("<table><tr><th>Capa</th><th>Fichero</th><th>Filas</th><th>Dirección</th></tr>" + "".join(filas) + "</table>"
             if filas else '<p class="vacio">Todavía no hay modelos construidos.</p>')
    return f"""<h1>Datos abiertos</h1>
<p class="intro">Plata y oro, publicados como ficheros Parquet. Cualquiera puede consultarlos sin descargar nada: DuckDB los lee por su dirección.</p>
<section>{tabla}</section>
<section><h2>Consultarlos con DuckDB</h2><pre><code>import duckdb
duckdb.sql("select * from '{e(ejemplo)}'").show()</code></pre></section>
<section><h2>Las respuestas, completas</h2>{''.join(f'<h3>pregunta_{k}</h3>' + (tabla_modelo(f'pregunta_{k}') or '<p class="vacio">Pendiente.</p>') for k in range(1, 5))}</section>"""


def generar():
    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir()
    shutil.copy(RAIZ / "web" / "estilo.css", SITE / "estilo.css")
    piezas = [("index", "Inicio", inicio()), ("montaje", "Cómo está montado", montaje())]
    piezas += [(n, t, bitacora(n, t)) for n, t in BITACORA + HISTORIA]
    piezas.append(("datos", "Datos abiertos", datos()))
    for nombre, titulo, cuerpo in piezas:
        (SITE / f"{nombre}.html").write_text(pagina(nombre, titulo, cuerpo), encoding="utf-8")
    print(f"🌐 Portal generado en _site/ ({len(piezas)} páginas). Ábrelo: _site/index.html")


if __name__ == "__main__":
    errores = comprobar()
    for err in errores:
        print("❌", err)
    if errores:
        sys.exit(f"\n{len(errores)} problemas en las páginas: corrígelos antes de subir.")
    todas = BITACORA + HISTORIA
    hechas = sum(1 for n, _ in todas if not leer_pagina(n)[1])
    print(f"✅ Páginas comprobadas: {hechas} de {len(todas)} escritas, sin líneas del guion ni marcas sin valor.")
    if not leer_pagina("historia")[1] or not leer_pagina("historia-pasos")[1]:
        tipos = ", ".join(sorted(TIPOS_USADOS)) or "ninguno"
        aviso = "" if len(TIPOS_USADOS) >= 3 else " · la J7 pide al menos tres tipos distintos entre las dos páginas"
        print(f"📊 Tipos de gráfico en tu historia: {tipos}{aviso}")
    if "--check" not in sys.argv:
        generar()
