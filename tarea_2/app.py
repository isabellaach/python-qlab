"""Tarea 2 – Dashboard: documentos y voces peruanas convertidos en texto buscable.

Solo lee los resultados ya calculados en los notebooks (CSV y JSON): no ejecuta OCR, ASR ni LLM en vivo.

    streamlit run app.py
"""
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

AQUI = Path(__file__).parent
DATOS, MODELOS, EJEMPLOS = AQUI / "datos", AQUI / "modelos", AQUI / "datos" / "ejemplos"
COLOR_TIPO = {"impreso": "#2a78d6", "foto": "#eb6834", "manuscrito": "#0ca30c"}

st.set_page_config(page_title="Del archivo escaneado al texto buscable", page_icon="🎙️", layout="wide")


# ───────────────────────────────────────────────────────── carga de datos
@st.cache_data
def cargar():
    docs = pd.read_csv(DATOS / "documentos.csv", keep_default_na=False)
    clips = pd.read_csv(DATOS / "transcripciones.csv", keep_default_na=False)
    fuentes = pd.read_csv(DATOS / "fuentes.csv", keep_default_na=False)
    llm = pd.read_csv(DATOS / "extraccion_llm.csv", keep_default_na=False) if (DATOS / "extraccion_llm.csv").exists() else pd.DataFrame()
    metricas = json.loads((MODELOS / "metricas.json").read_text(encoding="utf-8")) if (MODELOS / "metricas.json").exists() else {}
    comp_ocr = pd.read_csv(MODELOS / "comparacion_ocr.csv", keep_default_na=False) if (MODELOS / "comparacion_ocr.csv").exists() else pd.DataFrame()
    comp_asr = pd.read_csv(MODELOS / "comparacion_asr.csv", keep_default_na=False) if (MODELOS / "comparacion_asr.csv").exists() else pd.DataFrame()
    clips["minutos"] = clips["duracion_seg"] / 60
    docs["caracteres"] = docs["texto_ocr"].str.len()
    clips["palabras"] = clips["texto_asr"].str.replace(r"\[HABLANTE_\d+\]", " ", regex=True).str.split().str.len()
    return docs, clips, fuentes, llm, metricas, comp_ocr, comp_asr


docs, clips, fuentes, llm, metricas, comp_ocr, comp_asr = cargar()
campos_llm = {r.id: json.loads(r.campos_json) for r in llm.itertuples() if r.campos_json} if not llm.empty else {}


def campos(id_):
    "Campos estructurados del LLM para un documento o clip."
    c = campos_llm.get(id_)
    if not c:
        st.caption("Sin extracción del LLM para este registro.")
        return
    st.json(c)


def resaltar(texto, consulta):
    "Pone en negrita las apariciones de la búsqueda (sin distinguir mayúsculas)."
    if not consulta:
        return texto
    import re
    return re.sub(f"({re.escape(consulta)})", r"**\1**", texto, flags=re.I)


def descargar(df, nombre):
    st.download_button("⬇️ Descargar tabla filtrada (CSV)", df.to_csv(index=False).encode("utf-8"),
                       file_name=nombre, mime="text/csv")


# ───────────────────────────────────────────────────────── encabezado
st.title("¿Pueden los documentos escaneados y las entrevistas peruanas convertirse en texto buscable?")
st.markdown(
    f"""Pipeline de IA con modelos abiertos sobre **{len(docs)} documentos peruanos** (impresos, fotos y manuscritos de 1808 a 2020)
y **{len(clips)} clips de audio** en español peruano ({clips['minutos'].sum():.0f} minutos): OCR con **PaddleOCR**, transcripción con
**faster-whisper** (VAD + diarización), seudonimización de nombres de personas privadas y extracción de campos con un **LLM local** (Qwen2.5-3B).
La calidad se mide con **CER/WER** sobre 10 documentos y 10 clips transcritos a mano. Fuentes: Wikimedia Commons y OpenSLR 73, con licencias libres."""
)

cer = metricas.get("cer", {})
wer = metricas.get("wer", {})
acuerdo = metricas.get("acuerdo_llm", {})
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Documentos procesados", len(docs))
c2.metric("Minutos de audio transcritos", f"{clips['minutos'].sum():.1f}")
c3.metric(f"CER · {metricas.get('modelo_ocr_elegido', 'OCR')}",
          f"{cer[metricas['modelo_ocr_elegido']]['GLOBAL']:.1%}" if metricas.get("modelo_ocr_elegido") in cer else "—")
