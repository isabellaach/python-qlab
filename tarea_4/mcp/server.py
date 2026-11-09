"""Servidor MCP del BCRP: busca, descarga, resume y grafica series oficiales del Banco Central de Reserva del Perú.

    uv run pytest -q                                        # 8 pruebas de la sesión 04 + 2 propias
    uv run mcp/server.py                                    # el servidor, por stdio
    claude mcp add --scope project bcrp -- uv run mcp/server.py

Basado en el proyecto de la Sesión 04 (buscar_series venía hecha; serie, resumen, graficar_serie, el recurso y el
prompt son de esta tarea). Las cuentas las hace Python, no el modelo: así cada cifra sale de una llamada que se
puede repetir, con el código de la serie, el periodo y la URL oficial.
"""
import calendar
import json
import re
import time
import unicodedata
from datetime import datetime
from functools import cache
from pathlib import Path

import httpx
import pandas as pd
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

AQUI = Path(__file__).parent
RAIZ = AQUI.parent
CATALOGO = AQUI / "datos" / "catalogo_bcrp.csv"
FIGURAS = RAIZ / "figuras"
URL_CATALOGO = "https://estadisticas.bcrp.gob.pe/estadisticas/series/metadata"
API = "https://estadisticas.bcrp.gob.pe/estadisticas/series/api"
WEB = "https://estadisticas.bcrp.gob.pe/estadisticas/series"
SOLO_LECTURA = {"readOnlyHint": True, "openWorldHint": True}

mcp = FastMCP("bcrp", instructions=(
    "Series oficiales del Banco Central de Reserva del Perú (BCRP). Primero busca el código con buscar_series; "
    "luego usa resumen para variaciones, promedios y extremos, serie para los datos y graficar_serie para guardar "
    "un gráfico en figuras/. No calcules a mano: cita siempre el código de la serie, el periodo y la fuente."))


def _sin_tildes(s):
    return unicodedata.normalize("NFD", str(s).lower()).encode("ascii", "ignore").decode()


@cache
def catalogo():
    """El catálogo oficial: 17 mil series en unos 7 MB. Se baja una vez y queda en mcp/datos/."""
    if not CATALOGO.exists():
        CATALOGO.parent.mkdir(exist_ok=True)
        r = httpx.get(URL_CATALOGO, timeout=120)
        r.raise_for_status()
        CATALOGO.write_text(r.content.decode("latin-1"), encoding="utf-8")
    df = pd.read_csv(CATALOGO, sep=";", dtype=str).fillna("")
    df = df.rename(columns={"Código de serie": "codigo", "Categoría de serie": "categoria", "Grupo de serie": "grupo",
                            "Nombre de serie": "nombre", "Frecuencia": "frecuencia",
                            "Fecha de actualización": "actualizada", "Fecha de inicio": "inicio"})
    df["texto"] = (df.categoria + " " + df.grupo + " " + df.nombre).map(_sin_tildes)
    return df


def _ficha(codigo):
    fila = catalogo().query("codigo == @codigo")
    if fila.empty:
        raise ToolError(f"No existe el código de serie {codigo!r}. Búsquenlo con buscar_series.")
    f = fila.iloc[0]
    return {"codigo": f.codigo, "nombre": f"{f.grupo} - {f.nombre}", "categoria": f.categoria,
            "frecuencia": f.frecuencia, "inicio": f.inicio, "actualizada": f.actualizada}


@mcp.tool(annotations=SOLO_LECTURA)
def buscar_series(texto: str, frecuencia: str | None = None, limite: int = 10) -> list[dict]:
    """Busca series del BCRP por palabras: todas deben aparecer en la categoría, el grupo o el nombre.

    Ejemplos: "ipc 12 meses", "tipo de cambio interbancario venta", "reservas internacionales netas",
    "tasa de referencia", "cobre precio". frecuencia: "Diaria", "Mensual", "Trimestral" o "Anual".
    Devuelve el código, el nombre completo, la frecuencia y desde cuándo hay datos. Si no hay resultados,
    prueben con menos palabras.
    """
    df = catalogo()
    m = pd.Series(True, index=df.index)
    for palabra in _sin_tildes(texto).split():
        m &= df.texto.str.contains(re.escape(palabra))
    if frecuencia:
        m &= df.frecuencia.str.lower() == frecuencia.lower()
    # primero las series vigentes y, entre ellas, las de nombre más corto (las más generales)
    sel = df[m]
    orden = sel.assign(vieja=sel.actualizada < "2025", largo=(sel.grupo + sel.nombre).str.len())
    return [_ficha(c) for c in orden.sort_values(["vieja", "largo"]).head(limite).codigo]


