"""Dashboard – Tarea 1: Noticias peruanas, del titular al clasificador.

Ejecutar desde la carpeta tarea_1/:
    streamlit run app.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

BASE = Path(__file__).parent
DATOS = BASE / "datos" / "noticias.csv"
MODELO = BASE / "modelo"
METRICAS = MODELO / "metricas.json"
EMBEDDINGS = BASE / "datos" / "embeddings.npy"
EMB_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
NOMBRES = {"politica": "Política", "economia": "Economía",
           "deportes": "Deportes", "ciencia_tecnologia": "Ciencia y tecnología"}

st.set_page_config(page_title="Clasificador de noticias peruanas", page_icon="🗞️", layout="wide")


@st.cache_data
def cargar_datos():
    return pd.read_csv(DATOS).fillna({"bajada": ""})


@st.cache_data
def cargar_metricas():
    return json.loads(METRICAS.read_text(encoding="utf-8")) if METRICAS.exists() else {}


@st.cache_resource
def cargar_clasificador():
    from transformers import pipeline
    return pipeline("text-classification", model=str(MODELO), tokenizer=str(MODELO), top_k=None)


@st.cache_data
def cargar_embeddings():
    return np.load(EMBEDDINGS)


@st.cache_resource
def cargar_modelo_embeddings():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(EMB_MODEL)


def modelo_disponible():
    return any(MODELO.glob("*.safetensors")) or any(MODELO.glob("*.bin"))


df = cargar_datos()
met = cargar_metricas()

# ---------- Encabezado ----------
st.title("🗞️ ¿Pueden convertir titulares peruanos en un clasificador de noticias?")
st.markdown(
    f"""
