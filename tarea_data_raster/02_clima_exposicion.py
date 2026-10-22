"""Paso 2 · ¿A quién alcanzará el fuego en 24, 48 y 72 h?

1. Limpia fuentes fijas: focos persistentes (>= 4 de 7 días en el mismo lugar) o
   sobre suelo desnudo / urbano / agua según ESA WorldCover (raster, 10 m).
2. Pronóstico horario de Open-Meteo (viento, humedad, lluvia) para cada incendio activo.
3. Corredor de propagación: el fuego avanza a favor del viento a
   ROS = 10 % de la velocidad del viento (regla de Cruz y Alexander, 2019),
   frenado por la humedad (0 si HR >= 70 %, completo si HR <= 30 %) y anulado si llueve.
4. Personas dentro del corredor con WorldPop 2020 (raster, 1 km) -> semáforo.
"""
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import planetary_computer
import pystac_client
import rasterio
import requests
from rasterio.mask import mask
from shapely.geometry import LineString, Point

BASE = Path(__file__).parent
DATOS, RES = BASE / "datos", BASE / "resultados"
UTM = 32718  # UTM 18S, metros
HORIZONTES = [24, 48, 72]
UMBRAL_ROJO, UMBRAL_AMBAR = 500, 500  # personas

inc = pd.read_csv(RES / "incendios.csv", parse_dates=["primer_foco", "ultimo_foco"])
focos = pd.read_csv(RES / "focos_peru.csv", parse_dates=["fecha_utc"])
inc = inc[inc.activo].copy()

# ---------- 1 · Fuentes fijas ----------
dias = focos.groupby("incendio_id")["acq_date"].nunique().rename("dias_con_foco")
inc = inc.merge(dias, left_on="incendio_id", right_index=True)

catalogo = pystac_client.Client.open(
    "https://planetarycomputer.microsoft.com/api/stac/v1", modifier=planetary_computer.sign_inplace
)
CLASES_NO_COMBUSTIBLE = {50: "urbano", 60: "suelo desnudo", 70: "nieve", 80: "agua"}
fa = focos[focos.incendio_id.isin(inc.incendio_id)].copy()
fa["worldcover"] = 0
for item in catalogo.search(collections=["esa-worldcover"], intersects={
    "type": "Polygon", "coordinates": [[[-81.5, -18.5], [-68.5, -18.5], [-68.5, 0.1], [-81.5, 0.1], [-81.5, -18.5]]]
}).items():
    if item.properties.get("esa_worldcover:product_version") not in (None, "2.0.0"):
        continue
    xmin, ymin, xmax, ymax = item.bbox
    sel = fa.longitude.between(xmin, xmax) & fa.latitude.between(ymin, ymax) & (fa.worldcover == 0)
    if sel.any():
        with rasterio.open(item.assets["map"].href) as src:
            fa.loc[sel, "worldcover"] = [v[0] for v in src.sample(zip(fa.loc[sel, "longitude"], fa.loc[sel, "latitude"]))]
wc = fa.groupby("incendio_id")["worldcover"].agg(lambda s: s.isin(CLASES_NO_COMBUSTIBLE).mean()).rename("frac_no_combustible")
cob = fa.groupby("incendio_id")["worldcover"].agg(lambda s: s.mode().iat[0]).rename("cobertura_moda")
inc = inc.merge(wc, left_on="incendio_id", right_index=True).merge(cob, left_on="incendio_id", right_index=True)
NOMBRES_WC = {10: "bosque", 20: "matorral", 30: "pastizal", 40: "cultivo", 50: "urbano", 60: "suelo desnudo",
              70: "nieve", 80: "agua", 90: "humedal", 95: "manglar", 100: "musgo/liquen"}
inc["cobertura"] = inc.cobertura_moda.map(NOMBRES_WC).fillna("sin dato")
inc["fuente_fija"] = (inc.dias_con_foco >= 4) | (inc.frac_no_combustible >= 0.5)
print(f"Activos: {len(inc)} · descartados como fuente fija o no combustible: {inc.fuente_fija.sum()}")
print(inc[inc.fuente_fija][["distrito", "departamento", "dias_con_foco", "frac_no_combustible", "cobertura"]].to_string())
inc = inc[~inc.fuente_fija].reset_index(drop=True)