# ---------------------------------------------------------------------------------------------------------------
# Fechas: lo que pide el usuario («2025-01», «2025-T1», «2026-10-15», «2025») → lo que pide la API, y lo que
# devuelve la API («Ene.2025», «T1.25», «01.Oct.26», «2025») → un periodo ordenable («2025-01», «2025-T1», ...).
# ---------------------------------------------------------------------------------------------------------------
MESES = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6, "jul": 7, "ago": 8, "set": 9, "sep": 9,
         "oct": 10, "nov": 11, "dic": 12}
CARPETA_WEB = {"Diaria": "diarias", "Mensual": "mensuales", "Trimestral": "trimestrales", "Anual": "anuales"}


def _partes(fecha: str):
    """«2025», «2025-03», «2025-T2», «2025-03-15» → (año, mes o trimestre, día, ¿es trimestre?)."""
    m = re.fullmatch(r"(\d{4})(?:-(T)?(\d{1,2}))?(?:-(\d{1,2}))?", str(fecha).strip(), flags=re.I)
    if not m:
        raise ToolError(f"Fecha {fecha!r} no válida. Usen AAAA, AAAA-MM, AAAA-T1 o AAAA-MM-DD.")
    anio, es_t, medio, dia = m.groups()
    return int(anio), (int(medio) if medio else None), (int(dia) if dia else None), bool(es_t)


def _fecha_api(fecha: str, frecuencia: str, fin: bool) -> str:
    anio, medio, dia, es_t = _partes(fecha)
    if frecuencia == "Anual":
        return f"{anio}"
    if frecuencia == "Trimestral":
        if medio is None:
            return f"{anio}-{4 if fin else 1}"
        return f"{anio}-{medio if es_t else (medio - 1) // 3 + 1}"
    if frecuencia == "Mensual":
        mes = medio if medio and not es_t else (12 if fin else 1)
        if es_t:
            mes = medio * 3 if fin else medio * 3 - 2
        return f"{anio}-{mes}"
    # diaria
    mes = medio or (12 if fin else 1)
    dia = dia or (calendar.monthrange(anio, mes)[1] if fin else 1)
    return f"{anio}-{mes:02d}-{dia:02d}"


def _periodo(nombre: str, frecuencia: str) -> str:
    n = nombre.strip()
    if frecuencia == "Mensual":                                   # «Ene.2025»
        mes, anio = n.split(".")
        return f"{anio}-{MESES[mes[:3].lower()]:02d}"
    if frecuencia == "Diaria":                                    # «01.Oct.26»
        dia, mes, anio = n.split(".")
        return f"{2000 + int(anio)}-{MESES[mes[:3].lower()]:02d}-{int(dia):02d}"
    if frecuencia == "Trimestral":                                # «T1.25»
        t, anio = n.split(".")
        return f"{2000 + int(anio)}-{t.upper()}"
    return n                                                      # anual: «2025»


@cache
def _descargar(codigo: str, desde: str, hasta: str) -> tuple:
    """Pide la serie a la API con hasta 4 intentos (si hay muchos pedidos seguidos, la API responde HTML)."""
    url = f"{API}/{codigo}/json/{desde}/{hasta}"
    for intento in range(4):
        try:
            r = httpx.get(url, timeout=60, follow_redirects=True)
            js = json.loads(r.content.decode("utf-8-sig"))
            return url, js["config"]["series"][0]["name"], tuple((p["name"], p["values"][0]) for p in js["periods"])
        except (json.JSONDecodeError, KeyError, IndexError, httpx.HTTPError):
            time.sleep(2 * (intento + 1))
    raise ToolError(f"El BCRP no respondió con datos para {codigo} entre {desde} y {hasta} ({url}). "
                    "Puede ser un límite de pedidos: reintenten en unos segundos.")


