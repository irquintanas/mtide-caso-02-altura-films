# Caso 02 · Altura Films · el lakehouse de tu empresa

Reto individual del MTIDE 3.1 (Gestión y Visualización de Datos). Empresa y datos **ficticios**.

Eres el equipo de datos de **Altura Films**. Partes del parte diario que limpiaste en la J3 y lo conviertes en un
**lakehouse** con dbt: lo que llega se guarda tal cual en **bronce**, dbt lo limpia en **plata** y lo resume en **oro**,
y los **tests** paran cualquier dato malo antes de que llegue a las conclusiones. Todo lo publicas en tu propia cuenta
de GitHub como un **portal de datos** que explica, con tus cifras, qué has hecho y qué recomiendas.

Qué hay que hacer, bloque a bloque: **[ENCARGO.md](ENCARGO.md)**.

## Paso 0 · Preparar (una vez)

Necesitas una cuenta de GitHub, Git, Python 3.10 o superior y un editor (VS Code, por ejemplo).

1. En **tu** cuenta de GitHub, crea un repositorio **vacío y público** llamado `mtide-caso-02-altura-films` (sin README, sin .gitignore, sin licencia).
2. En ese repositorio nuevo: **Settings → Pages → Build and deployment → Source: GitHub Actions**. Hazlo antes de subir nada.
3. Clona este repositorio de partida, apúntalo al tuyo y súbelo:

   ```bash
   git clone https://github.com/irquintanas/mtide-caso-02-altura-films.git
   cd mtide-caso-02-altura-films
   git remote rename origin profesor        # el repositorio de partida queda como referencia
   git remote add origin https://github.com/TU-USUARIO/mtide-caso-02-altura-films.git
   git push -u origin main
   ```

4. Instala y prueba en tu portátil:

   ```bash
   python -m venv .venv
   source .venv/bin/activate                # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   dbt build --project-dir dbt --profiles-dir dbt
   python web/build.py                      # abre _site/index.html en el navegador
   ```

5. En tu repositorio de GitHub, pestaña **Actions**: la primera ejecución tiene que acabar en verde. Tu portal ya está en
   `https://TU-USUARIO.github.io/mtide-caso-02-altura-films/` (casi vacío: lo irás llenando).
6. Recomendado: **Settings → Rules → Rulesets → New branch ruleset** para `main`: *Require a pull request before merging*
   (con 0 aprobaciones) y *Require status checks to pass* (el check `comprobar`). Así nunca fusionas en rojo.
7. Manda a tu profesor los dos enlaces: el de tu repositorio y el de tu portal.

## El ciclo de cada bloque

```bash
git switch main && git pull               # parte siempre de main actualizado
git switch -c remesa                      # una rama por bloque: remesa, oro, fuentes, memo
# … el trabajo del bloque: ENCARGO.md …
dbt build --project-dir dbt --profiles-dir dbt     # hasta que todo esté en verde
python web/build.py                                # comprueba tus páginas y genera el portal
git add -A
git commit -m "Bloque 1: arreglo la remesa en plata"
git push -u origin remesa
```

En tu repositorio de GitHub: **Compare & pull request** (base: `main`). GitHub Actions lo comprueba; en la página de la
ejecución verás un resumen del lakehouse y, en *Artifacts*, un zip con plata y oro. **En verde, lo fusionas tú**
(*Merge pull request*). Cada cambio en `main` vuelve a publicar el portal, la documentación de dbt (`/dbt-docs/`) y los datos.

## Qué hay en el repositorio

| Ruta | Qué es |
|---|---|
| `lakehouse/bronce/` | Lo que llega, tal cual. **No se modifica nunca.** |
| `lakehouse/plata/`, `lakehouse/oro/` | Los Parquet que escribe dbt. No se suben a git: se reconstruyen en cada ejecución |
| `dbt/` | El proyecto dbt: `models/plata` (limpieza), `models/oro` (lo construyes tú), `tests/`, `seeds/` |
| `herramientas/sistema_simulado.py` | El sistema de Altura Films: manda los datos nuevos cuando el encargo lo pide |
| `paginas/` | Las páginas del portal que escribes tú (Markdown) |
| `web/build.py` | Comprueba tus páginas y genera el portal en `_site/`, con las cifras leídas del oro |
| `bi/resumen.py` | El resumen que aparece en cada ejecución de Actions |
| `.github/workflows/publicar.yml` | Comprobar en cada pull request; publicar en cada cambio de `main` |

## Las cifras de tus páginas

No escribas cifras a mano: escribe una **marca** y el portal pone el valor real del lakehouse.

| Marca | Qué pone |
|---|---|
| `{{ pregunta_1.ingreso_min[0] }}` | La columna `ingreso_min` de la primera fila (la 0) del modelo `pregunta_1` |
| `{{ pregunta_1.encargo[1] }}` | La columna `encargo` de la segunda fila |
| `{{ stg_parte.filas }}` | Cuántas filas tiene el modelo `stg_parte` |

Una página que empieza por `<!-- pendiente … -->` sale como «pendiente» y no se comprueba. Cuando empieces a escribirla,
borra esa línea y sustituye cada línea del guion (`> ✏️ …`) por tu texto. `python web/build.py` falla si queda alguna
línea del guion o una marca sin valor, y GitHub hará lo mismo con tu pull request.

## Si algo falla

- **`Conversion Error` / `Could not convert`** en `dbt build`: un dato no tiene el formato esperado. Busca la fila en bronce y arréglalo en plata.
- **`FAIL N`** en un test: N filas incumplen la regla. La SQL del test está en `dbt/target/compiled/…`: ejecútala con DuckDB para verlas.
- **`SKIP`**: no se construye porque algo de lo que depende ha fallado. Arregla lo primero que salga en rojo.
- **`database is locked`**: tienes `lakehouse/caso.duckdb` abierto en otro programa. Ciérralo.
- **Actions en rojo en «publicar» la primera vez**: no activaste Pages antes de subir. Actívalo y, en Actions, *Re-run jobs*.
- **Actions en rojo y en tu portátil en verde**: te falta subir algún fichero nuevo (`git status`).
- **El profesor ha corregido algo en el repositorio de partida**: `git pull profesor main`.
