"""Gráficos de pobreza monetaria con la ENAHO 2024 limpia (salidas/*_2024.parquet), siempre ponderados.

    uv run .claude/skills/graficando-enaho/scripts/graficar.py --tipo area           # urbana frente a rural
    uv run .claude/skills/graficando-enaho/scripts/graficar.py --tipo sexo           # o sexo_area, edad
    uv run .claude/skills/graficando-enaho/scripts/graficar.py --tipo departamento   # los 25, ordenados
    uv run .claude/skills/graficando-enaho/scripts/graficar.py --tipo todos

Cada gráfico: barras desde cero, un color, el valor escrito, la línea del promedio nacional, un título que dice el
hallazgo (calculado de los datos), el periodo, la unidad y la fuente. PNG a 200 dpi en figuras/.
Imprime la tabla con las cifras para que quien pidió el gráfico pueda citarlas.
"""
import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

MORADO, GRIS, TEXTO = "#5B2A86", "#8A8A8A", "#333333"
FUENTE = ("Fuente: INEI, ENAHO 2024 (módulos 34 y 02). Estimación ponderada: {metodo}.\n"
          "Pobreza monetaria: gasto per cápita del hogar por debajo de la línea de pobreza.")
TIPOS = ["area", "sexo", "sexo_area", "edad", "departamento"]


def tasa(d, peso):
    return (d.pobre * d[peso]).sum() / d[peso].sum() * 100


def cargar(salidas: Path):
    faltan = [f for f in ("hogares_2024.parquet", "personas_2024.parquet") if not (salidas / f).exists()]
    if faltan:
        sys.exit(f"ERROR: faltan {faltan} en {salidas}/. Corre primero la skill limpiando-enaho: "
                 "uv run .claude/skills/limpiando-enaho/scripts/limpiar.py")
    return pd.read_parquet(salidas / "hogares_2024.parquet"), pd.read_parquet(salidas / "personas_2024.parquet")


