"""Gráficos del portal: el bloque ```grafico de las páginas, dibujado con los datos del lakehouse.

Cinco tipos, uno por mensaje. Todos leen un modelo (oro o plata), escriben la fuente al pie y llevan sus reglas de
honestidad dentro: las barras y la línea empiezan en cero, la referencia va siempre etiquetada, la media y la
mediana se calculan (no se escriben), la escala del mapa de calor va al pie y el eje truncado nunca sale solo.

    tipo: barras       (por defecto)  barras: categoría → columna [, columna2]   destacar · referencia · solo · orden · leyenda
    tipo: linea        x: columna    y: columna [, columna2]                     destacar · referencia · leyenda
    tipo: histograma   columna: columna_numérica                                 tramo · escala: log · marcas
    tipo: calor        filas: columna   columnas: columna   valor: columna       normalizar: fila · destacar · orden
    tipo: eje          barras: categoría → columna   corte: número                solo · orden
"""
import html
import math
import re
from datetime import date, datetime

e = html.escape
TIPOS = ("barras", "linea", "histograma", "calor", "eje")
CLAVE = re.compile(r"^\s*([a-zñ_]+)\s*:\s*(.*)$", re.I)


# ─────────────────────────── utilidades ───────────────────────────
def lista(t):
    return [x.strip() for x in str(t).split(",") if x.strip()]


