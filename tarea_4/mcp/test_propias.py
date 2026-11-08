"""Dos pruebas propias para graficar_serie, la herramienta agregada en la Tarea 4.

    uv run pytest -q          # junto con las 8 de la sesión 04 (test_server.py, sin cambios): 10 passed

Usan el mismo cliente en memoria que test_server.py y datos reales del BCRP.
"""
import pytest
from fastmcp.exceptions import ToolError

from server import RAIZ
from test_server import llamar


def test_graficar_serie_guarda_png_con_fuente_y_cifras():
    r = llamar("graficar_serie", codigo="PN01273PM", desde="2025-12", hasta="2026-09",
               comparar_con="PN01271PM", lineas_referencia=[1, 3], archivo="prueba_graficar_serie.png")
    ruta = RAIZ / r["archivo"]
    try:
        assert ruta.exists() and ruta.stat().st_size > 20_000           # un PNG real, no un archivo vacío
        assert ruta.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
        assert [s["codigo"] for s in r["series"]] == ["PN01273PM", "PN01271PM"]
        # las cifras del gráfico son las mismas que da resumen, con la cifra oficial de la sesión 04
        assert r["series"][0]["ultimo"] == {"periodo": "2026-09", "valor": pytest.approx(4.55, abs=0.01)}
        assert all(f.startswith("https://estadisticas.bcrp.gob.pe") for f in r["fuente"])
    finally:
        ruta.unlink(missing_ok=True)


def test_graficar_serie_falla_con_mensaje_claro():
    with pytest.raises(ToolError, match="XX999"):                      # código inexistente: no grafica nada
        llamar("graficar_serie", codigo="PN01273PM", desde="2025-01", hasta="2025-06", comparar_con="XX999")
    with pytest.raises(ToolError, match="no válida"):                   # fecha mal escrita: lo dice
        llamar("graficar_serie", codigo="PN01273PM", desde="enero 2025", hasta="2025-06")
