---
name: mapeando-enaho
description: Hace un mapa coroplético de la pobreza monetaria por departamento del Perú con la ENAHO 2024 del INEI, unido por código territorial (ubigeo[:2] = FIRST_IDDP), con los 25 departamentos y Lima y Callao separados, y lo compara con la referencia oficial. Úsala cuando pidan un mapa, un coroplético o la distribución territorial o regional de la pobreza en el Perú.
---
# Mapear la pobreza de la ENAHO 2024 por departamento

Trabaja desde la raíz del proyecto (`tarea_4/`).

1. Si no existe `salidas/hogares_2024.parquet`, usa primero la skill `limpiando-enaho` y sigue solo si su
   `validacion.txt` dice `VÁLIDO`.
2. Si no existe `datos/peru_departamental_simple.geojson`, corre `bash scripts/descargar_datos.sh`.
3. Corre exactamente:
   ```bash
   uv run ${CLAUDE_SKILL_DIR}/scripts/mapear.py
   ```
4. Revisa lo que imprime: deben ser **25/25 departamentos con dato** y la comparación con
   [la referencia de la Sesión 16](referencia_pobreza_departamento_2024.csv) (± 0.1 pp). Si la unión falla o un
   departamento difiere más de 0.1 pp, dilo y no lo corrijas a mano.
5. Responde con la ruta `mapas/pobreza_departamento_2024.png`, el departamento con más y con menos pobreza y la
   fuente «INEI, ENAHO 2024». Las cifras de cada departamento están en `salidas/comparacion_mapa_referencia.csv`.

Reglas del mapa (ya están en el script; respétalas si te piden cambios):
- Une por código, nunca por nombre: «APURIMAC» no es «Apurímac». `ccdd` y `FIRST_IDDP` son texto de 2 dígitos.
- Lima (15) y Callao (07) van separados; 25 unidades, ninguna sin dato.
- Un solo color de claro a oscuro, desde 0; nunca arcoíris. Leyenda con la unidad: % de personas.
- Ponderación del INEI: sumaria con factor07 × mieperho.
