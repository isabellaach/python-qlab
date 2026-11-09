# Verificación manual de las cifras del informe

Comprobé cifras de `informe_final.md` contra fuentes que **no pasan por el agente**:

- **BCRP:** las páginas web de BCRPData, no el MCP. Se consultaron con `curl` el 8 de noviembre de 2026 y se
  pueden abrir en el navegador con los enlaces de la tabla.
- **ENAHO:** las cifras oficiales del INEI que dan como referencia el enunciado de la Tarea 4
  ([issue #201](https://github.com/d2cml-ai/Data-Science-Python/issues/201)) y la Sesión 16
  (`.claude/skills/mapeando-enaho/referencia_pobreza_departamento_2024.csv`, copiado de esa sesión).

Una cifra se da por correcta si coincide con la fuente al redondearla a la precisión publicada: 2 decimales en el
BCRP y 1 decimal en el INEI.

## BCRP (precios, Lima Metropolitana)

| # | Afirmación del informe | Informe | Fuente externa | ¿Coincide? | Dónde comprobarlo |
|---|---|---|---|---|---|
| 1 | Índice de alimentos y bebidas en dic. 2024 (dic. 2021 = 100), es decir, +19,53 % acumulado | 119,53 | 119.53 (y dic. 2021 = 100.00) | ✔ | [PN39445PM, 2021-12 a 2024-12](https://estadisticas.bcrp.gob.pe/estadisticas/series/mensuales/resultados/PN39445PM/html/2021-12/2024-12/) |
| 2 | Índice del IPC total en dic. 2024 (dic. 2021 = 100), es decir, +14,17 % acumulado | 114,17 | 114.17 | ✔ | [PN38705PM, 2021-12 a 2024-12](https://estadisticas.bcrp.gob.pe/estadisticas/series/mensuales/resultados/PN38705PM/html/2021-12/2024-12/) |
| 3 | Máximo del índice de alimentos (ago. 2024) y del IPC total (ago. 2024) | 120,75 y 114,32 | 120.75 (Ago24) y 114.32 (Ago24) | ✔ | Mismos enlaces 1 y 2 |
| 4 | Pico de la inflación a 12 meses de alimentos: feb. 2023 | 13,16 % | 13.16 (Feb23) | ✔ | [PN09822PM, 2020-01 a 2024-12](https://estadisticas.bcrp.gob.pe/estadisticas/series/mensuales/resultados/PN09822PM/html/2020-1/2024-12/) |
| 5 | Pico de la inflación a 12 meses total: jun. 2022 | 8,81 % | 8.81 (Jun22) | ✔ | [PN01273PM, 2020-01 a 2024-12](https://estadisticas.bcrp.gob.pe/estadisticas/series/mensuales/resultados/PN01273PM/html/2020-1/2024-12/) |
| 6 | Inflación a 12 meses de alimentos, ene. y dic. 2024 | 4,28 % y 1,25 % | 4.28 y 1.25 | ✔ | Enlace 4 |
| 7 | Inflación a 12 meses total, ene. y dic. 2024 | 3,02 % y 1,97 % | 3.02 y 1.97 | ✔ | Enlace 5 |

La variación acumulada del punto 1 sale de 119,53 / 100 − 1 = 19,53 %. Además, la API del BCRP, consultada con
`curl` y sin el MCP, da 119.529248286908, es decir, 19,53 %.

## ENAHO 2024 (pobreza monetaria, INEI)

| # | Afirmación del informe | Informe | Cifra oficial del INEI | Diferencia | ¿Coincide? |
|---|---|---|---|---|---|
| 8 | Pobreza monetaria nacional | 27,58 % | 27,6 % | −0,02 pp | ✔ |
| 9 | Pobreza rural y urbana | 39,30 % y 24,81 % | 39,3 % y 24,8 % | 0,00 y +0,01 pp | ✔ |
| 10 | Pobreza de Lima Metropolitana | 28,21 % | 28,2 % | +0,01 pp | ✔ |
| 11 | Pobreza extrema nacional | 5,50 % | 5,5 % | 0,00 pp | ✔ |
| 12 | Departamento con más pobreza (Cajamarca) y con menos (Ica) | 45,01 % y 6,01 % | 45,0 % y 6,0 % | +0,01 y +0,01 pp | ✔ |
| 13 | Loreto, Puno, Callao y Lima | 42,97 %, 39,94 %, 33,86 % y 27,07 % | 43,0 %, 39,9 %, 33,9 % y 27,1 % | entre −0,04 y +0,04 pp | ✔ |
| 14 | Residentes habituales en la muestra | 108 664 | 108 664 (enunciado) | 0 | ✔ |

En los 25 departamentos, la diferencia máxima es de 0,05 pp (Amazonas); ver
`salidas/comparacion_mapa_referencia.csv`.

**No verificadas con una fuente externa:** las tasas por sexo y por grupo de edad (por ejemplo, 36,47 % en las
personas de 0 a 17 años). No tengo una cifra oficial de referencia a mano. Se calcularon con `facpob07` sobre los
residentes habituales, y el mismo método da 27,53 % a nivel nacional, a 0,07 pp del 27,6 % oficial.

## Resultado

Revisé **14 afirmaciones**, 7 del BCRP y 7 de la ENAHO. **Las 14 coinciden** con la fuente oficial. No encontré
cifras inventadas ni mal citadas en el informe.

Una precisión de redacción: el título del gráfico del BCRP dice que la inflación «volvió al rango meta en 2024». Es
cierto para el cierre del año, pero en setiembre de 2024 la inflación de alimentos (0,69 %) estuvo por debajo del
rango. El propio informe lo aclara en la sección 4.

**Comprobación en el navegador** (además de `curl`), marcada a mano:

- [x] Enlace 1 (PN39445PM): dic. 2024 = 119.53
- [x] Enlace 4 (PN09822PM): feb. 2023 = 13.16 y dic. 2024 = 1.25
- [x] Enlace 5 (PN01273PM): jun. 2022 = 8.81 y dic. 2024 = 1.97
Captura de la comprobación: [`evidencias_ia/integracion/02_verificacion_bcrp_web.png`](../evidencias_ia/integracion/02_verificacion_bcrp_web.png)