**Sí.** Se recolectaron **{len(df)} noticias reales de El Comercio** desde sus sitemaps oficiales
({df['fecha'].min()} a {df['fecha'].max()}), un LLM local (**Qwen2.5-3B-Instruct**) las etiquetó en 4 categorías
(supervisión débil) y con esas etiquetas se hizo fine-tuning de **DistilBERT multilingüe**.
El modelo se evaluó en un **conjunto de test reservado** (15%) contra la sección editorial del diario.
Más abajo puedes escribir cualquier titular y ver qué categoría predice.
"""
)

# ---------- Barra lateral: filtros ----------
st.sidebar.header("Filtros")
medios = sorted(df["medio"].unique())
sel_medios = st.sidebar.multiselect("Medio", medios, default=medios)
cats = [c for c in NOMBRES if c in df["etiqueta"].unique()]
sel_cats = st.sidebar.multiselect("Categoría", cats, default=cats, format_func=NOMBRES.get)
filtrado = df[df["medio"].isin(sel_medios) & df["etiqueta"].isin(sel_cats)]
st.sidebar.caption(f"{len(filtrado)} de {len(df)} noticias seleccionadas")

# ---------- Indicadores ----------
c1, c2, c3 = st.columns(3)
c1.metric("Noticias recolectadas", f"{len(df)}",
          delta=f"{len(filtrado)} con los filtros actuales", delta_color="off")
f1 = met.get("f1_macro_test")
f1_zs = met.get("f1_zero_shot_40")
c2.metric("F1 macro en test (DistilBERT)", f"{f1:.3f}" if f1 is not None else "—",
          delta=f"{f1 - f1_zs:+.3f} vs. zero-shot" if f1 is not None and f1_zs is not None else None)
acu, n_ok = met.get("acuerdo_llm_humano"), met.get("acuerdo_llm_humano_n")
c3.metric("Concordancia LLM vs. auditoría humana", f"{acu:.0%}" if acu is not None else "—",
          delta=f"{n_ok}/20 casos revisados" if n_ok is not None else None, delta_color="off")

# ---------- Gráfico y tabla ----------
st.subheader("Distribución de categorías")
if filtrado.empty:
    st.info("No hay noticias con los filtros seleccionados.")
else:
    conteo = (filtrado["etiqueta"].map(NOMBRES).value_counts()
              .rename_axis("Categoría").reset_index(name="Noticias"))
    fig = px.bar(conteo, x="Categoría", y="Noticias", color="Categoría", text="Noticias",
                 title=f"{len(filtrado)} noticias seleccionadas por categoría")
    fig.update_layout(showlegend=False)
    st.plotly_chart(fig, width="stretch")

st.subheader("Explorar las noticias")
st.dataframe(filtrado, width="stretch", hide_index=True,
             column_config={"url": st.column_config.LinkColumn("url")})
st.download_button("⬇️ Descargar CSV filtrado", filtrado.to_csv(index=False).encode("utf-8"),
                   file_name="noticias_filtradas.csv", mime="text/csv")

if met.get("comparativa"):
    with st.expander("Comparativa de modelos en test"):
        st.dataframe(pd.DataFrame(met["comparativa"]), width="stretch", hide_index=True)

# ---------- Probador en vivo ----------
st.divider()
st.subheader("🔮 Probador en vivo")
titular = st.text_input("Escribe o pega un titular",
                        placeholder="Ej.: Congreso aprueba nuevo retiro de fondos de AFP")
if st.button("Clasificar titular", type="primary"):
    if not titular.strip():
        st.warning("Escribe un titular primero.")
    elif not modelo_disponible():
        st.error("No se encontraron los pesos del modelo en `modelo/`. "
                 "Ejecuta `02_clasificacion.ipynb` para entrenarlo y guardarlo.")
    else:
        with st.spinner("Clasificando..."):
            pred = cargar_clasificador()(titular.strip())
            pred = pred[0] if isinstance(pred[0], list) else pred
        probs = pd.DataFrame(pred).sort_values("score", ascending=False)
        top = probs.iloc[0]
        st.success(f"Categoría predicha: **{NOMBRES.get(top['label'], top['label'])}** "
                   f"· confianza **{top['score']:.1%}**")
        probs["Categoría"] = probs["label"].map(NOMBRES)
        fig = px.bar(probs, x="score", y="Categoría", orientation="h", range_x=[0, 1],
                     text=probs["score"].map("{:.1%}".format), title="Probabilidad por categoría")
        fig.update_layout(yaxis={"categoryorder": "total ascending"}, xaxis_title="Probabilidad")
        st.plotly_chart(fig, width="stretch")

# ---------- Innovación: buscador semántico ----------
st.divider()
st.subheader("🔎 Buscador semántico")
st.markdown("Encuentra las noticias del dataset más parecidas **en significado** a lo que escribas, "
            "aunque no compartan las mismas palabras (embeddings + similitud coseno).")
consulta = st.text_input("¿Qué tema buscas?", placeholder="Ej.: riesgos de la inteligencia artificial")
k = st.slider("Número de resultados", 3, 10, 5)
if st.button("Buscar noticias similares"):
    if not consulta.strip():
        st.warning("Escribe un tema o titular primero.")
    elif not EMBEDDINGS.exists():
        st.error("No se encontró `datos/embeddings.npy`. Ejecuta `03_buscador_semantico.ipynb`.")
    else:
        with st.spinner("Buscando..."):
            emb = cargar_embeddings()
            q = cargar_modelo_embeddings().encode([consulta.strip()], normalize_embeddings=True)[0]
            sim = emb @ q
            top = np.argsort(-sim)[:k]
        res = df.iloc[top][["titular", "etiqueta", "fecha", "url"]].assign(similitud=sim[top].round(3))
        res["etiqueta"] = res["etiqueta"].map(NOMBRES)
        if sim[top[0]] < 0.5:
            st.info("Ninguna noticia es muy parecida: es posible que el tema no aparezca en el dataset.")
        st.dataframe(res, width="stretch", hide_index=True,
                     column_config={"url": st.column_config.LinkColumn("url"),
                                    "similitud": st.column_config.ProgressColumn("similitud", min_value=0, max_value=1, format="%.2f")})

st.caption("Tarea 1 – Data Science con Python · Datos: El Comercio (elcomercio.pe), uso académico.")
