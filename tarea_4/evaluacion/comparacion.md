# Evaluación: el agente sin y con MCP y skills

Corrida del 8 de noviembre de 2026, 21:15 (hora de Lima). Se usó `uv run evaluacion/evaluar.py` con Claude Sonnet en
modo no interactivo (`claude -p`). Hubo **20 sesiones independientes** (10 preguntas × 2 modos) con
`--no-session-persistence`, así que ninguna sesión vio a otra.

- **Respuestas esperadas fijadas antes de correr.** `preguntas.csv` entró en el commit `d358924` (21:15) antes de la
  corrida y no se cambió después.
- **Verificación independiente del agente:**
  - BCRP: verdades oficiales de la Sesión 04, tomadas de la web del BCRP. Las dos cifras nuevas (PN09822PM y
    PN39445PM) se consultaron con `curl` a la API del BCRP, sin el MCP.
  - ENAHO: valores publicados por el INEI que usan el enunciado y la Sesión 16.
- **Tolerancias fijadas de antemano** (columna `tolerancia` de `preguntas.csv`):
  - 0,05 pp para inflación y PBI; 0,01 para la tasa de referencia; 0,002 soles para el tipo de cambio.
  - 0,15 pp para la pobreza, cuyas referencias del INEI están redondeadas a un decimal.
  - 0,2 pp para la variación acumulada.
  - En las preguntas mixtas deben acertar **las dos** cifras.

## Herramientas habilitadas en cada modo

| | Modo A: sin MCP ni skills | Modo B: con MCP y skills |
|---|---|---|
| Herramientas | Ninguna (`--tools ""`) | `Bash`, `Read`, `Skill` y el MCP `bcrp` (`buscar_series`, `serie`, `resumen`, `graficar_serie`) |
| Servidores MCP | Ninguno (`--strict-mcp-config` sin `--mcp-config`) | Solo `bcrp` (se negó `mcp__fetch`) |
| Skills | Desactivadas (`--disable-slash-commands`) | `limpiando-enaho`, `graficando-enaho`, `mapeando-enaho` |
| Carpeta | Temporal y vacía, fuera del proyecto: no puede ver ningún archivo | `tarea_4/`, con prohibido leer `evaluacion/`, `informes/` y `evidencias_ia/` |
| Bash | — | `uv run .claude/skills/...` y los comandos de solo lectura que permite Claude Code |

La lista exacta de herramientas de cada sesión está en el mensaje `init` de
`evidencias_ia/evaluacion/modo_{A,B}/<id>.jsonl` y en la columna `herramientas_habilitadas` de `resultados.csv`.
Ese mismo archivo trae también la pregunta, la respuesta esperada, la generada, la fuente citada, las herramientas
usadas, el resultado, el tiempo, los turnos, el costo y los errores.

## Resultados

| | Modo A: sin MCP ni skills | Modo B: con MCP y skills |
|---|---|---|
| **Correctas** | **0/10** | **10/10** |
| Incorrectas | 2 | 0 |
| Sin respuesta (reconoce que no sabe) | 8 | 0 |
| Tiempo promedio por pregunta | 5,0 s | 9,3 s |
| Costo total | 0,10 US$ | 0,58 US$ |
| Errores de herramientas | — | 0 |

| Pregunta | Esperada | Modo A | Modo B | Herramientas usadas en el modo B |
|---|---|---|---|---|
| bcrp_ipc_set26 | 4,5487 | sin respuesta | 4,55 ✔ | `buscar_series` → `serie` (PN01273PM) |
| bcrp_referencia_set26 | 4,25 | sin respuesta | 4,25 ✔ | `buscar_series` → `serie` (PD04722MM) |
| bcrp_tc_15oct26 | 3,4282 | sin respuesta | 3,4282 ✔ | `buscar_series` → `serie` (PD04638PD) |
| bcrp_pbi_2025 | 3,4306 | sin respuesta | 3,43 ✔ | `buscar_series` → `resumen` → `serie` (PM04908AA y PM04935AA) |
| enaho_extrema | 5,5 | sin respuesta | 5,5 ✔ | lectura de `salidas/indicadores.csv` y `validacion.txt` |
| enaho_urbana | 24,8 | **26,1 ✘** | 24,81 ✔ | lectura de `salidas/indicadores.csv` |
| enaho_cusco | 18,5 | sin respuesta | 18,54 ✔ | lectura de `salidas/comparacion_mapa_referencia.csv` |
| enaho_cajamarca | 45,0 | sin respuesta | 45,01 ✔ | lectura de `salidas/indicadores.csv` |
| mixta_alimentos_rural | 1,2481 y 39,3 | sin respuesta | 1,25 y 39,3 ✔ | `buscar_series` → `serie` (PN09822PM) + `indicadores.csv` |
| mixta_acumulada_lima | 19,53 y 28,2 | **sin respuesta y 27,8 ✘** | 19,53 y 28,21 ✔ | `buscar_series` → `resumen` (PN39445PM) + `indicadores.csv` |

