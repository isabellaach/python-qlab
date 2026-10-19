# Tarea 1 – Noticias peruanas: del titular al clasificador

## 1. Pregunta del proyecto

> **¿Pueden convertir titulares peruanos en un clasificador de noticias?**

**Sí.** Con 384 noticias reales de El Comercio, etiquetadas por un LLM local y usadas para hacer fine-tuning de DistilBERT, el clasificador alcanza un **F1 macro de 0.850 en un test reservado**, frente a **0.597** del modelo zero-shot sin entrenamiento. Además, clasifica un titular en unos 5 ms.

| Resultado | Valor |
| :--- | :--- |
| F1 macro en test (DistilBERT fine-tuned) | **0.850** (accuracy 0.845, 58 noticias) |
| F1 macro zero-shot (línea base, 40 titulares) | 0.597 |
| Acuerdo LLM vs. auditoría humana | **19/20 (95%)** |
| Acuerdo LLM vs. sección editorial (384 noticias) | 84.6% |

## 2. Medio y fechas de extracción

- **Opción B – El Comercio** (`elcomercio.pe`).
- **Fecha de descarga:** 18 de octubre de 2026.
- **Fechas de publicación cubiertas:** del 6 al 18 de octubre de 2026.
- **Fuente:** sitemaps oficiales de noticias por sección (`/sitemap/news/<seccion>/` y `/sitemap/web/<seccion>/`), declarados en el propio `robots.txt`. El RSS clásico (`/arcio/rss/...`) responde 301 y no trae ítems. La bajada se tomó de la `meta description` de cada nota.
- **Scraping respetuoso:** User-Agent descriptivo, pausa de 1.5 s entre solicitudes, un solo reintento y respaldo crudo en `datos/raw/`.
- **Volumen:** 399 notas descargadas, de las que quedaron **384** tras la limpieza (15 descartadas por pertenecer a secciones fuera de las 4 categorías: opinión, ecdata, autos, BBC Mundo y El Dominical).

| Categoría | Noticias |
| :--- | :---: |
| economia | 99 |
| deportes | 98 |
| ciencia_tecnologia | 95 |
| politica | 92 |

## Metodología

1. **`01_recoleccion.ipynb`**: scraping, limpieza, mapeo `seccion_original` → categoría, EDA con 3 gráficos Plotly y exportación de `datos/noticias.csv`.
2. **`02_clasificacion.ipynb`**:
   - Línea base zero-shot con `Recognai/bert-base-spanish-wwm-cased-xnli`.
   - Supervisión débil con **`Qwen/Qwen2.5-3B-Instruct`** ejecutado localmente, sin API. La confianza se obtiene de la probabilidad de cada una de las 4 etiquetas, por lo que el LLM no puede inventar categorías. Resultado en `datos/etiquetas_llm.csv`.
   - Auditoría humana de 20 casos (`datos/auditoria_humana.csv`).
   - Split estratificado 70/15/15 con `random_state=42`.
   - Fine-tuning de `distilbert-base-multilingual-cased` (3 épocas, batch 8, mejor época por F1 macro) **con las etiquetas del LLM**. La evaluación se hace contra la **sección editorial** del diario, independiente del LLM.
3. **`app.py`**: dashboard Streamlit con filtros, métricas, gráfico, tabla descargable y probador en vivo.

| Modelo | F1 macro test | Latencia / titular | Parámetros |
| :--- | :---: | :---: | :---: |
| Zero-shot (BETO-XNLI) | 0.641 | ≈ 40 ms | 110 M |
| LLM débil (Qwen2.5-3B, titular + bajada) | 0.859 | ≈ 750–1 000 ms | 3 086 M |
| **DistilBERT fine-tuned** | **0.850** | **≈ 5 ms** | 135 M |

**Modelo elegido para producción:** DistilBERT fine-tuned. Tiene casi el mismo F1 que el LLM, pero es más de 100 veces más rápido y 23 veces más pequeño, y corre en CPU sin costo por consulta.

