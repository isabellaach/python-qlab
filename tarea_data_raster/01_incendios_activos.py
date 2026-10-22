"""Paso 1 · Focos VIIRS (NASA FIRMS, últimos 7 días) -> incendios activos en el Perú.

Regla del profesor: focos a <= 1 km y <= 48 h entre sí forman un incendio;
un incendio está activo si tiene al menos un foco en las últimas 24 h.
"""
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

DATOS = Path(__file__).parent / "datos"
RES = Path(__file__).parent / "resultados"
RES.mkdir(exist_ok=True)

PIXEL_HA = 0.375 * 0.375 * 100  # un píxel VIIRS de 375 m = 14,06 ha
R_TIERRA_KM = 6371.0

# 1 · Leer los tres satélites VIIRS (S-NPP, NOAA-20, NOAA-21)
archivos = sorted(DATOS.glob("*_VIIRS_C2_South_America_7d.csv"))
focos = pd.concat([pd.read_csv(f) for f in archivos], ignore_index=True)
focos["fecha_utc"] = pd.to_datetime(
    focos["acq_date"] + " " + focos["acq_time"].astype(str).str.zfill(4), format="%Y-%m-%d %H%M", utc=True
)

# 2 · Quedarse con el Perú y descartar focos de baja confianza
focos = focos[focos["latitude"].between(-18.5, 0.1) & focos["longitude"].between(-81.5, -68.5)]
focos = focos[focos["confidence"] != "low"]
deps = gpd.read_file(DATOS / "peru_departamental_simple.geojson")[["NOMBDEP", "geometry"]]
dist = gpd.read_file(DATOS / "peru_distrital_simple.geojson")[["NOMBDIST", "NOMBPROV", "NOMBDEP", "geometry"]]
gfocos = gpd.GeoDataFrame(focos, geometry=gpd.points_from_xy(focos.longitude, focos.latitude), crs=4326)
gfocos = gpd.sjoin(gfocos, dist, predicate="within", how="inner").drop(columns="index_right").reset_index(drop=True)

# 3 · Agrupar: arista entre dos focos si están a <= 1 km y <= 48 h (componentes conexas)
coords = np.radians(gfocos[["latitude", "longitude"]].to_numpy())
vecinos = BallTree(coords, metric="haversine").query_radius(coords, r=1.0 / R_TIERRA_KM)
t = gfocos["fecha_utc"].astype("int64").to_numpy() / 3.6e12  # horas
padre = np.arange(len(gfocos))


def raiz(i):
    while padre[i] != i:
        padre[i] = padre[padre[i]]
        i = padre[i]
    return i


for i, vs in enumerate(vecinos):
    for j in vs:
        if j > i and abs(t[i] - t[j]) <= 48:
            padre[raiz(i)] = raiz(j)
gfocos["incendio_id"] = [raiz(i) for i in range(len(gfocos))]

# 4 · Resumir cada incendio
corte = gfocos["fecha_utc"].max()
gfocos["ultimas_24h"] = gfocos["fecha_utc"] >= corte - pd.Timedelta(hours=24)
# Huella: píxeles únicos de 375 m (aprox. 0,0034°) con fuego
gfocos["celda"] = (gfocos.latitude / 0.0034).round().astype(int).astype(str) + "_" + (
    gfocos.longitude / 0.0034
).round().astype(int).astype(str)

inc = gfocos.groupby("incendio_id").agg(
    lat=("latitude", "mean"),
    lon=("longitude", "mean"),
    focos=("latitude", "size"),
    focos_24h=("ultimas_24h", "sum"),
    frp_total_mw=("frp", "sum"),
    primer_foco=("fecha_utc", "min"),
    ultimo_foco=("fecha_utc", "max"),
    celdas=("celda", "nunique"),
    distrito=("NOMBDIST", lambda s: s.mode().iat[0]),
    provincia=("NOMBPROV", lambda s: s.mode().iat[0]),
    departamento=("NOMBDEP", lambda s: s.mode().iat[0]),
)
inc["huella_ha"] = (inc.pop("celdas") * PIXEL_HA).round(0)
inc["activo"] = inc["focos_24h"] > 0
inc = inc.sort_values("huella_ha", ascending=False).reset_index()

gfocos.drop(columns=["geometry", "celda"]).to_csv(RES / "focos_peru.csv", index=False)
inc.to_csv(RES / "incendios.csv", index=False)

act = inc[inc.activo]
print(f"Corte de datos: {corte:%Y-%m-%d %H:%M} UTC")
print(f"Focos en el Perú (7 d, confianza nominal/alta): {len(gfocos):,}")
print(f"Incendios: {len(inc):,} · activos (foco en 24 h): {len(act):,} · activos con huella >= 100 ha: {(act.huella_ha >= 100).sum()}")
print(act.head(15)[["incendio_id", "distrito", "provincia", "departamento", "focos", "focos_24h", "huella_ha", "frp_total_mw"]].to_string())