c4.metric(f"WER · {metricas.get('modelo_asr_elegido', 'ASR')}",
          f"{wer[metricas['modelo_asr_elegido']]['GLOBAL']:.1%}" if metricas.get("modelo_asr_elegido") in wer else "—")
c5.metric("Acuerdo LLM vs. auditoría humana",
          f"{acuerdo['correctas'] / acuerdo['total']:.0%}" if acuerdo.get("total") else "—",
          f"{acuerdo['correctas']}/{acuerdo['total']} extracciones" if acuerdo.get("total") else None, delta_color="off")

tab_res, tab_docs, tab_audio, tab_eval = st.tabs(["📊 Resumen", "📄 Documentos", "🎧 Audios", "🧪 Evaluación de modelos"])

# ───────────────────────────────────────────────────────── resumen
with tab_res:
    izq, der = st.columns(2)
    reparto = docs.groupby("tipo").agg(documentos=("id", "count"), caracteres=("caracteres", "sum")).reindex(["impreso", "foto", "manuscrito"])
    reparto = (100 * reparto / reparto.sum()).round(1).reset_index().melt(id_vars="tipo", var_name="medida", value_name="porcentaje")
    reparto["medida"] = reparto["medida"].map({"documentos": "% de los documentos", "caracteres": "% del texto leído por el OCR"})
    fig = px.bar(reparto, x="tipo", y="porcentaje", color="medida", barmode="group", text="porcentaje",
                 color_discrete_sequence=["#c3c2b7", "#2a78d6"], labels={"tipo": "", "porcentaje": "%", "medida": ""},
                 title="Los manuscritos son un tercio del corpus pero el OCR lee muy poco de ellos")
    fig.update_traces(texttemplate="%{text:.0f} %", textposition="outside")
    fig.update_layout(legend=dict(orientation="h", y=-0.15))
    izq.plotly_chart(fig, width="stretch")

    fig = px.bar(clips.sort_values("duracion_seg", ascending=False), x="id", y="duracion_seg", color="condicion",
                 hover_data=["n_hablantes", "fuente"], labels={"id": "", "duracion_seg": "segundos", "condicion": "Condición"},
                 title="Las entrevistas en la calle concentran la mayor parte del audio")
    der.plotly_chart(fig, width="stretch")

    st.subheader("Fuentes y licencias")
    st.dataframe(fuentes[["id", "modalidad", "tipo", "licencia", "autor", "fuente_url"]], width="stretch", hide_index=True,
                 column_config={"fuente_url": st.column_config.LinkColumn("fuente")})

