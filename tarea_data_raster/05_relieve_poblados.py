"""Paso 5 · Relieve y poblados alrededor de cada incendio en rojo o ámbar.

- Relieve: Copernicus DEM GLO-30 (Planetary Computer, raster 30 m), remuestreado a una rejilla de ~100 x 100.
- Poblados: centros poblados de GeoNames (Perú, clase P).
- Llegada estimada: la misma trayectoria hora a hora del paso 2. Un poblado se alcanza en la hora h
  si está a menos del radio del corredor (radio inicial + 25 % de lo avanzado) de algún punto
  de la trayectoria hasta esa hora.
"""
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import planetary_computer
import pystac_client
import rasterio
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.merge import merge

BASE = Path(__file__).parent
DATOS, RES = BASE / "datos", BASE / "resultados"
N = 110  # celdas por lado de la rejilla de relieve

inc = pd.read_csv(RES / "exposicion_incendios.csv")
inc = inc[~inc.semaforo.str.startswith("VERDE")].reset_index(drop=True)
pron = pd.read_csv(RES / "pronostico_72h.csv")
corr = gpd.read_file(RES / "corredores.geojson")

# Poblados GeoNames (clase P = lugares poblados)
cols = ["geonameid", "nombre", "ascii", "alt", "lat", "lon", "clase", "codigo", "pais", "cc2", "adm1", "adm2", "adm3",
        "adm4", "poblacion", "elev", "dem", "tz", "mod"]
geo = pd.read_csv(DATOS / "PE.txt", sep="\t", names=cols, usecols=["geonameid", "nombre", "lat", "lon", "clase", "codigo", "poblacion"],
                  dtype={"poblacion": "Int64"}, quoting=3)
geo = geo[geo.clase == "P"].drop(columns="clase")

utm = Transformer.from_crs(4326, 32718, always_xy=True)
cat = pystac_client.Client.open("https://planetarycomputer.microsoft.com/api/stac/v1", modifier=planetary_computer.sign_inplace)
wp = rasterio.open(DATOS / "per_ppp_2020_1km.tif")

relieve, poblados = [], []
for _, f in inc.iterrows():
    iid = int(f.incendio_id)
    x0, y0, x1, y1 = corr[(corr.incendio_id == iid) & (corr.horizonte_h == 72)].total_bounds
    # Caja cuadrada en km, al menos 16 km de lado, con 35 % de margen
    kx = np.cos(np.radians(f.lat))
    lado = max((x1 - x0) * kx, y1 - y0, 16 / 111.32) * 1.35
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    caja = (cx - lado / 2 / kx, cy - lado / 2, cx + lado / 2 / kx, cy + lado / 2)

    # Relieve
    items = cat.search(collections=["cop-dem-glo-30"], bbox=caja).item_collection()
    fuentes = [rasterio.open(it.assets["data"].href) for it in items]
    res = ((caja[2] - caja[0]) / N, (caja[3] - caja[1]) / N)
    mosaico, _ = merge(fuentes, bounds=caja, res=res, resampling=Resampling.bilinear, nodata=-9999)
    for s in fuentes:
        s.close()
    elev = mosaico[0][:N, :N]
    relieve.append({"incendio_id": iid, "oeste": round(caja[0], 5), "norte": round(caja[3], 5),
                    "dlon": round(res[0], 7), "dlat": round(res[1], 7), "filas": elev.shape[0], "columnas": elev.shape[1],
                    "elev_m": [int(v) if v > -9000 else None for v in elev.ravel()]})

    # Trayectoria hora a hora (igual que en el paso 2)
    p = pron[pron.incendio_id == iid].sort_values("h")
    seco = ((70 - p.relative_humidity_2m) / 40).clip(0, 1)
    ros = np.where(p.precipitation >= 0.5, 0, 0.10 * p.wind_speed_10m * seco)
    rumbo = np.radians((p.wind_direction_10m + 180) % 360)
    fx, fy = utm.transform(f.lon, f.lat)
    tx = fx + np.concatenate([[0], np.cumsum(ros * 1000 * np.sin(rumbo))])
    ty = fy + np.concatenate([[0], np.cumsum(ros * 1000 * np.cos(rumbo))])
    avance = np.concatenate([[0], np.cumsum(ros)])
    radio = max(1000, np.sqrt(f.huella_ha * 1e4 / np.pi) + 375) + 0.25 * avance * 1000

    cerca = geo[geo.lon.between(caja[0], caja[2]) & geo.lat.between(caja[1], caja[3])].copy()
    if cerca.empty:
        continue
    gx, gy = utm.transform(cerca.lon.to_numpy(), cerca.lat.to_numpy())
    dist_tray = np.hypot(gx[:, None] - tx[None, :], gy[:, None] - ty[None, :])  # poblado x hora
    alcanzado = np.minimum.accumulate(dist_tray, axis=1) <= radio[None, :]
    cerca["llegada_h"] = np.where(alcanzado.any(1), alcanzado.argmax(1), np.nan)
    cerca["distancia_km"] = (np.hypot(gx - fx, gy - fy) / 1000).round(1)
    cerca["rumbo"] = (np.degrees(np.arctan2(gx - fx, gy - fy)) % 360).round(0)
    cerca["personas_km2"] = [max(0.0, float(v[0])) for v in wp.sample(zip(cerca.lon, cerca.lat))]
    cerca["incendio_id"] = iid
    poblados.append(cerca)

pob = pd.concat(poblados, ignore_index=True)
pob["personas_km2"] = pob.personas_km2.round(0).astype(int)
pob = pob.sort_values(["incendio_id", "llegada_h", "distancia_km"], na_position="last")
pob.to_csv(RES / "poblados_cercanos.csv", index=False)
json.dump(relieve, open(RES / "relieve.json", "w"), separators=(",", ":"))

res = pob.groupby("incendio_id").agg(poblados=("nombre", "size"), alcanzados_72h=("llegada_h", "count"),
                                     primera_llegada_h=("llegada_h", "min"))
print(res.merge(inc.set_index("incendio_id")[["distrito", "semaforo"]], left_index=True, right_index=True).to_string())
print(pob[pob.incendio_id == inc.incendio_id.iloc[0]].head(12)[["nombre", "distancia_km", "rumbo", "llegada_h", "personas_km2"]].to_string())
