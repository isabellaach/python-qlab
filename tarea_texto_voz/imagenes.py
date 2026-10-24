"""Imágenes del reel, dibujadas con los resultados de tarea_data_raster.

Uso:
    python imagenes.py        # escribe salidas/img/<nombre>.png (960×720, fondo oscuro)

Cada escena de guion.json nombra su imagen en el campo "imagen".
"""

import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Circle, Polygon

AQUI = Path(__file__).parent
RASTER = AQUI.parent / "tarea_data_raster"
SALIDA = AQUI / "salidas" / "img"

FONDO, TIERRA, BORDE, TEXTO, GRIS = "#121418", "#1F2229", "#3A3F48", "#F0F0F0", "#9AA0A8"
ROJO, NARANJA, VERDE = "#E5484D", "#FF7A1A", "#4F7A5A"
JULI, CANDARAVE = 2540, 2564

plt.rcParams.update({"font.family": "Arial", "font.size": 22, "text.color": TEXTO})


def poligonos(geom):
    if geom is None:
        return []
    partes = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    return [p[0] for p in partes]


def capa(ax, features, **kw):
    for f in features:
        for anillo in poligonos(f["geometry"]):
            ax.add_patch(Polygon(anillo, closed=True, **kw))


def lienzo():
    fig = plt.figure(figsize=(9.6, 7.2), dpi=100, facecolor=FONDO)
    ax = fig.add_axes([0, 0, 1, 1], facecolor=FONDO)
    ax.set_axis_off()
    return fig, ax


def encuadre(ax, lon, lat, radio_km):
    """Centra en (lon, lat) con proporción 4:3 y escala real en km."""
    k = math.cos(math.radians(lat))
    dy = radio_km / 111
    dx = dy * 4 / 3 / k
    ax.set_xlim(lon - dx, lon + dx)
    ax.set_ylim(lat - dy, lat + dy)
    ax.set_aspect(1 / k)


def encuadre_limites(ax, features, puntos, margen=0.15):
    """Encuadra 4:3 lo que ocupan los corredores y los puntos dados."""
    xs = [x for f in features for a in poligonos(f["geometry"]) for x, _ in a] + [x for x, _ in puntos]
    ys = [y for f in features for a in poligonos(f["geometry"]) for _, y in a] + [y for _, y in puntos]
    lon, lat = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    k = math.cos(math.radians(lat))
    radio_km = max((max(ys) - min(ys)) / 2, (max(xs) - min(xs)) / 2 * k * 3 / 4) * 111 * (1 + margen)
    encuadre(ax, lon, lat, radio_km)


