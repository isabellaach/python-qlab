"""Paso 3 · Área quemada con dNBR (Sentinel-2 L2A, Planetary Computer) para un incendio.

Uso: python 03_dnbr.py <incendio_id>
- Busca imágenes del 15 set al día de hoy y mide el % de nubes DENTRO de la zona (capa SCL).
- Pre: la más clara antes del primer foco. Post: la más clara después del primer foco.
- NBR = (B08 - B12) / (B08 + B12); dNBR = NBR_pre - NBR_post.
- Quemado = dNBR >= 0,27 (umbral usado por el profesor), sembrado: solo a <= 1,5 km de un foco VIIRS.
"""
import json
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import planetary_computer
import pystac_client
import rasterio
from rasterio.features import rasterize
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds

BASE = Path(__file__).parent
RES = BASE / "resultados"
iid = int(sys.argv[1])
inc = pd.read_csv(RES / "exposicion_incendios.csv").set_index("incendio_id").loc[iid]
focos = pd.read_csv(RES / "focos_peru.csv", parse_dates=["fecha_utc"])
focos = focos[focos.incendio_id == iid]
inicio = focos.fecha_utc.min()

# Zona de estudio: caja alrededor de los focos + 3 km
gf = gpd.GeoDataFrame(focos, geometry=gpd.points_from_xy(focos.longitude, focos.latitude), crs=4326)
caja = gf.to_crs(32718).total_bounds + np.array([-3000, -3000, 3000, 3000])
caja_ll = transform_bounds(32718, 4326, *caja)

cat = pystac_client.Client.open("https://planetarycomputer.microsoft.com/api/stac/v1", modifier=planetary_computer.sign_inplace)
items = cat.search(collections=["sentinel-2-l2a"], bbox=caja_ll, datetime="2026-09-15/2026-10-22",
                   query={"eo:cloud_cover": {"lt": 90}}).item_collection()


def leer(item, banda, ref=None):
    with rasterio.open(item.assets[banda].href) as src:
        b = transform_bounds(4326, src.crs, *caja_ll)
        win = from_bounds(*b, src.transform)
        shape = ref if ref else (int(round(win.height)), int(round(win.width)))
        arr = src.read(1, window=win, out_shape=shape, boundless=True, fill_value=0, resampling=rasterio.enums.Resampling.nearest)
        return arr, src.window_transform(win), src.crs, shape


# % de nubes en la zona con SCL (20 m): 3 sombra, 8-9 nube, 10 cirro; 0 sin dato
escenas = []
for it in items:
    scl, *_ = leer(it, "SCL")
    valido = scl > 0
    if valido.mean() < 0.9:
        continue
    nubes = np.isin(scl, [3, 8, 9, 10]).sum() / valido.sum() * 100
    escenas.append({"item": it, "fecha": it.datetime, "nubes_zona": round(nubes, 1), "nubes_escena": round(it.properties["eo:cloud_cover"], 1)})
esc = pd.DataFrame(escenas).sort_values("fecha")
print(esc[["fecha", "nubes_zona", "nubes_escena"]].to_string())

pre = esc[esc.fecha < inicio - pd.Timedelta(days=1)].sort_values(["nubes_zona", "fecha"], ascending=[True, False]).iloc[0]
post_c = esc[esc.fecha > inicio]
post = post_c.sort_values(["nubes_zona", "fecha"], ascending=[True, False]).iloc[0]
print(f"Primer foco: {inicio:%Y-%m-%d %H:%M} UTC · PRE {pre.fecha:%Y-%m-%d} ({pre.nubes_zona} % nubes) · POST {post.fecha:%Y-%m-%d} ({post.nubes_zona} % nubes)")


def nbr(item):
    b12, tr, crs, shape = leer(item, "B12")
    b08, *_ = leer(item, "B08", ref=shape)
    scl, *_ = leer(item, "SCL", ref=shape)
    # Desde la línea base 04.00 los niveles digitales llevan +1000
    b08, b12 = b08.astype("float32") - 1000, b12.astype("float32") - 1000
    n = (b08 - b12) / (b08 + b12 + 1e-6)
    malo = np.isin(scl, [0, 1, 3, 8, 9, 10]) | (b08 <= 0)
    return np.where(malo, np.nan, n), tr, crs, shape


