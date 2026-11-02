"""Captura imágenes del dashboard para el reel (Chrome sin ventana + recorte con Pillow).

Requiere el dashboard servido en local:  cd web && python -m http.server 8765
Uso:  python reel/capturas.py   → reel/recursos/img/*.png
"""
import json
import re
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

AQUI = Path(__file__).parent
WEB = AQUI.parent / "web"
OUT = AQUI / "recursos" / "img"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
URL = "http://localhost:8765/"
ESCALA = 2
ALTO_PAGINA = 5600

# nombre → (parámetros, selector CSS del elemento a recortar)
CAPTURAS = {
    "portada": ("", "header .hero"),
    "serie": ("", "#serie"),
    "grupos": ("?dim=educacion", "#grupos"),
    "estado": ("", "#estadoSerie"),
    "tablero": ("", "body"),
    **{f"mapa_{a}": (f"?anio={a}", "#map") for a in range(2015, 2026)},
}
SONDA = """<script>setTimeout(()=>{const e=document.querySelector(%s);const c=(%s.startsWith('#map')?e:(e.closest('.card')||e));
const r=c.getBoundingClientRect();document.title=JSON.stringify([r.left+scrollX,r.top+scrollY,r.width,r.height]);},3500)</script></body>"""


def chrome(*args):
    with tempfile.TemporaryDirectory() as perfil:
        return subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={perfil}",
                               f"--window-size=1440,{ALTO_PAGINA}", f"--force-device-scale-factor={ESCALA}",
                               "--virtual-time-budget=9000", *args], capture_output=True, text=True).stdout


def main():
    import sys
    solo = sys.argv[1:]  # opcional: prefijos de las capturas a rehacer (p. ej. mapa_)
    OUT.mkdir(parents=True, exist_ok=True)
    html = (WEB / "index.html").read_text(encoding="utf-8")
    sonda = WEB / "_sonda.html"
    try:
        for nombre, (params, selector) in CAPTURAS.items():
            if solo and not any(nombre.startswith(p) for p in solo):
                continue
            sonda.write_text(html.replace("</body>", SONDA % (json.dumps(selector), json.dumps(selector))), encoding="utf-8")
            dom = chrome("--dump-dom", URL + "_sonda.html" + params)
            x, y, w, h = json.loads(re.search(r"<title>(.*?)</title>", dom).group(1))
            png = OUT / f"_{nombre}.png"
            chrome(f"--screenshot={png}", URL + params)
            img = Image.open(png)
            if nombre == "tablero":
                caja = (0, 0, img.width, int(img.width * 1.25))
            else:
                pad = 8
                caja = tuple(int(v * ESCALA) for v in (x - pad, y - pad, x + w + pad, y + h + pad))
            img.crop(caja).save(OUT / f"{nombre}.png")
            png.unlink()
            print(nombre, caja)
    finally:
        sonda.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