def guardar(fig, nombre):
    fig.savefig(SALIDA / f"{nombre}.png", facecolor=FONDO)
    plt.close(fig)


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    deps = json.loads((RASTER / "datos/peru_departamental_simple.geojson").read_text())["features"]
    dists = json.loads((RASTER / "datos/peru_distrital_simple.geojson").read_text())["features"]
    corr = json.loads((RASTER / "resultados/corredores.geojson").read_text())["features"]
    exp = pd.read_csv(RASTER / "resultados/exposicion_incendios.csv")
    exp["nivel"] = exp.semaforo.str.split(" ").str[0]
    alerta = pd.read_csv(RASTER / "resultados/distritos_en_alerta.csv")
    pob = pd.read_csv(RASTER / "resultados/poblados_cercanos.csv")

    def corredores(ids, horizonte):
        return [f for f in corr if f["properties"]["incendio_id"] in ids and f["properties"]["horizonte_h"] == horizonte]

    def peru(ax):
        capa(ax, deps, facecolor=TIERRA, edgecolor=BORDE, linewidth=0.8)
        ax.set_xlim(-84.5, -66.5)
        ax.set_ylim(-18.6, 0.2)
        ax.set_aspect(1.0)

    def puntos(ax, nivel, color, tam):
        d = exp[exp.nivel == nivel]
        ax.scatter(d.lon, d.lat, s=tam, c=color, edgecolors=FONDO, linewidths=0.8, zorder=5)

    juli = exp[exp.incendio_id == JULI].iloc[0]

    # 1. Todos los incendios activos por nivel
    fig, ax = lienzo()
    peru(ax)
    puntos(ax, "VERDE", VERDE, 40)
    puntos(ax, "ÁMBAR", NARANJA, 110)
    puntos(ax, "ROJO", ROJO, 320)
    ax.annotate("Juli", (juli.lon, juli.lat), xytext=(-66.8, -14.2), color=ROJO, fontsize=28, weight="bold",
                ha="right", arrowprops=dict(arrowstyle="-", color=ROJO, lw=1.5))
    for i, (txt, col) in enumerate([("Preparar evacuación", ROJO), ("Alerta temprana", NARANJA), ("Vigilar", VERDE)]):
        ax.scatter([], [], c=col, s=150, label=txt)
    ax.legend(loc="lower left", frameon=False, labelcolor=TEXTO, fontsize=22, bbox_to_anchor=(0.03, 0.03))
    guardar(fig, "mapa_peru")

    # 2. Corredores de Juli a 24, 48 y 72 h
    fig, ax = lienzo()
    capa(ax, dists, facecolor=TIERRA, edgecolor=BORDE, linewidth=0.8)
    for h, alfa in [(72, 0.25), (48, 0.45), (24, 0.85)]:
        capa(ax, corredores({JULI}, h), facecolor=ROJO, alpha=alfa, edgecolor="none")
    ax.scatter([juli.lon], [juli.lat], s=260, marker="*", c="#FFD166", edgecolors=FONDO, zorder=6)
    encuadre(ax, juli.lon, juli.lat - 0.06, 16)
    ax.text(0.04, 0.94, "Juli, Puno", transform=ax.transAxes, fontsize=34, weight="bold", va="top")
    ax.text(0.04, 0.85, "Corredor del fuego: 24 h (intenso) a 72 h (claro)", transform=ax.transAxes,
            fontsize=22, color=GRIS, va="top")
    guardar(fig, "juli")

    # 3. Poblados en el camino de Juli, con hora estimada de llegada
    fig, ax = lienzo()
    p = pob[pob.incendio_id == JULI].sort_values("llegada_h")
    proximos = p[(p.llegada_h > 0)].head(4)
    capa(ax, dists, facecolor=TIERRA, edgecolor=BORDE, linewidth=0.8)
    ax.scatter(p.lon, p.lat, s=30, c=GRIS, zorder=4)
    ax.scatter([juli.lon], [juli.lat], s=520, marker="*", c="#FFD166", edgecolors=FONDO, zorder=6)
    for n, (_, r) in enumerate(proximos.iterrows(), 1):
        ax.scatter([r.lon], [r.lat], s=520, c=NARANJA, edgecolors=FONDO, zorder=5)
        ax.text(r.lon, r.lat, str(n), ha="center", va="center", fontsize=18, weight="bold", color=FONDO, zorder=7)
        ax.text(0.38, 0.80 - n * 0.09, f"{n}  {r.nombre}", transform=ax.transAxes, fontsize=22, weight="bold")
        ax.text(0.98, 0.80 - n * 0.09, f"~{r.llegada_h:.0f} h", transform=ax.transAxes, fontsize=22,
                weight="bold", color=NARANJA, ha="right")
    encuadre(ax, juli.lon + 0.016, juli.lat - 0.004, 1.7)
    ax.text(0.04, 0.95, "Hora estimada de llegada del fuego", transform=ax.transAxes, fontsize=28,
            weight="bold", va="top")
    ax.text(0.04, 0.87, "Amarillo: el incendio · gris: otros poblados", transform=ax.transAxes, fontsize=22, color=GRIS, va="top")
    guardar(fig, "juli_poblados")

    # 4. Los 56 distritos en el camino del fuego
    claves = set(zip(alerta.NOMBDIST, alerta.NOMBPROV, alerta.NOMBDEP))
    en_camino = [f for f in dists if (f["properties"]["NOMBDIST"], f["properties"]["NOMBPROV"], f["properties"]["NOMBDEP"]) in claves]
    fig, ax = lienzo()
    peru(ax)
    capa(ax, en_camino, facecolor=NARANJA, edgecolor=NARANJA, linewidth=1.2)
    puntos(ax, "ROJO", ROJO, 320)
    ax.text(0.97, 0.95, f"{len(en_camino)} distritos", transform=ax.transAxes, ha="right", va="top",
            fontsize=34, weight="bold", color=NARANJA)
    ax.text(0.97, 0.87, "tocados por un corredor de 72 h", transform=ax.transAxes, ha="right", va="top",
            fontsize=22, color=GRIS)
    guardar(fig, "distritos")
    print(f"Distritos dibujados: {len(en_camino)} de {len(claves)}")

    # 5. Candarave: corredor de 72 h contra círculo fijo de 5 km
    c = exp[exp.incendio_id == CANDARAVE].iloc[0]
    fig, ax = lienzo()
    capa(ax, dists, facecolor=TIERRA, edgecolor=BORDE, linewidth=0.8)
    capa(ax, corredores({CANDARAVE}, 72), facecolor=NARANJA, alpha=0.75, edgecolor="none")
    k = math.cos(math.radians(c.lat))
    ax.add_patch(Circle((c.lon, c.lat), 5 / 111, transform=ax.transData, fill=False, edgecolor=TEXTO,
                        linestyle="--", linewidth=2.5))
    ax.scatter([c.lon], [c.lat], s=300, marker="*", c="#FFD166", edgecolors=FONDO, zorder=6)
    encuadre_limites(ax, corredores({CANDARAVE}, 72), [(c.lon, c.lat)], margen=0.35)
    ax.text(0.04, 0.95, f"Corredor del viento: {c.personas_72h:,.0f} personas".replace(",", " "),
            transform=ax.transAxes, fontsize=28, weight="bold", color=NARANJA, va="top")
    ax.text(0.04, 0.86, f"Círculo fijo de 5 km: {c.personas_5km_circulo:,.0f} personas",
            transform=ax.transAxes, fontsize=28, color=TEXTO, va="top")
    guardar(fig, "candarave")

    # 6. Respuesta: Juli y los distritos en alerta
    fig, ax = lienzo()
    peru(ax)
    capa(ax, en_camino, facecolor=NARANJA, edgecolor=NARANJA, linewidth=1.2)
    puntos(ax, "ROJO", ROJO, 420)
    ax.annotate("Juli: preparar hoy", (juli.lon, juli.lat), xytext=(-72.5, -17.9), color=ROJO, fontsize=28,
                weight="bold", ha="right", arrowprops=dict(arrowstyle="-", color=ROJO, lw=1.5))
    ax.text(0.97, 0.95, "Distritos en alerta", transform=ax.transAxes, ha="right", va="top", fontsize=30,
            color=NARANJA, weight="bold")
    guardar(fig, "corredores")


if __name__ == "__main__":
    main()