# ---------- 2 · Pronóstico Open-Meteo (72 h, horario) ----------
pron = []
for k in range(0, len(inc), 50):
    lote = inc.iloc[k:k + 50]
    r = requests.get("https://api.open-meteo.com/v1/forecast", params={
        "latitude": ",".join(f"{x:.4f}" for x in lote.lat), "longitude": ",".join(f"{x:.4f}" for x in lote.lon),
        "hourly": "wind_speed_10m,wind_direction_10m,relative_humidity_2m,precipitation,temperature_2m",
        "forecast_days": 4, "timezone": "America/Lima",
    }, timeout=60)
    r.raise_for_status()
    js = r.json()
    js = js if isinstance(js, list) else [js]
    for iid, j in zip(lote.incendio_id, js):
        h = pd.DataFrame(j["hourly"])
        h["incendio_id"] = iid
        pron.append(h)
pron = pd.concat(pron, ignore_index=True)
pron["time"] = pd.to_datetime(pron["time"])
ahora = pd.Timestamp.now(tz="America/Lima").tz_localize(None).floor("h")
pron = pron[(pron.time >= ahora) & (pron.time < ahora + pd.Timedelta(hours=72))].copy()
pron["h"] = ((pron.time - ahora) / pd.Timedelta(hours=1)).astype(int)
pron.to_csv(RES / "pronostico_72h.csv", index=False)

# ---------- 3 · Corredor de propagación ----------
seco = ((70 - pron.relative_humidity_2m) / 40).clip(0, 1)
pron["ros_kmh"] = np.where(pron.precipitation >= 0.5, 0, 0.10 * pron.wind_speed_10m * seco)
rumbo = np.radians((pron.wind_direction_10m + 180) % 360)  # el viento VIENE de; el fuego va hacia el lado opuesto
pron["dx_m"] = pron.ros_kmh * 1000 * np.sin(rumbo)
pron["dy_m"] = pron.ros_kmh * 1000 * np.cos(rumbo)

pts = gpd.GeoSeries(gpd.points_from_xy(inc.lon, inc.lat), crs=4326).to_crs(UTM)
corredores, filas = [], []
for (_, f), p0 in zip(inc.iterrows(), pts):
    p = pron[pron.incendio_id == f.incendio_id].sort_values("h")
    x = p0.x + np.concatenate([[0], p.dx_m.cumsum()])
    y = p0.y + np.concatenate([[0], p.dy_m.cumsum()])
    radio_inicial = max(1000, np.sqrt(f.huella_ha * 1e4 / np.pi) + 375)
    fila = {"incendio_id": f.incendio_id}
    for H in HORIZONTES:
        n = min(H, len(p))
        avance = p.ros_kmh.iloc[:n].sum()
        tray = LineString(list(zip(x[:n + 1], y[:n + 1]))) if avance > 0.05 else Point(x[0], y[0])
        poly = tray.buffer(radio_inicial + 0.25 * avance * 1000).union(p0.buffer(radio_inicial))
        corredores.append({"incendio_id": f.incendio_id, "horizonte_h": H, "avance_km": round(avance, 1), "geometry": poly})
        fila[f"avance_{H}h_km"] = round(avance, 1)
    seg = p.iloc[:24]
    fila["viento_max_24h_kmh"] = round(seg.wind_speed_10m.max(), 0)
    fila["hr_min_24h"] = round(seg.relative_humidity_2m.min(), 0)
    fila["lluvia_72h_mm"] = round(p.precipitation.sum(), 1)
    fila["rumbo_fuego_24h"] = round(np.degrees(np.arctan2(seg.dx_m.sum(), seg.dy_m.sum())) % 360, 0)
    filas.append(fila)
corr = gpd.GeoDataFrame(corredores, crs=UTM)
inc = inc.merge(pd.DataFrame(filas), on="incendio_id")

