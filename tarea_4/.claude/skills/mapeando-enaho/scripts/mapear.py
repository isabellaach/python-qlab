"""Mapa coroplético de la pobreza monetaria por departamento con la ENAHO 2024, unido por código, no por nombre.

    uv run .claude/skills/mapeando-enaho/scripts/mapear.py
    uv run .claude/skills/mapeando-enaho/scripts/mapear.py --geojson datos/peru_departamental_simple.geojson

Une ccdd = ubigeo[:2] de la ENAHO con FIRST_IDDP del GeoJSON (ambos texto de dos dígitos), exige las 25 unidades
con dato (Lima 15 y Callao 07 por separado) y compara cada departamento con la referencia de la Sesión 16.
Sale: mapas/pobreza_departamento_2024.png y salidas/comparacion_mapa_referencia.csv. Si la unión falla, se detiene.
"""
import argparse
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

AQUI = Path(__file__).resolve().parent
REFERENCIA = AQUI.parent / "referencia_pobreza_departamento_2024.csv"
URL_GEOJSON = ("https://raw.githubusercontent.com/d2cml-ai/Data-Science-Python/main/sessions/06-geoespacial/"
               "lab/Data/peru_departamental_simple.geojson")
TOLERANCIA = 0.1                                            # pp frente a la referencia


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--salidas", default="salidas")
    p.add_argument("--geojson", default="datos/peru_departamental_simple.geojson")
    p.add_argument("--mapas", default="mapas")
    a = p.parse_args()
    salidas, mapas = Path(a.salidas), Path(a.mapas)
    if not (salidas / "hogares_2024.parquet").exists():
        sys.exit("ERROR: falta salidas/hogares_2024.parquet. Corre primero la skill limpiando-enaho: "
                 "uv run .claude/skills/limpiando-enaho/scripts/limpiar.py")
    if not Path(a.geojson).exists():
        sys.exit(f"ERROR: falta {a.geojson}. Bájalo con bash scripts/descargar_datos.sh ({URL_GEOJSON})")

    # Pobreza departamental ponderada con el método del INEI (sumaria, factor07 × mieperho)
    hog = pd.read_parquet(salidas / "hogares_2024.parquet")
    dep = (hog.assign(num=hog.pobre * hog.peso_personas).groupby(["ccdd", "departamento"], as_index=False)
           [["num", "peso_personas"]].sum())
    dep["pobreza_pct"] = dep.num / dep.peso_personas * 100
    dep["ccdd"] = dep.ccdd.astype(str).str.zfill(2)

    geo = gpd.read_file(a.geojson)
    geo["ccdd"] = geo.FIRST_IDDP.astype(str).str.zfill(2)
    mapa = geo.merge(dep[["ccdd", "departamento", "pobreza_pct"]], on="ccdd", how="left", validate="1:1")
    sin_dato = mapa[mapa.pobreza_pct.isna()]
    if len(mapa) != 25 or not sin_dato.empty or mapa.ccdd.nunique() != 25:
        sys.exit(f"ERROR: la unión por código no dio 25 departamentos con dato ({len(mapa)} geometrías; "
                 f"sin dato: {sin_dato.NOMBDEP.tolist()}). Revisen que ccdd y FIRST_IDDP sean texto de 2 dígitos.")
    assert {"07", "15"} <= set(mapa.ccdd), "Lima (15) y Callao (07) deben ir separados"

    # Comparación con la referencia de la Sesión 16
    ref = pd.read_csv(REFERENCIA, dtype={"ccdd": str}).rename(columns={"pobreza_pct": "referencia_pct",
                                                                         "departamento": "nombre_referencia"})
    comp = dep.merge(ref, on="ccdd", how="outer", validate="1:1", indicator=True)
    comp["diferencia_pp"] = (comp.pobreza_pct - comp.referencia_pct).round(2)
    comp["coincide"] = comp.diferencia_pp.abs() <= TOLERANCIA
    salidas.mkdir(exist_ok=True)
    comp.drop(columns=["num", "peso_personas", "_merge"]).round({"pobreza_pct": 2}).to_csv(
        salidas / "comparacion_mapa_referencia.csv", index=False)

    # Mapa
    vmax = 50 if mapa.pobreza_pct.max() <= 50 else float(mapa.pobreza_pct.max())
    fig, ax = plt.subplots(figsize=(7.5, 9.5))
    mapa.plot(column="pobreza_pct", cmap="Purples", vmin=0, vmax=vmax, edgecolor="white", linewidth=0.6, ax=ax,
              legend=True, legend_kwds={"label": "Pobreza monetaria (% de personas)", "shrink": 0.55,
                                        "orientation": "vertical"})
    puntos = mapa.to_crs(32718).representative_point().to_crs(mapa.crs)
    for (_, fila), pt in zip(mapa.iterrows(), puntos):
        if fila.ccdd == "07":                                   # Callao es muy chico: etiqueta al costado
            ax.annotate(f"Callao {fila.pobreza_pct:.1f}", (pt.x, pt.y), xytext=(-60, -6), textcoords="offset points",
                        fontsize=7, arrowprops={"arrowstyle": "-", "lw": 0.6, "color": "#444"})
            continue
        claro = fila.pobreza_pct < vmax * 0.55
        desplazamiento = {"06": (8, -22), "10": (-14, -6), "21": (14, 4)}.get(fila.ccdd, (0, 0))   # Cajamarca, Huánuco y Puno: alejar la etiqueta del borde
        ax.annotate(f"{fila.pobreza_pct:.1f}", (pt.x, pt.y), xytext=desplazamiento, textcoords="offset points",
                    ha="center", va="center", fontsize=7.5, fontweight="bold",
                    color="#222222" if claro else "white")
    mx, mn = mapa.loc[mapa.pobreza_pct.idxmax()], mapa.loc[mapa.pobreza_pct.idxmin()]
    ax.set_title(f"La pobreza va de {mn.pobreza_pct:.1f} % en {mn.departamento} a {mx.pobreza_pct:.1f} % en "
                 f"{mx.departamento}\nPobreza monetaria por departamento, Perú 2024", loc="left", fontsize=12,
                 fontweight="bold")
    ax.set_axis_off()
    fig.text(0.02, 0.02, "Fuente: INEI, ENAHO 2024 (módulo 34). Estimación ponderada (factor07 × mieperho).\n"
             "Límites: repositorio del curso (peru_departamental_simple.geojson). Unión ubigeo[:2] = FIRST_IDDP.",
             fontsize=7.5, color="#555555")
    mapas.mkdir(exist_ok=True)
    salida = mapas / "pobreza_departamento_2024.png"
    fig.savefig(salida, dpi=200, bbox_inches="tight")
    plt.close(fig)

    print(f"Mapa: {salida}  ·  {mapa.pobreza_pct.notna().sum()}/25 departamentos con dato, unidos por código")
    print(f"Comparación con la Sesión 16: {int(comp.coincide.sum())}/25 coinciden (± {TOLERANCIA} pp); "
          f"diferencia máxima {comp.diferencia_pp.abs().max():.2f} pp -> {salidas / 'comparacion_mapa_referencia.csv'}")
    print(comp.sort_values("pobreza_pct", ascending=False)[["ccdd", "departamento", "pobreza_pct", "referencia_pct",
                                                             "diferencia_pp"]].round(2).to_string(index=False))


if __name__ == "__main__":
    main()