## 3. Hallazgos analíticos

1. **El "alumno" alcanza al "profesor".** DistilBERT, entrenado solo con las etiquetas de Qwen y viendo **solo el titular**, logra prácticamente el mismo F1 que el LLM que lee titular y bajada (0.850 vs. 0.859). Un LLM puede reemplazar el etiquetado manual y transferir su conocimiento a un modelo pequeño y rápido.
2. **Tecnología se confunde con economía.** `deportes` (F1 0.96) y `politica` (F1 0.93) tienen vocabulario muy propio (clubes, torneos; Congreso, Senado). `ciencia_tecnologia` es la peor (F1 0.75, recall 0.60): la sección *Tecnología* de El Comercio incluye **negocios de empresas tech y ecología/medio ambiente** (*"Finlandia frena centros de datos de Google"*, *"minería ilegal en Madre de Dios"*), que el modelo manda a `economia`. El LLM ya cometía esta confusión (18 de 95 noticias de tecnología etiquetadas como economía) y el modelo la heredó.

Hallazgo adicional del EDA: deportes publicó sus 98 notas en solo 3 días, mientras ciencia y tecnología necesitó 13. Además, política usa los titulares más largos (mediana de 108 caracteres) porque suelen ser citas textuales.

## 4. Limitaciones técnicas

1. **Etiquetas débiles y poco volumen.** El modelo aprende de las etiquetas del LLM, que coinciden con la sección del diario en el 84.6% de los casos, así que hereda sus errores. Además, el test tiene solo 58 noticias: un acierto más o menos mueve el F1 en ~0.02, y las métricas tienen bastante incertidumbre.
2. **Un solo medio y una ventana corta de tiempo.** Los datos cubren 13 días de El Comercio, dominados por los temas de esas semanas (elecciones municipales, facultades legislativas, Liga 1). El modelo podría rendir peor con otros medios, otros estilos de titular o temas nuevos. Por otro lado, los pesos del modelo (≈ 540 MB) no se suben a GitHub por el límite de 100 MB, así que para usar el dashboard hay que ejecutar antes `02_clasificacion.ipynb`.

## 5. Cómo ejecutar en local

Requisitos: Python 3.14. Se recomienda una Mac con Apple Silicon o una GPU para el notebook 2 (en CPU también funciona, pero más lento).

```bash
# 1. Entrar a la carpeta del trabajo
cd tarea_1

# 2. Crear y activar un entorno virtual
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. (Opcional) Volver a ejecutar los notebooks
#    01 reutiliza el respaldo de datos/raw/; 02 reutiliza datos/etiquetas_llm.csv
jupyter nbconvert --to notebook --execute --inplace 01_recoleccion.ipynb
jupyter nbconvert --to notebook --execute --inplace 02_clasificacion.ipynb   # entrena y guarda modelo/

# 5. Lanzar el dashboard
streamlit run app.py
```

El dashboard se abre en `http://localhost:8501`. **Ejecución local comprobada.**

## Estructura

```text
tarea_1/
├── 01_recoleccion.ipynb       # Scraping, limpieza y EDA
├── 02_clasificacion.ipynb     # Zero-shot, LLM, fine-tuning y evaluación
├── app.py                     # Dashboard Streamlit
├── requirements.txt           # Dependencias con versiones exactas
├── README.md
├── .gitignore                 # Excluye pesos del modelo y entorno virtual
├── datos/
│   ├── raw/                   # Respaldo crudo: robots.txt, sitemaps y notas (jsonl)
│   ├── noticias.csv           # 384 noticias, 7 columnas
│   ├── etiquetas_llm.csv      # Etiquetas de Qwen2.5-3B
│   └── auditoria_humana.csv   # 20 casos revisados manualmente
└── modelo/                    # config, tokenizer y metricas.json (pesos excluidos)
```