# ───────────────────────────────────────────────────────── documentos
with tab_docs:
    f1, f2, f3 = st.columns([1, 1, 2])
    tipos = f1.multiselect("Tipo de documento", ["impreso", "foto", "manuscrito"], default=["impreso", "foto", "manuscrito"])
    modelos_ocr = ["PP-OCRv6 (base)"] + (sorted(set(comp_ocr["modelo"]) - {"PP-OCRv6 (base)"}) if not comp_ocr.empty else [])
    modelo_ocr = f2.selectbox("Modelo OCR", modelos_ocr,
                              help="PP-OCRv6 leyó los 25 documentos. Los otros modelos solo se ejecutaron sobre la muestra de evaluación.")
    consulta = f3.text_input("Buscar palabras en el texto OCR", placeholder="por ejemplo: Lima, independencia, señor…")

    tabla = docs[docs["tipo"].isin(tipos)][["id", "tipo", "fuente", "texto_ocr", "confianza_media", "caracteres"]].copy()
    if modelo_ocr != "PP-OCRv6 (base)":
        otros = comp_ocr[comp_ocr["modelo"] == modelo_ocr].set_index("id")["texto"]
        tabla = tabla[tabla["id"].isin(otros.index)]
        tabla["texto_ocr"] = tabla["id"].map(otros)
        tabla["caracteres"] = tabla["texto_ocr"].str.len()
    if consulta:
        tabla = tabla[tabla["texto_ocr"].str.contains(consulta, case=False, regex=False)]
    st.caption(f"{len(tabla)} documentos · modelo: {modelo_ocr}")

    if not tabla.empty:
        fig = px.box(tabla, x="tipo", y="caracteres", color="tipo", points="all", hover_data=["id"],
                     color_discrete_map=COLOR_TIPO, category_orders={"tipo": ["impreso", "foto", "manuscrito"]},
                     title="Cantidad de texto leído por documento", labels={"caracteres": "caracteres", "tipo": ""})
        fig.update_layout(showlegend=False, height=330)
        st.plotly_chart(fig, width="stretch")
    st.dataframe(tabla, width="stretch", hide_index=True,
                 column_config={"texto_ocr": st.column_config.TextColumn("texto OCR", width="large")})
    descargar(tabla, "documentos_filtrados.csv")

    st.subheader("Explorador de documentos")
    if tabla.empty:
        st.info("Ningún documento coincide con los filtros.")
    else:
        id_doc = st.selectbox("Documento", tabla["id"], format_func=lambda i: f"{i} · {docs.set_index('id').at[i, 'tipo']}")
        fila = docs.set_index("id").loc[id_doc]
        img = EJEMPLOS / f"{id_doc}.jpg"
        a, b = st.columns([1, 1])
        with a:
            if img.exists():
                st.image(str(img), caption=f"{id_doc} · {fila['fuente']}")
            else:
                st.info("La imagen de este documento no se incluye en el dashboard (solo una selección ligera de ejemplos). "
                        f"Puedes verla en su fuente: {fuentes.set_index('id').at[id_doc, 'fuente_url']}")
            st.markdown("**Campos extraídos por el LLM**")
            campos(id_doc)
        with b:
            texto = tabla.set_index("id").at[id_doc, "texto_ocr"]
            st.markdown(f"**Texto OCR ({modelo_ocr})**")
            st.markdown(resaltar(texto, consulta).replace("\n", "  \n"))
            if fila["texto_referencia"]:
                with st.expander("Transcripción manual (referencia)"):
                    st.text(fila["texto_referencia"])
                if not comp_ocr.empty:
                    st.dataframe(comp_ocr[comp_ocr["id"] == id_doc][["modelo", "cer"]].assign(cer=lambda d: d["cer"].map("{:.1%}".format)),
                                 hide_index=True)

# ───────────────────────────────────────────────────────── audios
with tab_audio:
    f1, f2, f3, f4 = st.columns([1, 1, 1, 2])
    condiciones = sorted(clips["condicion"].unique())
    cond = f1.multiselect("Condición de grabación", condiciones, default=condiciones)
    modelos_asr = ["faster-whisper large-v3-turbo"] + (sorted(set(comp_asr["modelo"]) - {"faster-whisper large-v3-turbo"}) if not comp_asr.empty else [])
    modelo_asr = f2.selectbox("Modelo ASR", modelos_asr,
                              help="Whisper turbo transcribió todo el corpus. Los otros modelos solo se ejecutaron sobre la muestra de evaluación.")
    dur = f3.slider("Duración (segundos)", 0, int(clips["duracion_seg"].max()) + 1, (0, int(clips["duracion_seg"].max()) + 1))
    consulta_a = f4.text_input("Buscar palabras en las transcripciones", placeholder="por ejemplo: Perú, fiesta, independencia…")

    tabla_a = clips[clips["condicion"].isin(cond) & clips["duracion_seg"].between(*dur)][
        ["id", "condicion", "fuente", "duracion_seg", "n_hablantes", "palabras", "texto_asr"]].copy()
    if modelo_asr != "faster-whisper large-v3-turbo":
        otros = comp_asr[comp_asr["modelo"] == modelo_asr].set_index("id")["texto"]
        tabla_a = tabla_a[tabla_a["id"].isin(otros.index)]
        tabla_a["texto_asr"] = tabla_a["id"].map(otros)
    if consulta_a:
        tabla_a = tabla_a[tabla_a["texto_asr"].str.contains(consulta_a, case=False, regex=False)]
    st.caption(f"{len(tabla_a)} clips · {tabla_a['duracion_seg'].sum() / 60:.1f} min · modelo: {modelo_asr}")

    if not tabla_a.empty:
        fig = px.scatter(tabla_a, x="duracion_seg", y="palabras", color="condicion", size="n_hablantes", hover_data=["id"],
                         title="Palabras transcritas según la duración del clip (tamaño = hablantes detectados)",
                         labels={"duracion_seg": "segundos", "palabras": "palabras", "condicion": "Condición"})
        fig.update_layout(height=360)
        st.plotly_chart(fig, width="stretch")
    st.dataframe(tabla_a, width="stretch", hide_index=True,
                 column_config={"texto_asr": st.column_config.TextColumn("transcripción (seudonimizada)", width="large")})
    descargar(tabla_a, "transcripciones_filtradas.csv")

    st.subheader("Explorador de audios")
    if tabla_a.empty:
        st.info("Ningún clip coincide con los filtros.")
    else:
        id_clip = st.selectbox("Clip", tabla_a["id"], format_func=lambda i: f"{i} · {clips.set_index('id').at[i, 'condicion']}")
        fila = clips.set_index("id").loc[id_clip]
        a, b = st.columns([1, 1])
        with a:
            audio = EJEMPLOS / f"{id_clip}.ogg"
            if audio.exists():
                st.audio(str(audio), format="audio/ogg")
                st.caption(f"{fila['fuente']} · reproducción permitida por la licencia; el clip no menciona nombres de personas.")
            else:
                st.info("Este audio no se publica en el dashboard (menciona nombres de personas o es de los más pesados). "
                        "Su transcripción seudonimizada sí está disponible.")
            st.markdown(f"**{fila['duracion_seg']:.0f} s · {fila['n_hablantes']} hablante(s) detectado(s) · idioma: {fila['idioma']}**")
            st.markdown("**Campos extraídos por el LLM**")
            campos(id_clip)
        with b:
            texto = tabla_a.set_index("id").at[id_clip, "texto_asr"]
            st.markdown(f"**Transcripción ({modelo_asr})**")
            for bloque in [t for t in texto.split("[HABLANTE_") if t.strip()]:
                if "]" in bloque[:4]:
                    n, resto = bloque.split("]", 1)
                    st.markdown(f"🗣️ **Hablante {n}:** {resaltar(resto.strip(), consulta_a)}")
                else:
                    st.markdown(resaltar(bloque.strip(), consulta_a))
            if not comp_asr.empty and id_clip in set(comp_asr["id"]):
                with st.expander("Comparar modelos en este clip"):
                    comp = comp_asr[comp_asr["id"] == id_clip]
                    st.dataframe(comp[["modelo", "wer", "segundos"]].assign(wer=lambda d: d["wer"].map(lambda v: f"{v:.1%}" if v != "" else "—")),
                                 hide_index=True)
                    for r in comp.itertuples():
                        st.markdown(f"**{r.modelo}:** {r.texto}")
                    if fila["texto_referencia"]:
                        st.markdown(f"**Referencia manual:** {fila['texto_referencia']}")