## Qué mejoró y qué empeoró

- **Mejoraron las 10 preguntas.** Con el MCP y las skills, Claude pasó de 0 a 10 respuestas correctas.
- **Ninguna empeoró.**
- **El costo de la mejora es tiempo y dinero:** casi el doble de tiempo (9,3 s frente a 5,0 s) y unas 6 veces más
  costo.

## Errores principales

1. **Modo A: cifras inventadas de memoria.** Dio dos cifras de pobreza de la ENAHO 2024 de memoria y las dos estaban
   mal:
   - Pobreza urbana: 26,1 % frente al 24,8 % oficial.
   - Pobreza de Lima Metropolitana: 27,8 % frente al 28,2 % oficial.
   - Las dos son plausibles y vienen con una fuente que suena oficial («informe técnico del INEI»), así que un
     lector no notaría el error sin verificarlas.
2. **Modo A: abstención.** En las otras 8 preguntas dijo que no podía saber la cifra (fecha de corte, sin acceso a
   fuentes). Es lo correcto, pero no sirve para responder: las preguntas del BCRP de 2026 son posteriores a la fecha
   de corte del modelo.
3. **Modo B: no usó las skills, sino sus salidas.** En las preguntas de la ENAHO no invocó las skills: leyó con
   `grep` y `cat` los archivos que ya habían generado (`indicadores.csv`, `validacion.txt` y
   `comparacion_mapa_referencia.csv`). La respuesta es trazable, pero:
   - La invocación y el encadenamiento de las skills se demuestran en `evidencias_ia/skills/` y en la ejecución
     integrada (`evidencias_ia/integracion/`), no en esta evaluación.
   - `validacion.txt` y `comparacion_mapa_referencia.csv` incluyen los valores de referencia del INEI. Por eso, en
     la ENAHO, el modo B mide sobre todo si el agente encuentra la cifra validada, no si la estima de forma
     independiente. Aun así, en todos los casos respondió la estimación propia, no la referencia: por ejemplo,
     18,54 y no 18,5.
4. **Modo B: redondeo.** En `bcrp_ipc_set26` (4,55) y `bcrp_pbi_2025` (3,43) redondeó a dos decimales. Las dos
   respuestas quedan dentro de la tolerancia.
5. **Modo B: serie distinta para el PBI.** Usó PM04908AA (variación porcentual real) y no PM04923AA, la de la verdad
   oficial. Dio el mismo valor redondeado.

## Conclusión

Sin herramientas, Claude no puede responder datos posteriores a su fecha de corte. Sus respuestas de memoria sobre
la ENAHO 2024 suenan oficiales pero estaban equivocadas: falló las 2 veces que respondió. Con el MCP del BCRP y las
salidas validadas de las skills de la ENAHO, respondió las 10 preguntas correctamente. Además citó en cada una el
código de la serie, el periodo o el archivo, lo que permite comprobarlas.

La mejora no se debe a que el modelo «sepa más», sino a que **cada cifra sale de una fuente consultable**. A cambio,
tarda el doble y cuesta unas 6 veces más.

Límites de esta evaluación:

- Son solo 10 preguntas, una sola corrida y un solo modelo (Sonnet).
- Las respuestas de la ENAHO del modo B dependen de que las salidas de `limpiando-enaho` ya existían y estaban
  validadas.
