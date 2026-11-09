# Demo de las skills ENAHO: transcripción completa

Sesión `aa5a55c4-c952-44f3-9a7e-41b4ac63ec26` de Claude Code, exportada y sanitizada con `scripts/exportar_conversaciones.py`.

## Usuaria · 00:34 UTC

Haz un mapa de la pobreza monetaria por departamento con ENAHO 2024

`Skill`

```json
{
 "skill": "mapeando-enaho"
}
```

<details><summary>Resultado</summary>

```text
Launching skill: mapeando-enaho
```
</details>

## Usuaria · 00:34 UTC

Base directory for this skill: ~/Documents/Github/python-qlab/tarea_4/.claude/skills/mapeando-enaho

# Mapear la pobreza de la ENAHO 2024 por departamento

Trabaja desde la raíz del proyecto (`tarea_4/`).

1. Si no existe `salidas/hogares_2024.parquet`, usa primero la skill `limpiando-enaho` y sigue solo si su
   `validacion.txt` dice `VÁLIDO`.
2. Si no existe `datos/peru_departamental_simple.geojson`, corre `bash scripts/descargar_datos.sh`.
3. Corre exactamente:
   ```bash
   uv run ~/Documents/Github/python-qlab/tarea_4/.claude/skills/mapeando-enaho/scripts/mapear.py
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

`Bash`

```json
{
 "command": "ls salidas/ datos/ 2>&1; cat salidas/validacion.txt 2>&1 | head -20",
 "description": "Check existing outputs and data files"
}
```

<details><summary>Resultado</summary>

```text
datos/:
966-Modulo02.zip
966-Modulo34.zip
peru_departamental_simple.geojson

salidas/:
comparacion_mapa_referencia.csv
indicadores.csv
validacion.txt
VALIDACIÓN ENAHO 2024  ·  2026-11-08 18:54
Archivos: 966-Modulo34/sumaria-2024.dta (33,691 hogares) y 966-Modulo02/enaho01-2024-200.dta (117,721 personas)
Unidad de análisis: residentes habituales; pobreza = pobreza <= 2; urbano = estrato <= 5.

[APROBADA] (esencial) Llaves únicas en hogares (módulo 34): 0 duplicados con ['conglome', 'vivienda', 'hogar']
[APROBADA] (esencial) Llaves de hogares (módulo 34) como texto, con ceros iniciales: largos {'conglome': [6], 'vivienda': [3], 'hogar': [2]}
[APROBADA] (esencial) Llaves únicas en personas (módulo 02): 0 duplicados con ['conglome', 'vivienda', 'hogar', 'codperso']
[APROBADA] (esencial) Llaves de personas (módulo 02) como texto, con ceros iniciales: largos {'conglome': [6], 'vivienda': [3], 'hogar': [2], 'codperso': [2]}
[APROBADA] Hogares en la sumaria: 33,691 (referencia 33,691)
[APROBADA] (esencial) Residentes habituales: 108,664 de 117,721 filas del módulo 02 (referencia 108,664)
[APROBADA] (esencial) Unión m:1 sin duplicar ni perder personas: 108,664 antes, 108,664 después; 0 personas sin hogar en la sumaria
[APROBADA] (esencial) 25 códigos territoriales (01 a 25): 25 códigos: 01…25; sin nombre: ninguno
[APROBADA] (esencial) Sin datos faltantes en pobreza, factores y ubicación: 0 valores faltantes
[APROBADA] (esencial) Factores de expansión positivos: facpob07 mín. 1.1; factor07 mín. 1.1
[APROBADA] (esencial) Población expandida plausible (30 a 36 millones): 34,147,768 personas con facpob07
[APROBADA] (esencial) Pobreza nacional (sumaria, factor07 × mieperho, método INEI): 27.58 % (referencia 27.6 % ± 0.1)
[APROBADA] (esencial) Pobreza nacional (personas, facpob07): 27.53 % (referencia 27.6 % ± 0.1)
[APROBADA] La ponderación cambia el resultado (el promedio simple no sirve): sin ponderar 25.61 % frente a 27.53 % ponderado
[APROBADA] Pobreza urbana (método INEI): 24.81 % (referencia 24.8 % ± 0.15); con personas y facpob07 daría 24.74 %
[APROBADA] Pobreza rural (método INEI): 39.30 % (referencia 39.3 % ± 0.15); con personas y facpob07 daría 39.44 %
```
</details>

`Bash`

```json
{
 "command": "tail -5 salidas/validacion.txt; ls salidas/*.parquet 2>&1",
 "description": "Check validation verdict and parquet files"
}
```

<details><summary>Resultado (error)</summary>

```text
Exit code 1
[APROBADA] Pobreza extrema (método INEI): 5.50 % (referencia 5.5 % ± 0.15)
[APROBADA] Pobreza de los 25 departamentos frente a la referencia de la Sesión 16: diferencia máxima 0.05 pp (01 Amazonas)

