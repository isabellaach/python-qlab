"""Paso 4 · Mapa estático para el README: corredores de 72 h por semáforo + zoom al incendio en rojo."""
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd

BASE = Path(__file__).parent
RES = BASE / "resultados"
deps = gpd.read_file(BASE / "datos" / "peru_departamental_simple.geojson")
inc = pd.read_csv(RES / "exposicion_incendios.csv")
corr = gpd.read_file(RES / "corredores.geojson").merge(inc[["incendio_id", "semaforo"]], on="incendio_id")
COLOR = {"R": "#d7301f", "Á": "#fd8d3c", "V": "#41ab5d"}
rojo = inc[inc.semaforo.str[0] == "R"].iloc[0]

fig, ax = plt.subplots(1, 2, figsize=(13, 7.5), gridspec_kw={"width_ratios": [1.1, 1]})
for a in ax:
    deps.plot(ax=a, color="#f4f1ec", edgecolor="#9a9a9a", linewidth=0.5)
for H, alfa in [(72, 0.25), (24, 0.55)]:
    c = corr[corr.horizonte_h == H]
    for a in ax:
        c.plot(ax=a, color=c.semaforo.str[0].map(COLOR), alpha=alfa, edgecolor="none")
for a in ax:
    a.scatter(inc.lon, inc.lat, s=6, c=inc.semaforo.str[0].map(COLOR), edgecolor="k", linewidths=0.2, zorder=3)
    a.set_xticks([]); a.set_yticks([]); a.set_xlabel(""); a.set_ylabel("")
ax[0].set_title(f"{len(inc)} incendios activos · corredores 24 h (oscuro) y 72 h (claro)", fontsize=10)
ax[1].set_xlim(rojo.lon - 0.45, rojo.lon + 0.45); ax[1].set_ylim(rojo.lat - 0.45, rojo.lat + 0.45)
ax[1].set_title(f"ROJO: {rojo.distrito.title()} ({rojo.departamento.title()}) · {rojo.personas_24h:,.0f} personas en 24 h", fontsize=10)
for l, col in [("Rojo · preparar evacuación", "R"), ("Ámbar · alerta 24–72 h", "Á"), ("Verde · vigilar", "V")]:
    ax[0].scatter([], [], c=COLOR[col], label=l)
ax[0].legend(loc="lower left", fontsize=8)
fig.suptitle("¿A quién alcanzará el fuego? Viento de Open-Meteo + población WorldPop", fontsize=12)
fig.tight_layout()
fig.savefig(RES / "mapa_corredores.png", dpi=120)
