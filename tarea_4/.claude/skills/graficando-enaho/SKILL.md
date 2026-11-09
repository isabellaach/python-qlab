---
name: graficando-enaho
description: Hace gráficos de barras de la pobreza monetaria de la ENAHO 2024 del INEI, ponderados y con título analítico, unidad y fuente; por área urbana y rural, sexo, sexo y área, grupo de edad o departamento. Úsala cuando pidan graficar, visualizar, comparar en un gráfico o hacer una figura de la pobreza del Perú, de la ENAHO o del INEI.
argument-hint: "[area | sexo | sexo_area | edad | departamento | todos]"
---
# Graficar la pobreza de la ENAHO 2024

Trabaja desde la raíz del proyecto (`tarea_4/`).

1. Si no existen `salidas/hogares_2024.parquet` y `salidas/personas_2024.parquet`, usa primero la skill
   `limpiando-enaho` y sigue solo si su `validacion.txt` dice `VÁLIDO`.
2. Elige el tipo según el pedido y corre exactamente:
   ```bash
   uv run ${CLAUDE_SKILL_DIR}/scripts/graficar.py --tipo $ARGUMENTS
   ```
   | Pedido | `--tipo` | Peso |
   |---|---|---|
   | urbano y rural, área | `area` | factor07 × mieperho (método INEI) |
   | hombres y mujeres, sexo | `sexo` (y `sexo_area` para ver la brecha dentro de cada área) | facpob07 |
   | edad, niños, jóvenes, adultos mayores | `edad` | facpob07 |
   | departamentos, regiones, ranking | `departamento` | factor07 × mieperho |
   | varios o un informe | `todos` | — |
   Sin argumento claro, usa `todos`.
3. El script imprime la tabla con las cifras: cítalas tal cual, con «INEI, ENAHO 2024», y nombra el PNG de `figuras/`.
4. Para un gráfico que el script no cubre, sigue las mismas reglas: estimación ponderada, barras desde cero en un
   solo color con el valor escrito, línea del promedio nacional, título que diga el hallazgo, subtítulo con periodo
   y unidad (% de personas), nota al pie con la fuente y el método, PNG a 200 dpi en `figuras/`.
5. Describe diferencias, no causas. Si dos grupos difieren en menos de 1 punto, di que son casi iguales.