Resumen: 19 de 19 verificaciones aprobadas; 0 esenciales fallidas.
RESULTADO: VÁLIDO. La base se puede usar.
(eval):1: no matches found: salidas/*.parquet
```
</details>

**Claude** · 00:35 UTC

`salidas/hogares_2024.parquet` no existe, así que primero corro la limpieza.

`Skill`

```json
{
 "skill": "limpiando-enaho"
}
```

<details><summary>Resultado</summary>

```text
Launching skill: limpiando-enaho
```
</details>

## Usuaria · 00:35 UTC

Base directory for this skill: ~/Documents/Github/python-qlab/tarea_4/.claude/skills/limpiando-enaho

# Limpiar la ENAHO 2024

Trabaja desde la raíz del proyecto (`tarea_4/`). No reescribas el pipeline: corre el script tal cual.

1. Revisa que existan `datos/966-Modulo34.zip` y `datos/966-Modulo02.zip`. Si faltan, corre
   `bash scripts/descargar_datos.sh` (966 = código de la ENAHO 2024 en el portal del INEI).
2. Corre exactamente:
   ```bash
   uv run ~/Documents/Github/python-qlab/tarea_4/.claude/skills/limpiando-enaho/scripts/limpiar.py --anio 2024
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

`Bash`

```json
{
 "command": "uv run ~/Documents/Github/python-qlab/tarea_4/.claude/skills/limpiando-enaho/scripts/limpiar.py --anio 2024 2>&1 | tail -15; tail -2 salidas/validacion.txt; ls salidas/",
 "description": "Run ENAHO cleaning pipeline and check verdict",
 "timeout": 600000
}
```

<details><summary>Resultado</summary>

```text
[APROBADA] (esencial) Factores de expansión positivos: facpob07 mín. 1.1; factor07 mín. 1.1
[APROBADA] (esencial) Población expandida plausible (30 a 36 millones): 34,147,768 personas con facpob07
[APROBADA] (esencial) Pobreza nacional (sumaria, factor07 × mieperho, método INEI): 27.58 % (referencia 27.6 % ± 0.1)
[APROBADA] (esencial) Pobreza nacional (personas, facpob07): 27.53 % (referencia 27.6 % ± 0.1)
[APROBADA] La ponderación cambia el resultado (el promedio simple no sirve): sin ponderar 25.61 % frente a 27.53 % ponderado
[APROBADA] Pobreza urbana (método INEI): 24.81 % (referencia 24.8 % ± 0.15); con personas y facpob07 daría 24.74 %
[APROBADA] Pobreza rural (método INEI): 39.30 % (referencia 39.3 % ± 0.15); con personas y facpob07 daría 39.44 %
[APROBADA] Pobreza lima metropolitana (método INEI): 28.21 % (referencia 28.2 % ± 0.15); con personas y facpob07 daría 28.03 %
[APROBADA] Pobreza extrema (método INEI): 5.50 % (referencia 5.5 % ± 0.15)
[APROBADA] Pobreza de los 25 departamentos frente a la referencia de la Sesión 16: diferencia máxima 0.05 pp (01 Amazonas)

Resumen: 19 de 19 verificaciones aprobadas; 0 esenciales fallidas.
RESULTADO: VÁLIDO. La base se puede usar.

Guardé salidas/personas_2024.parquet (108,664 filas), salidas/hogares_2024.parquet (33,691 filas) y salidas/indicadores.csv
Resumen: 19 de 19 verificaciones aprobadas; 0 esenciales fallidas.
RESULTADO: VÁLIDO. La base se puede usar.
comparacion_mapa_referencia.csv
hogares_2024.parquet
indicadores.csv
personas_2024.parquet
validacion.txt
```
</details>

**Claude** · 00:35 UTC

Limpieza válida (19/19). Ahora el mapa:

`Bash`

```json
{
 "command": "uv run ~/Documents/Github/python-qlab/tarea_4/.claude/skills/mapeando-enaho/scripts/mapear.py 2>&1 | tail -40",
 "description": "Generate the department poverty choropleth map",
 "timeout": 600000
}
```

<details><summary>Resultado</summary>

```text
Mapa: mapas/pobreza_departamento_2024.png  ·  25/25 departamentos con dato, unidos por código
Comparación con la Sesión 16: 25/25 coinciden (± 0.1 pp); diferencia máxima 0.05 pp -> salidas/comparacion_mapa_referencia.csv
ccdd  departamento  pobreza_pct  referencia_pct  diferencia_pp
  06     Cajamarca        45.01            45.0           0.01
  16        Loreto        42.97            43.0          -0.03
  21          Puno        39.94            39.9           0.04
  19         Pasco        38.97            39.0          -0.03
  10       Huánuco        38.96            39.0          -0.04
  07        Callao        33.86            33.9          -0.04
  09  Huancavelica        33.40            33.4           0.00
  05      Ayacucho        32.76            32.8          -0.04
  20         Piura        31.86            31.9          -0.04
  13   La Libertad        30.19            30.2          -0.01
  25       Ucayali        27.07            27.1          -0.03
  15          Lima        27.07            27.1          -0.03
  24        Tumbes        26.90            26.9           0.00
  01      Amazonas        25.75            25.7           0.05
  23         Tacna        23.99            24.0          -0.01
  03      Apurímac        23.96            24.0          -0.04
  02        Áncash        22.77            22.8          -0.03
  22    San Martín        22.02            22.0           0.02
  08         Cusco        18.54            18.5           0.04
  12         Junín        18.50            18.5          -0.00
  04      Arequipa        15.78            15.8          -0.02
  14    Lambayeque        14.04            14.0           0.04
  17 Madre de Dios        11.15            11.1           0.05
  18      Moquegua        10.97            11.0          -0.03
  11           Ica         6.01             6.0           0.01
```
</details>

`Read`

```json
{
 "file_path": "~/Documents/Github/python-qlab/tarea_4/mapas/pobreza_departamento_2024.png"
}
```

<details><summary>Resultado</summary>

```text
[imagen]
```
</details>

**Claude** · 00:35 UTC

El mapa está guardado en **`mapas/pobreza_departamento_2024.png`**.

**Revisiones:**
- Primero tuve que correr la limpieza, porque faltaba `salidas/hogares_2024.parquet`. La validación dio **VÁLIDO**: pasaron las 19 verificaciones, y la pobreza nacional sale en 27.58 % frente al 27.6 % de la referencia.
- Los **25 departamentos tienen dato**. Se unieron por código territorial, y Lima y Callao van por separado.
- Los 25 coinciden con la referencia de la Sesión 16 dentro de ± 0.1 pp. La mayor diferencia es de 0.05 pp, en Amazonas.

**Resultados (porcentaje de personas pobres, ponderado con factor07 × mieperho):**
- **Más pobreza:** Cajamarca (45.0 %), seguida de Loreto (43.0 %) y Puno (39.9 %).
- **Menos pobreza:** Ica (6.0 %), seguida de Moquegua (11.0 %) y Madre de Dios (11.1 %).
- Callao (33.9 %) tiene más pobreza que Lima (27.1 %).

Fuente: INEI, ENAHO 2024. Las cifras de cada departamento están en `salidas/comparacion_mapa_referencia.csv`.

Las cifras solo describen cómo se reparte la pobreza en el territorio y no muestran por qué es más alta en unos departamentos que en otros.

Hay un detalle visual: la etiqueta «45.0» de Cajamarca queda en parte encima del borde con Lambayeque. Puedo moverla un poco si vas a publicar el mapa.

## Usuaria · 00:36 UTC

sí, mueve la etiqueta de Cajamarca

`Bash`

```json
{
 "command": "grep -n \"annot\\|representative_point\\|centroid\\|Callao\\|xytext\\|offset\\|text(\" .claude/skills/mapeando-enaho/scripts/mapear.py",
 "description": "Find label placement code in map script"
}
```

<details><summary>Resultado</summary>

```text
7:con dato (Lima 15 y Callao 07 por separado) y compara cada departamento con la referencia de la Sesión 16.
55:    assert {"07", "15"} <= set(mapa.ccdd), "Lima (15) y Callao (07) deben ir separados"
73:    puntos = mapa.to_crs(32718).representative_point().to_crs(mapa.crs)
75:        if fila.ccdd == "07":                                   # Callao es muy chico: etiqueta al costado
76:            ax.annotate(f"Callao {fila.pobreza_pct:.1f}", (pt.x, pt.y), xytext=(-60, -6), textcoords="offset points",
80:        ax.text(pt.x, pt.y, f"{fila.pobreza_pct:.1f}", ha="center", va="center", fontsize=7.5, fontweight="bold",
87:    fig.text(0.02, 0.02, "Fuente: INEI, ENAHO 2024 (módulo 34). Estimación ponderada (factor07 × mieperho).\n"
```
</details>

`Read`

```json
{
 "file_path": "~/Documents/Github/python-qlab/tarea_4/.claude/skills/mapeando-enaho/scripts/mapear.py",
 "offset": 70,
 "limit": 14
}
```

<details><summary>Resultado</summary>

```text
70	    mapa.plot(column="pobreza_pct", cmap="Purples", vmin=0, vmax=vmax, edgecolor="white", linewidth=0.6, ax=ax,
71	              legend=True, legend_kwds={"label": "Pobreza monetaria (% de personas)", "shrink": 0.55,
72	                                        "orientation": "vertical"})
73	    puntos = mapa.to_crs(32718).representative_point().to_crs(mapa.crs)
74	    for (_, fila), pt in zip(mapa.iterrows(), puntos):
75	        if fila.ccdd == "07":                                   # Callao es muy chico: etiqueta al costado
76	            ax.annotate(f"Callao {fila.pobreza_pct:.1f}", (pt.x, pt.y), xytext=(-60, -6), textcoords="offset points",
77	                        fontsize=7, arrowprops={"arrowstyle": "-", "lw": 0.6, "color": "#444"})
78	            continue
79	        claro = fila.pobreza_pct < vmax * 0.55
80	        ax.text(pt.x, pt.y, f"{fila.pobreza_pct:.1f}", ha="center", va="center", fontsize=7.5, fontweight="bold",
81	                color="#222222" if claro else "white")
82	    mx, mn = mapa.loc[mapa.pobreza_pct.idxmax()], mapa.loc[mapa.pobreza_pct.idxmin()]
83	    ax.set_title(f"La pobreza va de {mn.pobreza_pct:.1f} % en {mn.departamento} a {mx.pobreza_pct:.1f} % en "
```
</details>

**Claude** · 00:37 UTC

La etiqueta está en el punto representativo de Cajamarca, justo en la parte angosta. La bajo unos puntos hacia la zona ancha del departamento, que está más al sur.

`Edit`

```json
{
 "replace_all": false,
 "file_path": "~/Documents/Github/python-qlab/tarea_4/.claude/skills/mapeando-enaho/scripts/mapear.py",
 "old_string": "        claro = fila.pobreza_pct < vmax * 0.55\n        ax.text(pt.x, pt.y, f\"{fila.pobreza_pct:.1f}\", ha=\"center\", va=\"center\", fontsize=7.5, fontweight=\"bold\",\n                color=\"#222222\" if claro else \"white\")",
 "new_string": "        claro = fila.pobreza_pct < vmax * 0.55\n        desplazamiento = {\"06\": (3, -12)}.get(fila.ccdd, (0, 0))   # Cajamarca: bajar a su parte ancha\n        ax.annotate(f\"{fila.pobreza_pct:.1f}\", (pt.x, pt.y), xytext=desplazamiento, textcoords=\"offset points\",\n                    ha=\"center\", va=\"center\", fontsize=7.5, fontweight=\"bold\",\n                    color=\"#222222\" if claro else \"white\")"
}
```

`Bash`

```json
{
 "command": "uv run ~/Documents/Github/python-qlab/tarea_4/.claude/skills/mapeando-enaho/scripts/mapear.py 2>&1 | head -2",
 "description": "Regenerate the map with the moved label",
 "timeout": 600000
}
```

<details><summary>Resultado</summary>

```text
The file ~/Documents/Github/python-qlab/tarea_4/.claude/skills/mapeando-enaho/scripts/mapear.py has been updated successfully.
```
</details>

<details><summary>Resultado</summary>

```text
Mapa: mapas/pobreza_departamento_2024.png  ·  25/25 departamentos con dato, unidos por código
Comparación con la Sesión 16: 25/25 coinciden (± 0.1 pp); diferencia máxima 0.05 pp -> salidas/comparacion_mapa_referencia.csv
```
</details>

`Read`

```json
{
 "file_path": "~/Documents/Github/python-qlab/tarea_4/mapas/pobreza_departamento_2024.png"
}
```

<details><summary>Resultado</summary>

```text
[imagen]
```
</details>

**Claude** · 00:37 UTC

Mejoró, pero el «4» todavía roza el borde izquierdo. La muevo un poco más a la derecha y hacia abajo.

`Bash`

```json
{
 "command": "sed -i '' 's/{\"06\": (3, -12)}/{\"06\": (8, -22)}/' .claude/skills/mapeando-enaho/scripts/mapear.py && grep -n '\"06\"' .claude/skills/mapeando-enaho/scripts/mapear.py && uv run .claude/skills/mapeando-enaho/scripts/mapear.py 2>&1 | head -2",
 "description": "Adjust Cajamarca label offset and regenerate map",
 "timeout": 600000
}
```

<details><summary>Resultado</summary>

```text
80:        desplazamiento = {"06": (8, -22)}.get(fila.ccdd, (0, 0))   # Cajamarca: bajar a su parte ancha
Mapa: mapas/pobreza_departamento_2024.png  ·  25/25 departamentos con dato, unidos por código
Comparación con la Sesión 16: 25/25 coinciden (± 0.1 pp); diferencia máxima 0.05 pp -> salidas/comparacion_mapa_referencia.csv
[This command modified 1 file you've previously read: .claude/skills/mapeando-enaho/scripts/mapear.py. Call Read before editing.]
```
</details>

`Read`

```json
{
 "file_path": "~/Documents/Github/python-qlab/tarea_4/mapas/pobreza_departamento_2024.png"
}
```

<details><summary>Resultado</summary>

```text
[imagen]
```
</details>

**Claude** · 00:37 UTC

Moví la etiqueta «45.0» de Cajamarca hacia la parte ancha del departamento, y ahora queda completa sin tocar ningún borde. El mapa actualizado reemplazó al anterior en `mapas/pobreza_departamento_2024.png`.

El cambio está en el script de la skill, `.claude/skills/mapeando-enaho/scripts/mapear.py:80`, así que la próxima vez que se genere el mapa la etiqueta saldrá en el mismo lugar. Volví a correrlo y las cifras siguen igual: 25 de 25 departamentos con dato y todos dentro de ± 0.1 pp de la referencia.

Hay dos etiquetas más que todavía rozan un borde, por si quieres corregirlas antes de publicar:
- **Huánuco (39.0):** el «39.0» de arriba toca la línea con Pasco.
- **Puno (39.9):** queda pegada a su borde oeste.

Se corrigen igual que la de Cajamarca, agregándolas a la lista de desplazamientos del script.

## Usuaria · 00:38 UTC

ok arreglalas

`Bash`

```json
{
 "command": "sed -i '' 's/{\"06\": (8, -22)}/{\"06\": (8, -22), \"10\": (-5, 10), \"21\": (14, 4)}/; s/# Cajamarca: bajar a su parte ancha/# Cajamarca, Huánuco y Puno: alejar la etiqueta del borde/' .claude/skills/mapeando-enaho/scripts/mapear.py && grep -n 'desplazamiento =' .claude/skills/mapeando-enaho/scripts/mapear.py && uv run .claude/skills/mapeando-enaho/scripts/mapear.py 2>&1 | head -2",
 "description": "Offset Huánuco and Puno labels and regenerate map",
 "timeout": 600000
}
```

<details><summary>Resultado</summary>

```text
80:        desplazamiento = {"06": (8, -22), "10": (-5, 10), "21": (14, 4)}.get(fila.ccdd, (0, 0))   # Cajamarca, Huánuco y Puno: alejar la etiqueta del borde
Mapa: mapas/pobreza_departamento_2024.png  ·  25/25 departamentos con dato, unidos por código
Comparación con la Sesión 16: 25/25 coinciden (± 0.1 pp); diferencia máxima 0.05 pp -> salidas/comparacion_mapa_referencia.csv
[This command modified 1 file you've previously read: .claude/skills/mapeando-enaho/scripts/mapear.py. Call Read before editing.]
```
</details>

`Read`

```json
{
 "file_path": "~/Documents/Github/python-qlab/tarea_4/mapas/pobreza_departamento_2024.png"
}
```

<details><summary>Resultado</summary>

```text
[imagen]
```
</details>

**Claude** · 00:38 UTC

Puno quedó bien. Huánuco se movió en la dirección equivocada: ahora toca el borde de arriba. La parte ancha de Huánuco está a la izquierda, así que la llevo hacia allá.

`Bash`

```json
{
 "command": "sed -i '' 's/\"10\": (-5, 10)/\"10\": (-14, -6)/' .claude/skills/mapeando-enaho/scripts/mapear.py && grep -c '\"10\": (-14, -6)' .claude/skills/mapeando-enaho/scripts/mapear.py && uv run .claude/skills/mapeando-enaho/scripts/mapear.py 2>&1 | head -2",
 "description": "Readjust Huánuco label offset and regenerate map",
 "timeout": 600000
}
```

`Read`

```json
{
 "file_path": "~/Documents/Github/python-qlab/tarea_4/mapas/pobreza_departamento_2024.png"
}
```

<details><summary>Resultado</summary>

```text
1
Mapa: mapas/pobreza_departamento_2024.png  ·  25/25 departamentos con dato, unidos por código
Comparación con la Sesión 16: 25/25 coinciden (± 0.1 pp); diferencia máxima 0.05 pp -> salidas/comparacion_mapa_referencia.csv
[This command modified 1 file you've previously read: .claude/skills/mapeando-enaho/scripts/mapear.py. Call Read before editing.]
```
</details>

<details><summary>Resultado</summary>

```text
[imagen]
```
</details>

**Claude** · 00:38 UTC

Arreglé las dos etiquetas, y ahora todas las del mapa quedan dentro de su departamento:
- **Huánuco (39.0):** está en la parte ancha, al oeste, lejos del borde con Pasco. En el primer intento la subí, pero quedó pegada al borde de arriba, así que la llevé hacia la izquierda.
- **Puno (39.9):** la moví a la derecha y ya no toca su borde oeste.

Los desplazamientos de Cajamarca, Huánuco y Puno están en `.claude/skills/mapeando-enaho/scripts/mapear.py:80`, así que se aplican cada vez que se genera el mapa. Al volver a correrlo, las cifras no cambiaron: 25 de 25 departamentos con dato y todos dentro de ± 0.1 pp de la referencia.

El mapa actualizado está en `mapas/pobreza_departamento_2024.png`. No hice commit; avísame si quieres que lo prepare.

## Usuaria · 00:38 UTC

¿Cuál fue la pobreza en Cusco en 2024?

`Bash`

```json
{
 "command": "head -1 salidas/indicadores.csv; grep -i \"cusco\" salidas/indicadores.csv",
 "description": "Look up Cusco poverty figure in indicators"
}
```

<details><summary>Resultado</summary>

```text
grupo,categoria,pobreza_pct,pobreza_extrema_pct,poblacion_expandida,muestra,unidad_muestra,metodo,ccdd,anio,fuente
Departamento,08 Cusco,18.54,2.1,1409467,1230,hogares,"hogares, factor07 × mieperho",08,2024,"INEI, ENAHO 2024, módulos 34 (sumaria) y 02 (miembros); estimación ponderada"
```
</details>

**Claude** · 00:38 UTC

En 2024, el **18.5 %** de la población de Cusco estaba en pobreza monetaria (18.54 % en el cálculo). Son unas 1.41 millones de personas en total.

- **Pobreza extrema:** 2.1 %.
- **Referencia oficial (Sesión 16):** 18.5 %, así que la cifra coincide.
- **Comparación:** está casi 9 puntos por debajo del promedio nacional (27.6 %). Es casi igual a Junín (18.5 %) y está lejos de Cajamarca, que tiene la tasa más alta (45.0 %).
- **Método:** se calculó con la sumaria de hogares, con el peso factor07 × mieperho que usa el INEI. La muestra es de 1,230 hogares en el departamento.

Fuente: INEI, ENAHO 2024 (módulos 34 y 02), estimación ponderada.

## Usuaria · 00:39 UTC

<command-message>graficando-enaho</command-message>
<command-name>/graficando-enaho</command-name>
<command-args>sexo_area</command-args>

## Usuaria · 00:39 UTC

Base directory for this skill: ~/Documents/Github/python-qlab/tarea_4/.claude/skills/graficando-enaho

# Graficar la pobreza de la ENAHO 2024

Trabaja desde la raíz del proyecto (`tarea_4/`).

1. Si no existen `salidas/hogares_2024.parquet` y `salidas/personas_2024.parquet`, usa primero la skill
   `limpiando-enaho` y sigue solo si su `validacion.txt` dice `VÁLIDO`.
2. Elige el tipo según el pedido y corre exactamente:
   ```bash
   uv run ~/Documents/Github/python-qlab/tarea_4/.claude/skills/graficando-enaho/scripts/graficar.py --tipo sexo_area
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

`Bash`

```json
{
 "command": "uv run ~/Documents/Github/python-qlab/tarea_4/.claude/skills/graficando-enaho/scripts/graficar.py --tipo sexo_area 2>&1 | tail -30",
 "description": "Generate poverty chart by sex and area",
 "timeout": 600000
}
```

<details><summary>Resultado</summary>

```text
figuras/pobreza_sexo_area_2024.png
     categoria  pobreza_pct
Hombre\nurbana        24.63
 Mujer\nurbana        24.83
 Hombre\nrural        38.82
  Mujer\nrural        40.04

Nacional: 27.58 % (método INEI) · 27.53 % (residentes, facpob07)
```
</details>

`Read`

```json
{
 "file_path": "~/Documents/Github/python-qlab/tarea_4/figuras/pobreza_sexo_area_2024.png"
}
```

<details><summary>Resultado</summary>

```text
[imagen]
```
</details>

**Claude** · 00:39 UTC

El gráfico de pobreza por sexo y área está en **`figuras/pobreza_sexo_area_2024.png`**.

| Grupo | Pobreza monetaria |
|---|---|
| Hombre urbano | 24.63 % |
| Mujer urbana | 24.83 % |
| Hombre rural | 38.82 % |
| Mujer rural | 40.04 % |

- **La mayor diferencia es entre áreas, no entre sexos.** En el área rural, la pobreza es unos 14 a 15 puntos más alta que en la urbana, tanto para hombres como para mujeres.
- **En el área urbana, hombres y mujeres son casi iguales.** La diferencia es de 0.2 puntos.
- **En el área rural, la pobreza de las mujeres es 1.2 puntos más alta que la de los hombres.** Es una diferencia pequeña y solo describe la situación; no explica por qué ocurre.

Las cifras se calcularon por persona entre los residentes habituales, con el peso facpob07. Por eso la línea de referencia del gráfico marca el promedio nacional en 27.5 % y no en 27.6 %, que es la cifra oficial del INEI calculada con los hogares (sumaria, factor07 × mieperho).

Fuente: INEI, ENAHO 2024 (módulos 34 y 02), estimación ponderada.

## Usuaria · 00:40 UTC

<local-command-caveat>The command below was run directly in Claude Code, not sent to you as a request, and its output goes straight to the user. It's recorded here as context for later messages.</local-command-caveat>

## Usuaria · 00:40 UTC

<command-name>/export</command-name>
            <command-message>export</command-message>
            <command-args>evidencias_ia/skills/01_demo_skills_claude_code.md</command-args>

## Usuaria · 00:40 UTC

<local-command-stdout>Conversation exported to: ~/Documents/Github/python-qlab/tarea_4/evidencias_ia/skills/01_demo_skills_claude_code.md</local-command-stdout>