def barras(tabla, titulo, subtitulo, metodo, archivo, nacional, horizontal=False, etiqueta_nacional="Perú"):
    alto = 0.32 * len(tabla) + 1.8 if horizontal else 5
    fig, ax = plt.subplots(figsize=(9, alto))
    if horizontal:
        tabla = tabla.sort_values("pobreza_pct")
        ax.barh(tabla.categoria, tabla.pobreza_pct, color=MORADO, height=0.7)
        for y, v in enumerate(tabla.pobreza_pct):
            ax.text(v + 0.4, y, f"{v:.1f}", va="center", fontsize=8, color=TEXTO)
        ax.axvline(nacional, color=GRIS, ls="--", lw=1)
        ax.text(nacional + 0.3, len(tabla) - 0.4, f"{etiqueta_nacional}: {nacional:.1f} %", color=GRIS, fontsize=8)
        ax.set_xlim(0, tabla.pobreza_pct.max() * 1.12)
        ax.set_xlabel("% de personas en pobreza monetaria")
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(axis="y", length=0, labelsize=9)
    else:
        ax.bar(tabla.categoria, tabla.pobreza_pct, color=MORADO, width=0.6)
        for x, v in enumerate(tabla.pobreza_pct):
            ax.text(x, v + 0.6, f"{v:.1f} %", ha="center", fontsize=11, fontweight="bold", color=TEXTO)
        ax.axhline(nacional, color=GRIS, ls="--", lw=1)
        ax.text(-0.45, nacional + 0.6, f"{etiqueta_nacional}: {nacional:.1f} %", color=GRIS, fontsize=9)
        ax.set_ylim(0, max(tabla.pobreza_pct.max(), nacional) * 1.18)
        ax.set_ylabel("% de personas en pobreza monetaria")
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle(titulo, x=0.01, ha="left", fontsize=13, fontweight="bold")
    ax.set_title(subtitulo, loc="left", fontsize=9.5, color="#555555")
    fig.text(0.01, 0.01, FUENTE.format(metodo=metodo), fontsize=7.5, color="#555555")
    fig.tight_layout(rect=(0, 0.045 if horizontal else 0.07, 1, 1))
    fig.savefig(archivo, dpi=200)
    plt.close(fig)
    return archivo


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--tipo", default="todos", choices=TIPOS + ["todos"])
    p.add_argument("--salidas", default="salidas")
    p.add_argument("--figuras", default="figuras")
    a = p.parse_args()
    hog, per = cargar(Path(a.salidas))
    figs = Path(a.figuras)
    figs.mkdir(exist_ok=True)
    INEI, PERS = "hogares × miembros (factor07 × mieperho), método INEI", "residentes habituales (facpob07)"
    nac_inei, nac_pers = tasa(hog, "peso_personas"), tasa(per, "facpob07")
    hechos = []

    for tipo in TIPOS if a.tipo == "todos" else [a.tipo]:
        if tipo == "area":
            t = (hog.groupby("area").apply(tasa, "peso_personas", include_groups=False).rename("pobreza_pct")
                 .reindex(["Urbana", "Rural"]).reset_index().rename(columns={"area": "categoria"}))
            u, r = t.pobreza_pct
            titulo = f"La pobreza rural ({r:.1f} %) supera en {r - u:.1f} puntos a la urbana ({u:.1f} %)"
            sub = "Pobreza monetaria por área de residencia, Perú 2024 (% de personas)"
            f = barras(t, titulo, sub, INEI, figs / "pobreza_area_2024.png", nac_inei)
        elif tipo == "sexo":
            t = (per.groupby("sexo").apply(tasa, "facpob07", include_groups=False).rename("pobreza_pct")
                 .reindex(["Hombre", "Mujer"]).reset_index().rename(columns={"sexo": "categoria"}))
            h, m = t.pobreza_pct
            titulo = (f"La pobreza es casi igual entre mujeres ({m:.1f} %) y hombres ({h:.1f} %)" if abs(m - h) < 1
                      else f"Pobreza de mujeres ({m:.1f} %) frente a hombres ({h:.1f} %): {m - h:+.1f} puntos")
            sub = "Pobreza monetaria por sexo, Perú 2024 (% de personas; la pobreza se mide por hogar)"
            f = barras(t, titulo, sub, PERS, figs / "pobreza_sexo_2024.png", nac_pers)
        elif tipo == "sexo_area":
            t = (per.groupby(["area", "sexo"]).apply(tasa, "facpob07", include_groups=False).rename("pobreza_pct")
                 .reset_index())
            t["categoria"] = t.sexo + "\n" + t.area.str.lower()
            t = t.set_index(["area", "sexo"]).loc[[("Urbana", "Hombre"), ("Urbana", "Mujer"),
                                                    ("Rural", "Hombre"), ("Rural", "Mujer")]].reset_index()
            titulo = "La brecha está en el área de residencia, no en el sexo"
            sub = "Pobreza monetaria por sexo y área, Perú 2024 (% de personas)"
            f = barras(t, titulo, sub, PERS, figs / "pobreza_sexo_area_2024.png", nac_pers)
        elif tipo == "edad":
            orden = ["0-17", "18-29", "30-44", "45-64", "65 y más"]
            t = (per.groupby("grupo_edad").apply(tasa, "facpob07", include_groups=False).rename("pobreza_pct")
                 .reindex(orden).reset_index().rename(columns={"grupo_edad": "categoria"}))
            mx = t.loc[t.pobreza_pct.idxmax()]
            titulo = f"El grupo de {mx.categoria} años tiene la mayor pobreza ({mx.pobreza_pct:.1f} %)"
            sub = "Pobreza monetaria por grupo de edad, Perú 2024 (% de personas)"
            f = barras(t, titulo, sub, PERS, figs / "pobreza_edad_2024.png", nac_pers)
        else:
            t = (hog.groupby(["ccdd", "departamento"]).apply(tasa, "peso_personas", include_groups=False)
                 .rename("pobreza_pct").reset_index().rename(columns={"departamento": "categoria"}))
            mx, mn = t.loc[t.pobreza_pct.idxmax()], t.loc[t.pobreza_pct.idxmin()]
            titulo = (f"{mx.categoria} ({mx.pobreza_pct:.1f} %) tiene {mx.pobreza_pct / mn.pobreza_pct:.1f} veces "
                      f"la pobreza de {mn.categoria} ({mn.pobreza_pct:.1f} %)")
            sub = ("Pobreza monetaria por departamento, Perú 2024 (% de personas). "
                   "Lima (15) y Callao (07) por separado.")
            f = barras(t, titulo, sub, INEI, figs / "pobreza_departamento_2024.png", nac_inei, horizontal=True)
        hechos.append((f, t[["categoria", "pobreza_pct"]].round(2)))

    for f, t in hechos:
        print(f"\n{f}\n{t.to_string(index=False)}")
    print(f"\nNacional: {nac_inei:.2f} % (método INEI) · {nac_pers:.2f} % (residentes, facpob07)")


if __name__ == "__main__":
    main()
