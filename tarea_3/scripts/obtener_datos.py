"""Descarga los módulos 500 (Empleo e ingresos) y 400 (Salud) de la ENAHO anual, 2015-2025, desde el portal de microdatos del INEI.

El módulo 400 se usa para saber quién paga el seguro de salud (criterio de informalidad de los asalariados).

Fuente: https://proyectos.inei.gob.pe/microdatos/  (ENAHO Metodología ACTUALIZADA, periodo anual)
Cada año tiene un código de encuesta en el portal; los archivos son <código>-Modulo05.zip y <código>-Modulo04.zip (formato STATA).

Uso:  python scripts/obtener_datos.py
Los .zip quedan en datos/originales/ (no se suben a GitHub por su tamaño; este script los vuelve a bajar).
"""
from pathlib import Path
import shutil
import ssl
import urllib.request
import zipfile

import certifi  # certificados raíz (el Python de uv no trae los del sistema)

CODIGOS = {  # año -> código de la ENAHO anual en el portal del INEI
    2015: 498, 2016: 546, 2017: 603, 2018: 634, 2019: 687,
    2020: 737, 2021: 759, 2022: 784, 2023: 906, 2024: 966, 2025: 1031,
}
URL = "https://proyectos.inei.gob.pe/iinei/srienaho/descarga/STATA/{c}-Modulo{m}.zip"
MODULOS = ("05", "04")
RAIZ = Path(__file__).resolve().parents[1]
DEST = RAIZ / "datos" / "originales"


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    ctx = ssl.create_default_context(cafile=certifi.where())
    for anio, c in CODIGOS.items():
        for m in MODULOS:
            zpath = DEST / f"enaho_{anio}_{c}_modulo{m}.zip"
            if not zpath.exists():
                print(f"Descargando {anio} módulo {m} (código {c})…", flush=True)
                with urllib.request.urlopen(URL.format(c=c, m=m), context=ctx) as r, open(zpath, "wb") as f:
                    shutil.copyfileobj(r, f)
            with zipfile.ZipFile(zpath) as z:
                dtas = [Path(n).name for n in z.namelist() if n.lower().endswith(".dta")]
            print(f"{anio} módulo {m}: {zpath.stat().st_size/1e6:.1f} MB · {dtas}")

if __name__ == "__main__":
    main()
