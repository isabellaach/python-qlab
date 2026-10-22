"""Paso 6 · Relieve sombreado del Perú para el mapa nacional del sitio web.

Copernicus DEM GLO-90 (Planetary Computer) remuestreado a ~2 km, recortado al contorno del Perú
y convertido en una capa PNG semitransparente (sombras oscuras, laderas iluminadas claras).
"""
import base64
import io
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import planetary_computer
import pystac_client
import rasterio
from PIL import Image
from rasterio.enums import Resampling
from rasterio.features import geometry_mask
from rasterio.merge import merge
from rasterio.transform import from_bounds

BASE = Path(__file__).parent
RES = BASE / "resultados"
CAJA = (-81.5, -18.5, -68.4, 0.2)  # oeste, sur, este, norte (la misma del mapa del sitio)
PASO = 0.018  # grados (~2 km)

peru = gpd.read_file(BASE / "datos" / "peru_departamental_simple.geojson").union_all()
cat = pystac_client.Client.open("https://planetarycomputer.microsoft.com/api/stac/v1", modifier=planetary_computer.sign_inplace)
items = cat.search(collections=["cop-dem-glo-90"], intersects=peru.envelope.__geo_interface__).item_collection()
print(f"Teselas DEM: {len(items)}")
fuentes = [rasterio.open(it.assets["data"].href) for it in items]
dem, tr = merge(fuentes, bounds=CAJA, res=(PASO, PASO), resampling=Resampling.average, nodata=-9999)
dem = dem[0].astype("float32")
dem[dem < -500] = np.nan
alto, ancho = dem.shape

# Sombreado (luz del noroeste, 45°), exageración vertical x3 por el tamaño de celda
lat = CAJA[3] - (np.arange(alto) + 0.5) * PASO
dx = PASO * 111320 * np.cos(np.radians(lat))[:, None]
dy = PASO * 110540
z = np.nan_to_num(dem, nan=0.0)
gy, gx = np.gradient(z)
gx, gy = gx / dx * 3, -gy / dy * 3  # filas crecen hacia el sur
L = np.array([-0.5, 0.5, np.sqrt(0.5)])
hs = (-gx * L[0] - gy * L[1] + L[2]) / np.sqrt(gx**2 + gy**2 + 1)
d = hs - L[2]  # <0 sombra, >0 luz

# Capa RGBA: sombras en tinta oscura, luces en blanco; tinte leve por altitud
alt = np.clip(np.nan_to_num(dem, nan=0) / 5500, 0, 1)
rgba = np.zeros((alto, ancho, 4), dtype="float32")
sombra = d < 0
rgba[sombra, :3] = [20, 26, 30]
rgba[sombra, 3] = np.clip(-d[sombra] * 1.6, 0, 0.75) * 255
rgba[~sombra, :3] = [255, 255, 255]
rgba[~sombra, 3] = np.clip(d[~sombra] * 1.4, 0, 0.55) * 255
rgba[..., 3] = np.clip(rgba[..., 3] + alt * 40, 0, 255)

dentro = ~geometry_mask([peru.__geo_interface__], out_shape=(alto, ancho), transform=from_bounds(*CAJA, ancho, alto))
rgba[~dentro, 3] = 0
buf = io.BytesIO()
Image.fromarray(rgba.astype("uint8"), "RGBA").save(buf, format="PNG", optimize=True)
json.dump([{"oeste": CAJA[0], "sur": CAJA[1], "este": CAJA[2], "norte": CAJA[3], "ancho": ancho, "alto": alto,
            "png_base64": base64.b64encode(buf.getvalue()).decode()}], open(RES / "relieve_peru.json", "w"))
Image.fromarray(rgba.astype("uint8"), "RGBA").save(RES / "relieve_peru.png")
print(f"Rejilla {ancho} x {alto} · PNG {len(buf.getvalue()) / 1e6:.2f} MB · altitud máx {np.nanmax(dem):,.0f} m")