@mcp.tool(annotations=SOLO_LECTURA)
def serie(codigo: str, desde: str, hasta: str) -> dict:
    """Descarga los datos oficiales de una serie del BCRP entre dos fechas (ambas incluidas).

    Úsenla cuando necesiten los valores periodo a periodo. Fechas: "2025-01" (mensual), "2025-T1" (trimestral),
    "2026-10-15" (diaria) o "2025" (anual o año completo). Ejemplo: serie("PN01273PM", "2024-01", "2024-12").
    Devuelve el código, el nombre, la frecuencia, los datos [{periodo, valor}] y la URL oficial en «fuente».
    Para variaciones, promedios o extremos usen resumen: no calculen a mano.
    """
    codigo = codigo.strip().upper()
    ficha = _ficha(codigo)
    frec = ficha["frecuencia"]
    a, b = _fecha_api(desde, frec, fin=False), _fecha_api(hasta, frec, fin=True)
    url, nombre_api, periodos = _descargar(codigo, a, b)
    datos = []
    for nombre, valor in periodos:
        try:
            datos.append({"periodo": _periodo(nombre, frec), "valor": float(valor)})
        except ValueError:                                         # «n.d.»: sin dato ese periodo
            continue
    if not datos:
        raise ToolError(f"La serie {codigo} no tiene datos entre {desde} y {hasta}. Revisen el periodo: "
                        f"empieza en {ficha['inicio']} y se actualizó el {ficha['actualizada']}.")
    return {"codigo": codigo, "nombre": nombre_api or ficha["nombre"], "frecuencia": frec, "desde": desde,
            "hasta": hasta, "datos": datos, "fuente": url,
            "pagina_web": f"{WEB}/{CARPETA_WEB.get(frec, 'mensuales')}/resultados/{codigo}/html/{a}/{b}/"}


def _resumir(s: dict) -> dict:
    df = pd.DataFrame(s["datos"])
    primero, ultimo = df.iloc[0], df.iloc[-1]
    imax, imin = df.valor.idxmax(), df.valor.idxmin()
    cambio = ultimo.valor - primero.valor
    return {"codigo": s["codigo"], "nombre": s["nombre"], "frecuencia": s["frecuencia"], "n_datos": len(df),
            "primero": {"periodo": primero.periodo, "valor": round(float(primero.valor), 4)},
            "ultimo": {"periodo": ultimo.periodo, "valor": round(float(ultimo.valor), 4)},
            "cambio": round(float(cambio), 4),
            "variacion_pct": round(float(cambio / primero.valor * 100), 4) if primero.valor else None,
            "promedio": round(float(df.valor.mean()), 4),
            "maximo": {"periodo": df.periodo[imax], "valor": round(float(df.valor[imax]), 4)},
            "minimo": {"periodo": df.periodo[imin], "valor": round(float(df.valor[imin]), 4)},
            "fuente": s["fuente"], "pagina_web": s["pagina_web"]}


@mcp.tool(annotations=SOLO_LECTURA)
def resumen(codigo: str, desde: str, hasta: str) -> dict:
    """Resume una serie del BCRP en un periodo: primer y último valor, cambio absoluto, variación % entre ambos,
    promedio, máximo y mínimo (con su periodo), y la URL oficial.

    Úsenla para cualquier cifra calculada (cuánto subió, el promedio de un año, el pico de la inflación) en lugar
    de hacer cuentas a mano. Ejemplo: resumen("PN01273PM", "2024-01", "2024-12"). Ojo: «cambio» es la diferencia
    entre el último y el primer valor; si la serie ya es una variación %, el cambio está en puntos porcentuales.
    """
    return _resumir(serie(codigo, desde, hasta))


