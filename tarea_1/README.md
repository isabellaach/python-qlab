# Tarea 1 – Noticias peruanas: del titular al clasificador

**Pregunta guía:** ¿Pueden convertir titulares peruanos en un clasificador de noticias?

**Medio elegido:** Opción B – El Comercio (`elcomercio.pe`)

> 🚧 En construcción. El reporte final se completa en la Parte 3.

## Estructura

```text
tarea_1/
├── 01_recoleccion.ipynb       # Scraping, limpieza y EDA
├── 02_clasificacion.ipynb     # Modelado, LLM y evaluación
├── app.py                     # Aplicación interactiva Streamlit
├── requirements.txt           # Dependencias
├── datos/
│   ├── raw/                   # Respaldo crudo de los sitemaps
│   ├── noticias.csv           # Dataset recolectado
│   └── etiquetas_llm.csv      # Clasificaciones generadas por el LLM
└── modelo/                    # Configuración y tokenizer del modelo
```