nbr_pre, tr, crs, shape = nbr(pre["item"])
nbr_post, *_ = nbr(post["item"])
dnbr = nbr_pre - nbr_post

# Semilla VIIRS: solo píxeles a <= 1,5 km de un foco del incendio
semilla = rasterize([(g, 1) for g in gf.to_crs(crs).buffer(1500)], out_shape=shape, transform=tr, fill=0).astype(bool)
pix_ha = abs(tr.a * tr.e) / 1e4
clases = [(0.10, 0.27, "baja"), (0.27, 0.44, "moderada-baja"), (0.44, 0.66, "moderada-alta"), (0.66, 9, "alta")]
filas = []
for lo, hi, nom in clases:
    m = semilla & (dnbr >= lo) & (dnbr < hi)
    filas.append({"severidad": nom, "dnbr_desde": lo, "hectareas": round(m.sum() * pix_ha, 1)})
tabla = pd.DataFrame(filas)
quemado_ha = tabla[tabla.dnbr_desde >= 0.27].hectareas.sum()
cobertura_valida = np.isfinite(dnbr[semilla]).mean() * 100
print(tabla.to_string())
print(f"Quemado (dNBR >= 0,27, sembrado VIIRS): {quemado_ha:,.0f} ha · píxeles válidos en la zona: {cobertura_valida:.0f} %")

# Mapa
fig, ax = plt.subplots(1, 3, figsize=(15, 5.2))
ext = (tr.c, tr.c + tr.a * shape[1], tr.f + tr.e * shape[0], tr.f)
fx, fy = gf.to_crs(crs).geometry.x, gf.to_crs(crs).geometry.y
for a, arr, tit in [(ax[0], nbr_pre, f"NBR antes · {pre.fecha:%d %b} ({pre.nubes_zona:.0f} % nubes)"),
                    (ax[1], nbr_post, f"NBR después · {post.fecha:%d %b} ({post.nubes_zona:.0f} % nubes)")]:
    a.imshow(arr, cmap="RdYlGn", vmin=-0.3, vmax=0.7, extent=ext)
    a.set_title(tit, fontsize=10)
im = ax[2].imshow(np.where(semilla, dnbr, np.nan), cmap="inferno_r", vmin=0, vmax=0.8, extent=ext)
ax[2].scatter(fx, fy, s=8, c="cyan", edgecolor="k", linewidths=0.3, label="focos VIIRS")
ax[2].set_title(f"dNBR · quemado ≥ 0,27: {quemado_ha:,.0f} ha", fontsize=10)
ax[2].legend(loc="lower right", fontsize=8)
fig.colorbar(im, ax=ax[2], shrink=0.8, label="dNBR")
for a in ax:
    a.set_xticks([]); a.set_yticks([])
fig.suptitle(f"Incendio {iid} · {inc.distrito.title()}, {inc.provincia.title()}, {inc.departamento.title()} · Sentinel-2 L2A", fontsize=12)
fig.tight_layout()
fig.savefig(RES / f"dnbr_{iid}.png", dpi=130)

json.dump({
    "incendio_id": iid, "distrito": inc.distrito, "provincia": inc.provincia, "departamento": inc.departamento,
    "primer_foco_utc": f"{inicio:%Y-%m-%d %H:%M}", "pre": f"{pre.fecha:%Y-%m-%d}", "pre_nubes_zona": pre.nubes_zona,
    "post": f"{post.fecha:%Y-%m-%d}", "post_nubes_zona": post.nubes_zona, "quemado_ha": round(quemado_ha, 1),
    "huella_viirs_ha": inc.huella_ha, "pixeles_validos_pct": round(cobertura_valida, 1), "severidad": filas,
}, open(RES / f"dnbr_{iid}.json", "w"), ensure_ascii=False, indent=2)
