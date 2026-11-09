# Referencia: ENAHO 2024 para la skill limpiando-enaho

## Archivos

| Módulo | Archivo dentro del zip | Una fila por | Filas | Llaves | Factor |
|---|---|---|---|---|---|
| 34 (sumaria) | `966-Modulo34/sumaria-2024.dta` | hogar | 33,691 | `conglome`, `vivienda`, `hogar` | `factor07` |
| 02 (miembros) | `966-Modulo02/enaho01-2024-200.dta` | persona | 117,721 | las tres + `codperso` | `facpob07` |

El zip del módulo 34 trae además `sumaria-2024-12g.dta` (gasto en 12 grupos); el script la ignora.
Descarga: `https://proyectos.inei.gob.pe/iinei/srienaho/descarga/STATA/966-Modulo{34,02}.zip`.

## Reglas del pipeline (scripts/limpiar.py)

1. Leer con `pd.read_stata(..., convert_categoricals=False)`; las llaves quedan como texto
   (`conglome` 6 caracteres, `vivienda` 3, `hogar` 2, `codperso` 2) y se verifica su largo.
2. Columnas en minúscula; `aÑo` pasa a `anio`.
3. Residentes habituales: `((p204 == 1) & (p205 == 2)) | ((p204 == 2) & (p206 == 1))` → 108,664 personas.
4. `personas.merge(hogares, on=llaves, how="left", validate="m:1")`; se exige el mismo número de filas y
   ninguna persona sin hogar.
5. `ccdd = ubigeo[:2]` (01–25; Lima 15 y Callao 07 separados), `area = Urbana si estrato <= 5`,
   `pobre = pobreza <= 2`, `pobre_extremo = pobreza == 1`, `lima_metropolitana = dominio == 8`.

## Variables de las bases limpias

| Variable | Significado |
|---|---|
| `pobreza` | 1 pobre extremo, 2 pobre no extremo, 3 no pobre (INEI, gasto per cápita frente a la línea) |
| `linea`, `linpe` | Línea de pobreza total y extrema (S/ por persona al mes) |
| `gashog2d` | Gasto total bruto anual del hogar (S/) |
| `mieperho` | Miembros del hogar (sin trabajadores del hogar ni pensionistas) |
| `estrato` | 1–5 urbano (más de 2,000 habitantes), 6–8 rural |
| `dominio` | 1–3 costa, 4–6 sierra, 7 selva, 8 Lima Metropolitana |
| `p207` → `sexo` | 1 hombre, 2 mujer |
| `p208a` → `edad` | Años cumplidos; `grupo_edad`: 0-17, 18-29, 30-44, 45-64, 65 y más |
| `p203` | Parentesco con el jefe del hogar (1 = jefe) |
| `facpob07` | Factor de expansión de personas (proyecciones CPV 2007) |
| `factor07` | Factor de expansión de hogares; `peso_personas = factor07 × mieperho` |

## Dos formas de ponderar (y por qué)

| Cifra | Método INEI (sumaria, factor07 × mieperho) | Personas (residentes, facpob07) |
|---|---|---|
| Nacional | 27.58 % | 27.53 % |
| Urbana / rural | 24.81 % / 39.30 % | 24.74 % / 39.44 % |
| Lima Metropolitana | 28.21 % | 28.03 % |
| Diferencia máxima departamental frente a la referencia | 0.05 pp | 0.52 pp (Puno) |

El INEI publica la pobreza con la sumaria y `factor07 × mieperho`. Por eso las cifras territoriales usan ese
método, que reproduce la referencia de la Sesión 16. El sexo y la edad solo están en el módulo 02: esas cifras usan
residentes habituales y `facpob07`, y se rotulan como tales. Son estimaciones muestrales: diferencias menores a
1–2 pp entre grupos pequeños pueden no ser significativas.

## Valores de referencia (enunciado de la Tarea 4 y Sesión 16)

Pobreza nacional 27.6 % (± 0.1), residentes 108,664, 25 departamentos, urbana 24.8 %, rural 39.3 %,
extrema 5.5 %, Lima Metropolitana 28.2 %. Departamentos: `../mapeando-enaho/referencia_pobreza_departamento_2024.csv`.