@mcp.tool(annotations={"readOnlyHint": False, "openWorldHint": True})
def graficar_serie(codigo: str, desde: str, hasta: str, comparar_con: str | None = None,
                   lineas_referencia: list[float] | None = None, etiqueta_referencia: str = "Rango meta del BCRP",
                   titulo: str | None = None, archivo: str | None = None) -> dict:
    """Grafica una serie oficial del BCRP (y, si se pide, una segunda serie en el mismo eje) y guarda un PNG.

    Úsenla cuando pidan un gráfico, una figura o «ver la evolución» de un indicador del BCRP, o para ilustrar un
    informe. El PNG (200 dpi) queda en figuras/ con título, unidades, el periodo y la fuente con los códigos.
    - comparar_con: otro código con la misma unidad, por ejemplo IPC total frente a IPC de alimentos.
    - lineas_referencia: valores a marcar con líneas horizontales, por ejemplo [1, 3] para el rango meta de
      inflación del BCRP; con dos valores se sombrea la banda y se rotula con etiqueta_referencia.
    - titulo: el hallazgo en una frase; si es largo se parte en dos líneas.
    Ejemplo: graficar_serie("PN01273PM", "2020-01", "2024-12", lineas_referencia=[1, 3]).
    Devuelve la ruta del PNG y el resumen numérico de cada serie graficada, con sus fuentes.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    codigos = [codigo] + ([comparar_con] if comparar_con else [])
    series = [serie(c, desde, hasta) for c in codigos]
    fig, ax = plt.subplots(figsize=(9, 5))
    colores = ["#5B2A86", "#E07A1F"]
    for s, color in zip(series, colores):
        df = pd.DataFrame(s["datos"])
        etiqueta = s["nombre"].split(" - ")[-1]
        if s["frecuencia"] == "Diaria":
            x = pd.to_datetime(df.periodo)
        elif s["frecuencia"] == "Mensual":
            x = pd.to_datetime(df.periodo + "-01")
        else:
            x = df.periodo
        ax.plot(x, df.valor, color=color, lw=2, label=f"{etiqueta} ({s['codigo']})")
        ax.annotate(f"{df.valor.iloc[-1]:.1f}", (x.iloc[-1], df.valor.iloc[-1]), xytext=(5, 0),
                    textcoords="offset points", color=color, va="center", fontsize=9, fontweight="bold")
    for v in lineas_referencia or []:
        ax.axhline(v, color="#999999", ls="--", lw=1)
    if len(lineas_referencia or []) == 2:
        bajo, alto = sorted(lineas_referencia)
        ax.axhspan(bajo, alto, color="#2A9D8F", alpha=0.10, label=f"{etiqueta_referencia} ({bajo:g}–{alto:g})")
    valores = [d["valor"] for s in series for d in s["datos"]]
    if min(valores) < 0 < max(valores):
        ax.axhline(0, color="#333333", lw=0.8)
    grupo = series[0]["nombre"].split(" - ")[0]
    unidad = re.findall(r"\(([^()]*)\)", grupo)                      # «(var% 12 meses)», «(S/ por US$)»
    unidad = unidad[-1] if unidad else grupo
    import textwrap
    ax.set_title(textwrap.fill(titulo or f"{series[0]['nombre'].split(' - ')[-1]}, {desde} a {hasta}", 70),
                 loc="left", fontsize=13, fontweight="bold")
    ax.set_ylabel(unidad, fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.3)
    ax.legend(frameon=False, fontsize=9, loc="best")
    fig.text(0.01, 0.01, f"Fuente: BCRP, Estadísticas ({', '.join(codigos)}), consultado el "
             f"{datetime.now():%d/%m/%Y}. Elaborado con el MCP bcrp (graficar_serie).", fontsize=8, color="#555555")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    FIGURAS.mkdir(exist_ok=True)
    nombre = archivo or f"bcrp_{'_'.join(codigos)}_{desde}_{hasta}.png"
    ruta = FIGURAS / Path(nombre).with_suffix(".png").name
    fig.savefig(ruta, dpi=200)
    plt.close(fig)
    return {"archivo": str(ruta.relative_to(RAIZ)), "ruta_absoluta": str(ruta),
            "series": [_resumir(s) for s in series], "fuente": [s["fuente"] for s in series]}


@mcp.resource("bcrp://serie/{codigo}", mime_type="application/json")
def ficha_serie(codigo: str) -> str:
    """Ficha descriptiva de una serie del BCRP: nombre, categoría, frecuencia, desde cuándo hay datos, cuándo se
    actualizó y dónde verla en la web oficial."""
    f = _ficha(codigo.strip().upper())
    f["pagina_web"] = f"{WEB}/{CARPETA_WEB.get(f['frecuencia'], 'mensuales')}/"
    f["api_ejemplo"] = f"{API}/{f['codigo']}/json"
    return json.dumps(f, ensure_ascii=False, indent=2)


@mcp.prompt
def informe(tema: str) -> str:
    """Pide un informe breve sobre un tema con series del BCRP, con cada cifra trazable."""
    return (f"Prepara un informe breve sobre «{tema}» con series oficiales del BCRP.\n"
            "1. Usa buscar_series para identificar las series pertinentes y di por qué eliges cada código.\n"
            "2. Usa resumen (y serie si hacen falta los datos) para cada cifra: no hagas cuentas a mano.\n"
            "3. Usa graficar_serie para una figura que muestre la evolución principal.\n"
            "4. Escribe: contexto (2 líneas), 3 hallazgos con su cifra, interpretación y limitaciones.\n"
            "5. Cada cifra va con el código de la serie, el periodo y la URL oficial. Si una herramienta falla o "
            "no hay datos, dilo en vez de estimar. No presentes asociaciones como causas.")


if __name__ == "__main__":
    mcp.run()
