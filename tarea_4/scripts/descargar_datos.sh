#!/usr/bin/env bash
# Baja los datos obligatorios de la Tarea 4 a datos/ (ignorada por git).
#   bash scripts/descargar_datos.sh
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p datos
INEI=https://proyectos.inei.gob.pe/iinei/srienaho/descarga/STATA
for m in 34 02; do                       # 966 = código de la ENAHO 2024 en el portal del INEI
  [ -f "datos/966-Modulo$m.zip" ] || curl -fL --retry 3 -o "datos/966-Modulo$m.zip" "$INEI/966-Modulo$m.zip"
done
GEO=https://raw.githubusercontent.com/d2cml-ai/Data-Science-Python/main/sessions/06-geoespacial/lab/Data/peru_departamental_simple.geojson
[ -f datos/peru_departamental_simple.geojson ] || curl -fL --retry 3 -o datos/peru_departamental_simple.geojson "$GEO"
ls -lh datos
