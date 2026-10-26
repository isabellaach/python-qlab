# Tarea 2 – Voces y documentos peruanos: del archivo escaneado al texto buscable

> **¿Pueden convertir documentos escaneados y entrevistas en audio en un archivo de texto estructurado y buscable?**

**Dashboard público:** https://python-qlab-8pczqqvrjifzjm6vcpi2qh.streamlit.app/

**Resultados de los modelos elegidos** (10 documentos y 10 clips transcritos a mano): **CER 0,10** (PaddleOCR-VL) · **WER 0,24** (Whisper turbo) · **Acuerdo LLM–humano: 6/20**

Pipeline de IA con modelos abiertos y locales que extrae texto de **25 documentos peruanos** (impresos, fotos y manuscritos) con OCR,
transcribe **28 clips de audio en español peruano (51 min)** con VAD y diarización, reemplaza los nombres de personas privadas por seudónimos,
extrae campos estructurados con un LLM y mide la calidad de cada modelo con **CER y WER** sobre referencias transcritas a mano.

| Archivo | Contenido |
|---|---|
| `01_extraccion.ipynb` | Descarga del corpus, OCR, ASR con VAD y diarización, seudonimización, limpieza, EDA (3 gráficos), validación y exportación |
| `02_evaluacion.ipynb` | Muestra de evaluación, CER/WER de la línea base y de los modelos alternativos, extracción con LLM, auditoría humana y decisión |
| `app.py` | Dashboard de Streamlit: lee los CSV ya calculados, no ejecuta modelos |
| `voz.py` | Módulo de la Sesión 13 del curso (copiado sin cambios, licencia MIT) |
| `datos/` | `documentos.csv`, `transcripciones.csv`, `extraccion_llm.csv`, `fuentes.csv` y `ejemplos/` (muestra ligera publicable) |
| `modelos/` | Configuración de los modelos y métricas finales (sin pesos) |
| `evidencias_ia/` | Capturas de la conversación completa con Claude Code |

## Corpus y fuentes

Fecha de extracción: **25 de octubre de 2026**. El detalle de cada archivo (URL, autor, licencia y cómo recuperarlo) está en `datos/fuentes.csv`.

| Corpus | Contenido | Fuente | Licencias |
|---|---|---|---|
| **A. Documentos** | 25 imágenes: 8 impresos nítidos (periódicos de 1834 a 1935, una proclama de 1808, un comunicado del Minsa de 2020, una carta a máquina), 8 fotos con perspectiva, brillo o sombras (placas, documentos en vitrina) y 9 manuscritos (cartas de presidentes del Perú del siglo XIX, César Vallejo, Miguel Grau) | Wikimedia Commons, incluidos fondos digitalizados de la Biblioteca Nacional del Perú y del Archivo General de la Nación de Argentina | 15 dominio público, 2 CC0, 7 CC BY-SA, 1 CC BY |
| **B. Audio** | 22 entrevistas de Commons (calle, ferias, conferencia de prensa y fiestas patronales; Lima, Cusco, Puno, Huancayo; 2022–2024) y 6 frases leídas de OpenSLR 73. Un clip con dos entrevistadas se usa para comprobar la diarización | Wikimedia Commons; OpenSLR 73 (*Crowdsourced high-quality Peruvian Spanish speech*, Google) | CC BY-SA 4.0 |

**Descartes:** 1 clip sin voz inteligible (confirmado al escucharlo). No hubo duplicados (hash SHA-256) ni documentos ilegibles.

**Ética y datos personales.** Los nombres de las 15 personas privadas que se escuchan en las entrevistas se reemplazaron por `PERSONA_n`
(30 menciones); la lista real se guarda fuera de Git. Los documentos solo nombran personajes históricos o públicos y no se seudonimizaron.
No hay DNI, teléfonos ni correos en el corpus. La búsqueda automática de nombres falló con una transcripción escrita toda en minúsculas;
lo detectó la revisión humana. Las URLs de `fuentes.csv` se mantienen porque la licencia CC BY-SA exige atribuir la fuente.
El dashboard solo reproduce audios e imágenes con licencia libre que no mencionan nombres de personas.

## Modelos