# Círculo estático de 5 km (lo que usa el tablero del profesor), para comparar
circ = gpd.GeoDataFrame({"incendio_id": inc.incendio_id, "horizonte_h": 0}, geometry=pts.buffer(5000).values, crs=UTM)

# ---------- 4 · Población (WorldPop 2020, 1 km) ----------
with rasterio.open(DATOS / "per_ppp_2020_1km.tif") as src:
    def personas(geom):
        try:
            arr, _ = mask(src, [geom], crop=True, all_touched=False)
        except ValueError:
            return 0.0
        arr = arr[0]
        return float(arr[arr > 0].sum())

    corr4326 = corr.to_crs(4326)
    corr["personas"] = [personas(g) for g in corr4326.geometry]
    inc["personas_5km_circulo"] = [personas(g) for g in circ.to_crs(4326).geometry]

    for H in HORIZONTES:
        inc = inc.merge(corr[corr.horizonte_h == H][["incendio_id", "personas"]].rename(columns={"personas": f"personas_{H}h"}),
                        on="incendio_id")

    # Un foco de calor no es un incendio: para pedir evacuación exigimos un fuego confirmado
    # (>= 3 focos en 24 h o huella >= 50 ha). Si no, como máximo ÁMBAR "verificar en campo".
    inc["confirmado"] = (inc.focos_24h >= 3) | (inc.huella_ha >= 50)

    def semaforo(r):
        if r.personas_24h >= UMBRAL_ROJO and r.confirmado:
            return "ROJO · preparar evacuación (0–24 h)"
        if r.personas_72h >= UMBRAL_AMBAR or r.personas_24h >= UMBRAL_ROJO:
            return "ÁMBAR · alerta temprana (24–72 h)"
        return "VERDE · vigilar"

    inc["semaforo"] = inc.apply(semaforo, axis=1)

    # Distritos dentro del corredor de 72 h de los incendios en rojo/ámbar
    dist = gpd.read_file(DATOS / "peru_distrital_simple.geojson")[["NOMBDIST", "NOMBPROV", "NOMBDEP", "geometry"]]
    alerta = inc[~inc.semaforo.str.startswith("VERDE")].incendio_id
    c72 = corr4326[(corr4326.horizonte_h == 72) & corr4326.incendio_id.isin(alerta)]
    cruce = gpd.overlay(c72, dist, how="intersection", keep_geom_type=True)
    cruce["personas"] = [personas(g) for g in cruce.geometry]
    cruce = cruce.merge(inc[["incendio_id", "semaforo"]], on="incendio_id")
    cruce = cruce[cruce.personas >= 1].sort_values("personas", ascending=False)
    cruce.drop(columns="geometry").to_csv(RES / "distritos_en_alerta.csv", index=False)

orden = inc.semaforo.str[0].map({"R": 0, "Á": 1, "V": 2})
inc = inc.assign(_o=orden).sort_values(["_o", "personas_72h"], ascending=[True, False]).drop(columns="_o")
inc.to_csv(RES / "exposicion_incendios.csv", index=False)
corr4326.to_file(RES / "corredores.geojson", driver="GeoJSON")

print(f"\nPronóstico desde {ahora:%Y-%m-%d %H:%M} (hora de Lima) hasta +72 h")
print(inc.semaforo.value_counts().to_string())
print(f"Personas en corredores 24 h: {inc.personas_24h.sum():,.0f} · 72 h: {inc.personas_72h.sum():,.0f} · "
      f"círculo fijo 5 km: {inc.personas_5km_circulo.sum():,.0f}")
cols = ["incendio_id", "distrito", "departamento", "cobertura", "huella_ha", "focos_24h", "avance_24h_km", "avance_72h_km",
        "viento_max_24h_kmh", "hr_min_24h", "lluvia_72h_mm", "personas_24h", "personas_72h", "personas_5km_circulo", "semaforo"]
print(inc[cols].head(20).round(0).to_string())
print("\nDistritos en alerta:\n", cruce[["NOMBDIST", "NOMBPROV", "NOMBDEP", "incendio_id", "personas", "semaforo"]].head(15).round(0).to_string())
