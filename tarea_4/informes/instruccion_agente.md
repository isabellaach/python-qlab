# Instrucción de la ejecución integrada (Parte 3)

Se pega tal cual en una sesión nueva de Claude Code abierta en `tarea_4/`, con el MCP `bcrp` conectado y las tres
skills cargadas. No trae cifras: el agente debe obtenerlas con las herramientas.

```text
Eres un agente de investigación socioeconómica. Responde esta pregunta con datos oficiales:

«¿Cuánto subieron los precios de los alimentos en Lima entre 2021 y 2024 frente a la inflación general,
y qué departamentos, áreas y grupos de población tenían más pobreza monetaria en 2024?»

Reglas:
- Primero escribe un plan breve: qué series del BCRP y qué indicadores de la ENAHO necesitas, y con qué herramienta
  o skill obtendrás cada uno. Luego ejecútalo sin pedirme confirmación.
- BCRP: usa solo el MCP bcrp. Busca las series con buscar_series; calcula toda cifra con resumen (variación
  acumulada de los índices de precios con base dic. 2021 = 100 y picos de la inflación a 12 meses); guarda con
  graficar_serie un gráfico de la inflación a 12 meses de alimentos frente al IPC total, de 2020 a 2024, con el
  rango meta de 1 % a 3 %, en figuras/informe_bcrp_inflacion_alimentos.png.
- ENAHO 2024: usa las skills limpiando-enaho (si falta la base o para validar), graficando-enaho (área, edad y lo
  que haga falta) y mapeando-enaho (mapa departamental). No calcules la pobreza por tu cuenta si una skill lo hace.
- No hagas cuentas a mano ni escribas cifras de memoria: cada número del informe debe salir de una llamada a una
  herramienta, de salidas/indicadores.csv, de salidas/validacion.txt o de salidas/comparacion_mapa_referencia.csv.
- Si una herramienta falla o no encuentra datos, dilo en el informe en vez de inventar.
- Las series del BCRP son de Lima Metropolitana y mensuales; la ENAHO es nacional y de 2024. No presentes la
  relación entre precios y pobreza como causal.

Escribe informes/informe_final.md con estas secciones:
1. Pregunta de investigación (tema, objetivo y delimitación)
2. Fuentes y metodología (series con su código, módulos de la ENAHO, ponderación, indicadores)
3. Resultados: al menos 3 hallazgos, cada uno con sus cifras y su fuente (código de serie y periodo, o archivo)
4. Visualizaciones: el gráfico del BCRP, un gráfico de la ENAHO y el mapa departamental, con rutas relativas
   a figuras/ y mapas/ (desde informes/ usa ../figuras/... y ../mapas/...)
5. Interpretación
6. Limitaciones (cobertura temporal y geográfica, calidad de datos, alcance de las conclusiones)
7. Reproducibilidad (comandos, scripts, archivos de salida, códigos de serie y URLs del BCRP)
Agrega al final una tabla «Trazabilidad de cifras» con cada número del informe, su valor, la herramienta o
archivo de donde salió y la URL o ruta para comprobarlo.
```