| Tarea | Línea base | Alternativa(s) |
|---|---|---|
| OCR | PaddleOCR 3.7 – PP-OCRv6 *medium* | PaddleOCR-VL 1.6 (visión-lenguaje, 0,9 B) |
| ASR | faster-whisper *small* (CPU, int8) | faster-whisper *large-v3-turbo* (CPU, int8), Qwen3-ASR 0.6B (GPU de la Mac) |
| Diarización | WeSpeaker ResNet34 (pyannote) + agrupamiento jerárquico | — |
| Extracción | Qwen2.5-3B-Instruct, local, decodificación greedy | — |

Configuración completa en `modelos/configuracion.json`.

## Resultados

Sobre los mismos 10 documentos y 10 clips transcritos a mano (menos es mejor):

| OCR | CER global | Impresos | Fotos | Manuscritos | s/página |
|---|---|---|---|---|---|
| PP-OCRv6 (base) | 11,1 % | 3,6 % | 10,1 % | 36,4 % | 3,0 |
| **PaddleOCR-VL 1.6** (elegido) | **9,6 %** | 4,1 % | 10,4 % | **25,8 %** | 5,5 |

| ASR | WER global | Lectura limpia | Calle | Feria | Fiesta patronal | Factor tiempo real |
|---|---|---|---|---|---|---|
| faster-whisper small (base) | 34,9 % | 4,3 % | 26,2 % | 31,6 % | 42,1 % | 0,15 |
| **faster-whisper large-v3-turbo** (elegido) | **23,6 %** | 0 % | 18,4 % | 33,8 % | **23,6 %** | 0,27 |
| Qwen3-ASR 0.6B | 30,2 % | 0 % | 19,7 % | 32,0 % | 36,1 % | 0,10 |

La justificación completa (precisión, costo y latencia) está al final de `02_evaluacion.ipynb`.

## Hallazgos

1. **El OCR clásico casi no lee los manuscritos.** Los manuscritos son el 36 % de los documentos, pero solo aportan el 11 % del texto que lee PP-OCRv6,
   con un CER de 36 % frente a 4 % en los impresos. Un modelo de visión-lenguaje (PaddleOCR-VL) baja ese error a 26 %; en impresos y fotos no hay diferencia.
2. **El ruido pesa más que el acento.** Con lectura limpia los tres modelos de ASR transcriben el español peruano casi sin errores (0–4 %), pero en la
   fiesta patronal con música el modelo pequeño llega a 42 % de WER. Un modelo más grande (Whisper turbo) reduce ese error a la mitad.

## Limitaciones

1. **El VAD falla con audio muy fuerte y ruidoso.** En dos clips de fiesta patronal y feria, el detector de voz reconoció menos del 1 % de voz aunque
   hay una entrevista completa. Se agregó una regla de respaldo (transcribir sin VAD si detecta menos del 30 %), pero esos clips quedan expuestos a
   alucinaciones y se revisaron a mano.
2. **La diarización sobreestima el número de hablantes** en algunos clips de calle (hasta 8 en una entrevista de 2 o 3 personas), porque el ruido
   y los cambios de distancia al micrófono cambian la "huella" de una misma voz. No se ajustó el umbral para no adaptarlo a los resultados.
3. **La muestra de evaluación es pequeña** (10 documentos y 10 clips): sirve para comparar modelos, no para estimar con precisión el error de cada tipo.

## Cómo ejecutarlo

Los notebooks usan el entorno del repositorio del curso ([d2cml-ai/Data-Science-Python](https://github.com/d2cml-ai/Data-Science-Python)):

```bash
# en el repositorio del curso
uv sync --group docai
uv pip install --python .venv/bin/python soundfile jiwer rapidfuzz accelerate librosa "kaleido>=1"

# en esta carpeta (tarea_2/)
~/ruta/al/curso/.venv/bin/jupyter lab 01_extraccion.ipynb
```

`01_extraccion.ipynb` descarga de nuevo todo el corpus a `datos/raw/` (no versionado) a partir de las fuentes registradas.

El dashboard solo necesita tres paquetes:

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Uso de inteligencia artificial

El desarrollo se hizo con **Claude Code** como asistente. Cada paso se discutió y aprobó antes de ejecutarse; la selección del corpus,
la lista de nombres a seudonimizar, las transcripciones manuales de referencia y la auditoría del LLM las hizo o revisó la autora.
Las capturas completas de la conversación están en `evidencias_ia/`.