# ───────────────────────────────────────────────────────── evaluación
with tab_eval:
    if not metricas:
        st.info("Las métricas se generan en 02_evaluacion.ipynb.")
    else:
        st.markdown("Errores medidos sobre **los mismos 10 documentos y 10 clips** transcritos a mano. Menos es mejor.")
        izq, der = st.columns(2)
        t_cer = pd.DataFrame(cer).T.reset_index(names="modelo").melt(id_vars="modelo", var_name="tipo", value_name="CER")
        fig = px.bar(t_cer, x="tipo", y="CER", color="modelo", barmode="group", text_auto=".0%",
                     title="CER por tipo de documento", labels={"tipo": ""})
        fig.update_yaxes(tickformat=".0%")
        izq.plotly_chart(fig, width="stretch")
        t_wer = pd.DataFrame(wer).T.reset_index(names="modelo").melt(id_vars="modelo", var_name="condición", value_name="WER")
        fig = px.bar(t_wer, x="condición", y="WER", color="modelo", barmode="group", text_auto=".0%",
                     title="WER por condición de grabación", labels={"condición": ""})
        fig.update_yaxes(tickformat=".0%")
        der.plotly_chart(fig, width="stretch")
        if metricas.get("latencia_asr"):
            lat = pd.DataFrame(metricas["latencia_asr"].items(), columns=["modelo", "factor de tiempo real"])
            fig = px.bar(lat, x="modelo", y="factor de tiempo real", text_auto=".2f",
                         title="Latencia del ASR: segundos de proceso por segundo de audio (menos es más rápido)")
            st.plotly_chart(fig, width="stretch")
        if metricas.get("decision"):
            st.subheader("Decisión")
            st.markdown(metricas["decision"])

st.caption("Tarea 2 · Ciencia de Datos con Python · Los nombres de personas privadas se reemplazaron por PERSONA_n. "
           "Documentos: Wikimedia Commons (dominio público, CC0, CC BY, CC BY-SA). Audio: Wikimedia Commons y OpenSLR 73 (CC BY-SA 4.0).")