def numero(v):
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return None if isinstance(v, float) and math.isnan(v) else float(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def numero_texto(t):
    """'4,1' o '1.234,5' (español) o '4.1': número o None."""
    t = str(t).strip()
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    return numero(t)


def etiqueta_x(v, formato):
    if isinstance(v, datetime):
        return f"{v.day}/{v.month} {v:%H:%M}"
    if isinstance(v, date):
        return f"{v.day}/{v.month}"
    return formato(v)


def mezcla(t):
    """Del gris pálido (0) al azul marino (1)."""
    t = max(0.0, min(1.0, t))
    a, b = (241, 245, 251), (30, 39, 97)
    return "rgb(" + ", ".join(str(round(x + (y - x) * t)) for x, y in zip(a, b)) + ")"


def paso_bonito(rango, n=5):
    if rango <= 0:
        return 1.0
    bruto = rango / n
    mag = 10 ** math.floor(math.log10(bruto))
    for m in (1, 2, 2.5, 5, 10):
        if bruto <= m * mag:
            return m * mag
    return 10 * mag


def configuracion(cuerpo):
    conf = {}
    for l in cuerpo:
        m = CLAVE.match(l)
        if m:
            conf[m.group(1).lower()] = m.group(2).strip()
    return conf


def referencia(conf, leer):
    """(valor, etiqueta) de «referencia:», o (None, None); errores en una lista."""
    if not conf.get("referencia"):
        return None, []
    texto, _, etq = conf["referencia"].partition("·")
    texto = texto.strip()
    m = re.fullmatch(r"([A-Za-z_]\w*)\.([A-Za-z_]\w*)", texto)
    if m:
        d = leer(m.group(1))
        if d is None or m.group(2) not in d[0] or not d[1]:
            return None, [f"«referencia:» {texto} no existe o está vacío"]
        valor = numero(d[1][0][d[0].index(m.group(2))])
    else:
        valor = numero_texto(texto)
    if valor is None:
        return None, ["«referencia:» tiene que ser un número o modelo.columna"]
    return (valor, etq.strip()), []


# ─────────────────────────── preparar: leer y validar ───────────────────────────
def preparar(cuerpo, leer, formato):
    """Lee un bloque ```grafico y lo resuelve contra el lakehouse. Devuelve (datos, errores)."""
    conf = configuracion(cuerpo)
    tipo = conf.get("tipo", "barras").lower()
    if tipo not in TIPOS:
        return None, [f"«tipo: {tipo}» no existe; los tipos son: {', '.join(TIPOS)}"]
    falta = [k for k in ("titular", "modelo") if not conf.get(k)]
    if falta:
        return None, [f"falta «{k}:»" for k in falta]
    datos = leer(conf["modelo"])
    if datos is None:
        return None, [f"el modelo {conf['modelo']} no existe (¿has ejecutado dbt build?)"]
    cols, filas = datos
    g = {"tipo": tipo, "titular": conf["titular"], "modelo": conf["modelo"], "total": len(filas)}

    def columnas(*nombres):
        faltan = [c for c in nombres if c not in cols]
        return [f"{conf['modelo']} no tiene la columna {', '.join(faltan)} (tiene: {', '.join(cols)})"] if faltan else []

    if tipo in ("barras", "eje"):
        if not conf.get("barras"):
            return None, ["falta «barras:» (categoría → columna)"]
        partes = re.split(r"\s*(?:→|->)\s*", conf["barras"], maxsplit=1)
        if len(partes) != 2 or not partes[0] or not partes[1]:
            return None, ["«barras:» se escribe así: categoría → columna (o categoría → columna1, columna2)"]
        cat, series = partes[0].strip(), lista(partes[1])
        if len(series) > (1 if tipo == "eje" else 2):
            return None, ["«barras:» admite una columna en el tipo eje y una o dos en barras"]
        err = columnas(cat, *series)
        if err:
            return None, err
        puntos, vacias = [], 0
        for f in filas:
            crudos = [f[cols.index(c)] for c in series]
            if any(v is None for v in crudos):
                vacias += 1
                continue
            valores = [numero(v) for v in crudos]
            if any(v is None for v in valores):
                return None, [f"{conf['modelo']}: la columna {', '.join(series)} tiene valores que no son números"]
            puntos.append((formato(f[cols.index(cat)]), valores))
        if conf.get("solo"):
            quiero = lista(conf["solo"])
            fuera = [x for x in quiero if x not in [p[0] for p in puntos]]
            if fuera:
                return None, [f"«solo:» nombra {', '.join(fuera)}, que no está en la columna {cat}"]
            puntos = [p for p in puntos if p[0] in quiero]
        if conf.get("orden", "").lower() in ("desc", "asc"):
            puntos.sort(key=lambda p: p[1][-1], reverse=conf["orden"].lower() == "desc")
        puntos = puntos[:int(conf.get("limite", 15))]
        if not puntos:
            return None, ["no hay ninguna barra que dibujar"]
        destacar = lista(conf.get("destacar", ""))
        sin = [x for x in destacar if x not in [p[0] for p in puntos]]
        if sin:
            return None, [f"«destacar:» nombra {', '.join(sin)}, que no está entre las barras"]
        leyenda = lista(conf.get("leyenda", "")) or series
        if len(leyenda) != len(series):
            return None, [f"«leyenda:» necesita {len(series)} nombres separados por comas, uno por columna"]
        ref, err = referencia(conf, leer)
        if err:
            return None, err
        g.update(cat=cat, series=series, leyenda=leyenda, puntos=puntos, destacar=destacar, ref=ref, vacias=vacias)
        if tipo == "eje":
            corte = numero_texto(conf.get("corte", ""))
            if corte is None:
                return None, ["el tipo eje necesita «corte:», el valor donde empieza el eje truncado"]
            if min(v[0] for _, v in puntos) <= corte:
                return None, ["«corte:» tiene que quedar por debajo de todos los valores"]
            if len(puntos) < 2:
                return None, ["el tipo eje necesita al menos dos barras"]
            g["corte"] = corte
        return g, []

    if tipo == "linea":
        if not conf.get("x") or not conf.get("y"):
            return None, ["el tipo linea necesita «x:» (la columna del eje horizontal) e «y:» (una o dos columnas)"]
        x, series = conf["x"], lista(conf["y"])
        if len(series) > 2:
            return None, ["«y:» admite una o dos columnas"]
        err = columnas(x, *series)
        if err:
            return None, err
        puntos, vacias = [], 0
        for f in filas:
            ys = [numero(f[cols.index(c)]) for c in series]
            if any(f[cols.index(c)] is None for c in series):
                vacias += 1
                continue
            if any(v is None for v in ys):
                return None, [f"{conf['modelo']}: la columna {', '.join(series)} tiene valores que no son números"]
            puntos.append((f[cols.index(x)], ys))
        if conf.get("orden", "asc").lower() == "asc":
            try:
                puntos.sort(key=lambda p: p[0])
            except TypeError:
                pass
        if len(puntos) < 2:
            return None, ["una línea necesita al menos dos puntos"]
        etiquetas = [etiqueta_x(p[0], formato) for p in puntos]
        destacar = conf.get("destacar", "").strip()
        if destacar and destacar not in etiquetas:
            return None, [f"«destacar:» {destacar} no es ningún valor de {x} (por ejemplo: {', '.join(etiquetas[:3])}…)"]
        leyenda = lista(conf.get("leyenda", "")) or series
        if len(leyenda) != len(series):
            return None, [f"«leyenda:» necesita {len(series)} nombres separados por comas"]
        ref, err = referencia(conf, leer)
        if err:
            return None, err
        g.update(x=x, series=series, leyenda=leyenda, etiquetas=etiquetas, valores=[p[1] for p in puntos],
                 destacar=destacar, ref=ref, vacias=vacias)
        return g, []

    if tipo == "histograma":
        if not conf.get("columna"):
            return None, ["el tipo histograma necesita «columna:»"]
        c = conf["columna"]
        err = columnas(c)
        if err:
            return None, err
        crudos = [f[cols.index(c)] for f in filas if f[cols.index(c)] is not None]
        valores = [numero(v) for v in crudos]
        if any(v is None for v in valores):
            return None, [f"{conf['modelo']}: la columna {c} tiene valores que no son números"]
        log = conf.get("escala", "").lower() == "log"
        excluidos = 0
        if log:
            excluidos = sum(1 for v in valores if v <= 0)
            valores = [v for v in valores if v > 0]
        if len(valores) < 5:
            return None, ["un histograma necesita al menos cinco valores"]
        orden = sorted(valores)
        n = len(orden)

        def cuantil(q):
            pos = q * (n - 1)
            i = int(pos)
            return orden[i] + (orden[min(i + 1, n - 1)] - orden[i]) * (pos - i)
        marcas = {"media": sum(orden) / n, "mediana": cuantil(0.5), "p95": cuantil(0.95)}
        pedidas = lista(conf.get("marcas", "media, mediana, p95"))
        malas = [m for m in pedidas if m not in marcas]
        if malas:
            return None, [f"«marcas:» admite media, mediana y p95 (no {', '.join(malas)})"]
        lo, hi = orden[0], orden[-1]
        if log:
            a, b = math.log10(lo), math.log10(hi)
            b = b if b > a else a + 1
            k = 30
            bordes = [10 ** (a + (b - a) * i / k) for i in range(k + 1)]
        else:
            paso = numero_texto(conf["tramo"]) if conf.get("tramo") else paso_bonito(hi - lo, 20)
            if not paso or paso <= 0:
                return None, ["«tramo:» tiene que ser un número mayor que cero"]
            inicio = math.floor(lo / paso) * paso
            k = max(1, math.ceil((hi - inicio) / paso + 1e-9))
            if k > 80:
                return None, [f"con «tramo: {conf.get('tramo')}» salen {k} barras: usa un tramo mayor"]
            bordes = [inicio + paso * i for i in range(k + 1)]
        cuentas = [0] * (len(bordes) - 1)
        for v in orden:
            i = next((j for j in range(len(cuentas)) if v < bordes[j + 1]), len(cuentas) - 1)
            cuentas[i] += 1
        g.update(columna=c, log=log, bordes=bordes, cuentas=cuentas, marcas={m: marcas[m] for m in pedidas},
                 n=n, excluidos=excluidos, tramo=None if log else bordes[1] - bordes[0])
        return g, []

    # calor
    if not all(conf.get(k) for k in ("filas", "columnas", "valor")):
        return None, ["el tipo calor necesita «filas:», «columnas:» y «valor:»"]
    fc, cc, vc = conf["filas"], conf["columnas"], conf["valor"]
    err = columnas(fc, cc, vc)
    if err:
        return None, err
    celdas, orden_filas, valores_col = {}, [], []
    for f in filas:
        r, c, v = f[cols.index(fc)], f[cols.index(cc)], f[cols.index(vc)]
        if v is None:
            continue
        v = numero(v)
        if v is None:
            return None, [f"{conf['modelo']}: la columna {vc} tiene valores que no son números"]
        rk = formato(r)
        if rk not in orden_filas:
            orden_filas.append(rk)
        if c not in valores_col:
            valores_col.append(c)
        if (rk, c) in celdas:
            return None, [f"{conf['modelo']} tiene varias filas para {rk} × {etiqueta_x(c, formato)}: "
                          f"agrupa en el modelo (group by {fc}, {cc}) para que haya una por celda"]
        celdas[(rk, c)] = v
    if not celdas:
        return None, ["no hay ninguna celda con valor"]
    try:
        valores_col.sort()
    except TypeError:
        pass
    if len(valores_col) > 40:
        return None, [f"«columnas:» {cc} tiene {len(valores_col)} valores distintos: agrúpalos en el modelo (como mucho 40)"]
    normalizar = conf.get("normalizar", "").lower() == "fila"
    if normalizar:
        for rk in orden_filas:
            vs = [celdas[(rk, c)] for c in valores_col if (rk, c) in celdas]
            media = sum(vs) / len(vs) if vs else 0
            for c in valores_col:
                if (rk, c) in celdas:
                    celdas[(rk, c)] = celdas[(rk, c)] / media if media else 0
    if conf.get("orden", "").lower() in ("desc", "asc"):
        media_fila = lambda rk: sum(v for (r, _), v in celdas.items() if r == rk) / max(1, sum(1 for (r, _) in celdas if r == rk))
        orden_filas.sort(key=media_fila, reverse=conf["orden"].lower() == "desc")
    destacar = lista(conf.get("destacar", ""))
    sin = [x for x in destacar if x not in orden_filas]
    if sin:
        return None, [f"«destacar:» nombra {', '.join(sin)}, que no está en la columna {fc}"]
    g.update(fc=fc, cc=cc, vc=vc, filas=orden_filas, columnas=valores_col, celdas=celdas,
             etiquetas=[etiqueta_x(c, formato) for c in valores_col], normalizar=normalizar, destacar=destacar)
    return g, []


# ─────────────────────────── dibujar ───────────────────────────
def pie(g, texto):
    return f'<p class="g-fuente">Modelo <code>{e(g["modelo"])}</code> · {texto}</p>'


def cabecera(g):
    return f'<figcaption>{e(g["titular"])}</figcaption>'


def html_barras(g, formato):
    maximo = max([max(v) for _, v in g["puntos"]] + ([g["ref"][0]] if g["ref"] else []) + [0]) or 1
    pct = lambda v: f"{max(v, 0) / maximo * 100:.1f}%"
    doble = len(g["series"]) == 2
    filas = []
    for nombre, valores in g["puntos"]:
        dest = nombre in g["destacar"]
        if doble:
            pista = "".join(f'<div class="g-pista fina"><div class="g-barra s{k}" style="width:{pct(v)}"></div></div>'
                            for k, v in enumerate(valores))
            pista = f'<div class="g-pistas">{pista}</div>'
            valor = " → ".join(formato(v) for v in valores)
        else:
            clase = "destacada" if dest else ("gris" if g["destacar"] else "")
            linea = f'<div class="g-ref" style="left:{pct(g["ref"][0])}"></div>' if g["ref"] else ""
            pista = f'<div class="g-pista"><div class="g-barra {clase}" style="width:{pct(valores[0])}"></div>{linea}</div>'
            valor = formato(valores[0])
        filas.append(f'<div class="g-fila{" dest" if dest else ""}"><span class="g-etq">{e(nombre)}</span>{pista}'
                     f'<span class="g-valor">{e(valor)}</span></div>')
    extra = ""
    if g["ref"] and not doble:
        etq = formato(g["ref"][0]) + (f" · {g['ref'][1]}" if g["ref"][1] else "")
        extra = (f'<div class="g-fila"><span></span><div class="g-pista vacia"><span class="g-ref-etq" '
                 f'style="left:{pct(g["ref"][0])}">{e(etq)}</span></div><span></span></div>')
    leyenda = ('<div class="g-leyenda">' + "".join(f'<span><i class="s{k}"></i>{e(s)}</span>' for k, s in enumerate(g["leyenda"]))
               + "</div>") if doble else ""
    filtro = f" · se muestran {len(g['puntos'])} de {g['total']} filas" if len(g["puntos"]) < g["total"] else ""
    if g["vacias"]:
        filtro += f" ({g['vacias']} sin valor)"
    return (f'<figure class="grafico">{cabecera(g)}{leyenda}{"".join(filas)}{extra}'
            + pie(g, f'{e(g["cat"])} → {e(", ".join(g["series"]))}{filtro} · barras desde cero, leídas del lakehouse al generar esta web.')
            + "</figure>")


def html_eje(g, formato):
    puntos, corte = g["puntos"], g["corte"]
    maximo = max(v[0] for _, v in puntos)

    def panel(titulo, base):
        filas = "".join(
            f'<div class="g-fila"><span class="g-etq">{e(n)}</span><div class="g-pista"><div class="g-barra {"" if base == 0 else "gris"}" '
            f'style="width:{(v[0] - base) / (maximo - base) * 100:.1f}%"></div></div><span class="g-valor">{e(formato(v[0]))}</span></div>'
            for n, v in puntos)
        return f'<div class="g-panel"><span class="g-panel-t">{e(titulo)}</span>{filas}</div>'

    alto = max(puntos, key=lambda p: p[1][0])
    bajo = min(puntos, key=lambda p: p[1][0])
    real = alto[1][0] / bajo[1][0] if bajo[1][0] else float("inf")
    aparente = (alto[1][0] - corte) / (bajo[1][0] - corte)
    lectura = (f"Con el eje cortado en {formato(corte)}, {alto[0]} parece {formato(round(aparente, 1))} veces {bajo[0]}; "
               f"en realidad es {formato(round(real, 2))} veces.")
    return (f'<figure class="grafico">{cabecera(g)}<div class="g-paneles">{panel("Eje desde cero", 0)}'
            f'{panel("Eje cortado en " + formato(corte), corte)}</div><p class="g-lectura">{e(lectura)}</p>'
            + pie(g, f'{e(g["cat"])} → {e(g["series"][0])} · el eje truncado se dibuja siempre junto al honesto, nunca solo.')
            + "</figure>")


def html_linea(g, formato):
    W, H, L, R, T, B = 1000, 290, 64, 24, 34, 42
    valores = g["valores"]
    n = len(valores)
    tope = max([max(v) for v in valores] + ([g["ref"][0]] if g["ref"] else []) + [0])
    paso = paso_bonito(tope or 1, 4)
    ymax = max(paso * math.ceil((tope or 1) / paso), paso)
    X = lambda i: L + (W - L - R) * (i / (n - 1))
    Y = lambda v: H - B - (H - T - B) * max(v, 0) / ymax
    partes = []
    t = 0.0
    while t <= ymax + 1e-9:
        partes.append(f'<line x1="{L}" x2="{W - R}" y1="{Y(t):.1f}" y2="{Y(t):.1f}" stroke="#E7EBF2"></line>'
                      f'<text x="{L - 8}" y="{Y(t) + 4:.1f}" text-anchor="end" font-size="12" fill="#4A5470">{e(formato(t))}</text>')
        t += paso
    cada = max(1, math.ceil(n / 12))
    for i, et in enumerate(g["etiquetas"]):
        if i % cada == 0 or i == n - 1:
            ancla = "start" if i == 0 else "end" if i == n - 1 else "middle"   # los extremos no se salen del lienzo
            partes.append(f'<text x="{X(i):.1f}" y="{H - B + 20}" text-anchor="{ancla}" font-size="12" fill="#4A5470">{e(et)}</text>')
    colores = ["#1E2761", "#0F766E"]
    for s in range(len(g["series"])):
        pts = " ".join(f"{X(i):.1f},{Y(v[s]):.1f}" for i, v in enumerate(valores))
        if s == 0 and len(g["series"]) == 1:
            partes.append(f'<polygon points="{X(0):.1f},{Y(0):.1f} {pts} {X(n - 1):.1f},{Y(0):.1f}" fill="#E7EBF2"></polygon>')
        partes.append(f'<polyline points="{pts}" fill="none" stroke="{colores[s]}" stroke-width="3"></polyline>')
        for i, v in enumerate(valores):
            partes.append(f'<circle cx="{X(i):.1f}" cy="{Y(v[s]):.1f}" r="{3.5 if n <= 31 else 0}" fill="#FFFFFF" stroke="{colores[s]}" stroke-width="2"></circle>')
            if n <= 14 and len(g["series"]) == 1:
                partes.append(f'<text x="{X(i):.1f}" y="{Y(v[s]) - 10:.1f}" text-anchor="middle" font-size="12" fill="#1A2340">{e(formato(v[s]))}</text>')
    if g["ref"]:
        y = Y(g["ref"][0])
        etq = g["ref"][1] or formato(g["ref"][0])
        partes.append(f'<line x1="{L}" x2="{W - R}" y1="{y:.1f}" y2="{y:.1f}" stroke="#0F766E" stroke-width="2" stroke-dasharray="6 5"></line>'
                      f'<line x1="{W - R - 6.8 * len(etq) - 42:.0f}" x2="{W - R - 6.8 * len(etq) - 12:.0f}" y1="14" y2="14" stroke="#0F766E" stroke-width="2" stroke-dasharray="6 5"></line>'
                      f'<text x="{W - R}" y="18" text-anchor="end" font-size="12" font-weight="700" fill="#0F766E">{e(etq)}</text>')
    if g["destacar"]:
        i = g["etiquetas"].index(g["destacar"])
        v = valores[i][0]
        texto = f"{g['destacar']} · {formato(v)}"
        ancho = 9 * len(texto) + 16
        bx = min(max(X(i) - ancho / 2, L), W - R - ancho)
        partes.append(f'<rect x="{bx:.1f}" y="4" width="{ancho}" height="24" rx="5" fill="#0F766E"></rect>'
                      f'<text x="{bx + ancho / 2:.1f}" y="21" text-anchor="middle" font-size="13" font-weight="700" fill="#FFFFFF">{e(texto)}</text>'
                      f'<line x1="{X(i):.1f}" y1="28" x2="{X(i):.1f}" y2="{Y(v) - 6:.1f}" stroke="#0F766E" stroke-width="1.5"></line>')
    leyenda = ('<div class="g-leyenda">' + "".join(f'<span><i style="background:{colores[k]}"></i>{e(s)}</span>' for k, s in enumerate(g["leyenda"]))
               + "</div>") if len(g["series"]) == 2 else ""
    alt = f'{g["titular"]}: {", ".join(f"{a} {formato(v[0])}" for a, v in list(zip(g["etiquetas"], valores))[:12])}'
    svg = f'<svg class="g-svg" viewBox="0 0 {W} {H}" role="img" aria-label="{e(alt)}">{"".join(partes)}</svg>'
    vacias = f" · {g['vacias']} filas sin valor" if g["vacias"] else ""
    return (f'<figure class="grafico">{cabecera(g)}{leyenda}{svg}'
            + pie(g, f'{e(g["x"])} → {e(", ".join(g["series"]))}{vacias} · eje vertical desde cero.') + "</figure>")


def html_histograma(g, formato):
    bordes, cuentas, log = g["bordes"], g["cuentas"], g["log"]
    lo, hi = bordes[0], bordes[-1]
    pos = (lambda v: (math.log10(v) - math.log10(lo)) / (math.log10(hi) - math.log10(lo))) if log else (lambda v: (v - lo) / (hi - lo))
    tope = max(cuentas) or 1
    barras = "".join(f'<div class="g-hbar" title="{e(formato(a))} – {e(formato(b))}: {c}"><div style="height:{c / tope * 100:.1f}%"></div></div>'
                     for a, b, c in zip(bordes, bordes[1:], cuentas))
    nombres = {"media": "media", "mediana": "mediana", "p95": "p95"}
    marcas = []
    orden = sorted(g["marcas"].items(), key=lambda kv: kv[1])
    for k, (m, v) in enumerate(orden):
        lado = "izq" if k == 0 and len(orden) > 1 else "der"
        marcas.append(f'<div class="g-marca {m}" style="left:{pos(v) * 100:.1f}%"></div>'
                      f'<span class="g-marca-t {m} {lado}" style="left:{pos(v) * 100:.1f}%;top:{-22 if k < 2 else 4}px">{nombres[m]} {e(formato(v))}</span>')
    if log:
        ticks = [t * 10 ** p for p in range(math.floor(math.log10(lo)), math.ceil(math.log10(hi)) + 1) for t in (1, 3) if lo <= t * 10 ** p <= hi]
    else:
        paso = paso_bonito(hi - lo, 6)
        ticks, t = [], math.ceil(lo / paso) * paso
        while t <= hi + 1e-9:
            ticks.append(t)
            t += paso
    ejes = "".join(f'<span style="left:{pos(t) * 100:.1f}%">{e(formato(t))}</span>' for t in ticks)
    escala = "escala logarítmica" if log else f"tramos de {formato(g['tramo'])}"
    fuera = f" · {g['excluidos']} valores ≤ 0 fuera de la escala logarítmica" if g["excluidos"] else ""
    calc = ", ".join(nombres[m] for m in g["marcas"])
    return (f'<figure class="grafico">{cabecera(g)}<div class="g-hist"><div class="g-hbarras">{barras}</div>{"".join(marcas)}</div>'
            f'<div class="g-hejes">{ejes}</div>'
            + pie(g, f'columna {e(g["columna"])} · {formato(g["n"])} valores · {escala}{fuera} · {calc} calculadas con todos los valores.')
            + "</figure>")


def html_calor(g, formato):
    vals = list(g["celdas"].values())
    lo = 0.0 if min(vals) >= 0 else min(vals)
    hi = max(vals) or 1
    numeros = len(g["columnas"]) <= 14
    cab = '<span></span>' + "".join(f'<span class="g-ccol">{e(et)}</span>' for et in g["etiquetas"])
    filas = []
    for r in g["filas"]:
        celdas = []
        for c in g["columnas"]:
            v = g["celdas"].get((r, c))
            if v is None:
                celdas.append('<span class="g-celda vacia"></span>')
                continue
            t = (v - lo) / (hi - lo) if hi > lo else 0
            texto = e(formato(round(v, 2))) if numeros else ""
            celdas.append(f'<span class="g-celda" style="background:{mezcla(t)};color:{"#FFFFFF" if t > 0.55 else "#1A2340"}" '
                          f'title="{e(r)} · {e(formato(v))}">{texto}</span>')
        dest = " dest" if r in g["destacar"] else ""
        filas.append(f'<div class="g-cfila{dest}" style="grid-template-columns:minmax(90px,160px) repeat({len(g["columnas"])}, minmax(0,1fr))">'
                     f'<span class="g-etq">{e(r)}</span>{"".join(celdas)}</div>')
    nota = " · 1 = la media de su fila" if g["normalizar"] else ""
    escala = (f'<div class="g-escala"><span>{e(formato(round(lo, 2)))}</span><i></i><span>{e(formato(round(hi, 2)))} {e(g["vc"])}{nota}</span></div>')
    return (f'<figure class="grafico">{cabecera(g)}<div class="scroll"><div class="g-calor">'
            f'<div class="g-cfila" style="grid-template-columns:minmax(90px,160px) repeat({len(g["columnas"])}, minmax(0,1fr))">{cab}</div>'
            f'{"".join(filas)}</div></div>{escala}'
            + pie(g, f'{e(g["fc"])} × {e(g["cc"])} → {e(g["vc"])}{" normalizado por fila" if g["normalizar"] else ""} · color de menos a más.')
            + "</figure>")


def dibujar(cuerpo, leer, formato):
    """(html, errores, tipo) de un bloque ```grafico."""
    g, errores = preparar(cuerpo, leer, formato)
    if errores:
        return f'<p class="vacio">⚠️ Gráfico sin dibujar: {e("; ".join(errores))}</p>', errores, None
    hacer = {"barras": html_barras, "eje": html_eje, "linea": html_linea, "histograma": html_histograma, "calor": html_calor}
    return hacer[g["tipo"]](g, formato), [], g["tipo"]
