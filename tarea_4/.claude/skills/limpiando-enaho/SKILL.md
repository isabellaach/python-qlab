---
name: limpiando-enaho
description: Limpia y valida los módulos 34 (sumaria) y 02 (miembros) de la ENAHO 2024 del INEI; une personas y hogares, filtra residentes habituales y calcula la pobreza monetaria ponderada por área, departamento, sexo y edad. Úsala cuando pidan limpiar, unir, procesar o validar la ENAHO, o una cifra de pobreza del Perú en 2024 (nacional, urbana, rural, extrema, de un departamento, por sexo o edad), o cuando otra skill necesite salidas/personas_2024.parquet.
argument-hint: "[año: 2024]"
---
# Limpiar la ENAHO 2024

Trabaja desde la raíz del proyecto (`tarea_4/`). No reescribas el pipeline: corre el script tal cual.

1. Revisa que existan `datos/966-Modulo34.zip` y `datos/966-Modulo02.zip`. Si faltan, corre
   `bash scripts/descargar_datos.sh` (966 = código de la ENAHO 2024 en el portal del INEI).
2. Corre exactamente:
   ```bash
   uv run ${CLAUDE_SKILL_DIR}/scripts/limpiar.py --anio 2024
   ```
   Solo 2024 está validado; si piden otro año, dilo en vez de improvisar.
3. Lee `salidas/validacion.txt`. Si dice `NO VÁLIDO` o el script termina con error, **detente** y explica qué
   verificación falló. Nunca ajustes cifras para que coincidan con la referencia.
4. Responde con las cifras de `salidas/indicadores.csv` (léelo con `dtype={"ccdd": str}`), citando el grupo, el
   método de la columna `metodo` y la fuente «INEI, ENAHO 2024». Para un cruce que no esté ahí, calcúlalo desde
   los parquet con el mismo peso:
   - territorial (nacional, área, departamento, Lima Metropolitana): `salidas/hogares_2024.parquet`, peso
     `peso_personas` (= factor07 × mieperho, método oficial del INEI);
   - individual (sexo, edad, parentesco): `salidas/personas_2024.parquet`, peso `facpob07`.
   Nunca uses promedios simples: `(pobre * peso).sum() / peso.sum() * 100`.
5. Antes de usar una variable que no está en las bases, lee [reference.md](reference.md).

Las asociaciones que encuentres son descriptivas: no las presentes como causas.
