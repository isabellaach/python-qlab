"""Dashboard: ¿a quién alcanzará el fuego en 24-72 h?  ->  streamlit run app.py"""
import json
from pathlib import Path

import folium
import geopandas as gpd
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

RES = Path(__file__).parent / "resultados"
st.set_page_config(page_title="Alerta de evacuación por incendios", layout="wide")

inc = pd.read_csv(RES / "exposicion_incendios.csv")
corr = gpd.read_file(RES / "corredores.geojson")
dist = pd.read_csv(RES / "distritos_en_alerta.csv")
pron = pd.read_csv(RES / "pronostico_72h.csv", parse_dates=["time"])
focos = pd.read_csv(RES / "focos_peru.csv", parse_dates=["fecha_utc"])
dnbr = json.load(open(next(RES.glob("dnbr_*.json"))))
corte = focos.fecha_utc.max()
COLOR = {"R": "#d7301f", "Á": "#fd8d3c", "V": "#41ab5d"}
inc["color"] = inc.semaforo.str[0].map(COLOR)

st.title("🔥 ¿Qué poblaciones deben prepararse para evacuar en las próximas 24–72 h?")
st.caption(f"Focos VIIRS (NASA FIRMS) al {corte:%d/%m/%Y %H:%M} UTC · pronóstico Open-Meteo desde "
           f"{pron.time.min():%d/%m %H:%M} (Lima) · población WorldPop 2020 · Sentinel-2 L2A. "
           "Herramienta académica: no reemplaza a INDECI, COEN ni SERFOR.")

c = st.columns(5)
c[0].metric("Incendios activos (24 h)", len(inc))
c[1].metric("🔴 Preparar evacuación", (inc.semaforo.str[0] == "R").sum())
c[2].metric("🟠 Alerta temprana", (inc.semaforo.str[0] == "Á").sum())
c[3].metric("Personas en corredores de 72 h (rojo + ámbar)",
            f"{inc[inc.semaforo.str[0] != 'V'].personas_72h.sum():,.0f}")
c[4].metric("Distritos en el camino del fuego", dist.NOMBDIST.nunique())

st.header("1 · Mapa: hacia dónde empuja el viento a cada incendio")
izq, der = st.columns([3, 2])
with izq:
    horiz = st.radio("Horizonte del corredor", [24, 48, 72], index=2, horizontal=True, format_func=lambda h: f"{h} h")
    solo_alerta = st.checkbox("Solo incendios en rojo o ámbar", value=True)
    vis = inc[inc.semaforo.str[0] != "V"] if solo_alerta else inc
    m = folium.Map(location=[-9.5, -75], zoom_start=5, tiles="CartoDB positron")
    capa = corr[(corr.horizonte_h == horiz) & corr.incendio_id.isin(vis.incendio_id)].merge(
        inc[["incendio_id", "color", "distrito", "semaforo"]], on="incendio_id")
    folium.GeoJson(capa, style_function=lambda f: {"color": f["properties"]["color"], "fillColor": f["properties"]["color"],
                                                   "weight": 1, "fillOpacity": 0.35},
                   tooltip=folium.GeoJsonTooltip(["distrito", "avance_km", "semaforo"], ["Distrito", "Avance (km)", "Semáforo"])).add_to(m)
    for _, r in vis.iterrows():
        folium.CircleMarker([r.lat, r.lon], radius=5, color="black", weight=1, fill=True, fill_color=r.color, fill_opacity=1,
                            tooltip=f"{r.distrito.title()} ({r.departamento.title()}) · {r.personas_24h:,.0f} pers. en 24 h · "
                                    f"{r.personas_72h:,.0f} en 72 h").add_to(m)
    st_folium(m, height=520, use_container_width=True, returned_objects=[])
with der:
    st.subheader("Ranking de exposición")
    tabla = inc[["semaforo", "distrito", "departamento", "cobertura", "focos_24h", "huella_ha", "avance_24h_km",
                 "avance_72h_km", "personas_24h", "personas_72h", "personas_5km_circulo"]].copy()
    tabla["semaforo"] = tabla.semaforo.str.split(" · ").str[0]
    st.dataframe(tabla.round(0), hide_index=True, height=520, column_config={
        "personas_5km_circulo": st.column_config.NumberColumn("personas círculo 5 km (método anterior)")})

st.header("2 · Distritos en el camino del fuego (corredor de 72 h)")
d = dist.groupby(["NOMBDEP", "NOMBPROV", "NOMBDIST"], as_index=False).agg(
    personas=("personas", "sum"), semaforo=("semaforo", "min")).sort_values("personas", ascending=False)
d["semaforo"] = d.semaforo.str.split(" · ").str[0]
st.dataframe(d.round(0), hide_index=True, width="stretch")

st.header("3 · ¿Por qué el viento importa? Corredor vs. círculo fijo de 5 km")
st.write("El tablero de referencia cuenta personas en un círculo fijo de 5 km. Aquí el área sigue al viento: "
         "puede ser mucho mayor (fuego seco y ventoso) o mucho menor (viento que aleja el fuego de la ciudad).")
comp = inc[inc.semaforo.str[0] != "V"].set_index("distrito")[["personas_72h", "personas_5km_circulo"]]
st.bar_chart(comp.rename(columns={"personas_72h": "corredor 72 h", "personas_5km_circulo": "círculo 5 km"}), stack=False)

st.header("4 · Clima pronosticado por incendio")
sel = st.selectbox("Incendio", inc.incendio_id, format_func=lambda i: (lambda r: f"{r.semaforo.split(' · ')[0]} · "
                   f"{r.distrito.title()} ({r.departamento.title()})")(inc.set_index('incendio_id').loc[i]))
p = pron[pron.incendio_id == sel].set_index("time")
a, b = st.columns(2)
a.line_chart(p[["wind_speed_10m", "relative_humidity_2m"]].rename(
    columns={"wind_speed_10m": "viento (km/h)", "relative_humidity_2m": "humedad (%)"}))
b.bar_chart(p[["precipitation"]].rename(columns={"precipitation": "lluvia (mm/h)"}))

st.header("5 · Área quemada medida con satélite (dNBR, Sentinel-2)")
a, b = st.columns([3, 1])
a.image(str(RES / f"dnbr_{dnbr['incendio_id']}.png"))
b.metric("Quemado (dNBR ≥ 0,27)", f"{dnbr['quemado_ha']:,.0f} ha")
b.metric("Huella VIIRS", f"{dnbr['huella_viirs_ha']:,.0f} ha")
b.write(f"**{dnbr['distrito'].title()}, {dnbr['departamento'].title()}** · antes: {dnbr['pre']} "
        f"({dnbr['pre_nubes_zona']} % nubes) · después: {dnbr['post']} ({dnbr['post_nubes_zona']} % nubes)")
b.dataframe(pd.DataFrame(dnbr["severidad"])[["severidad", "hectareas"]], hide_index=True)

with st.expander("Método y limitaciones"):
    st.markdown("""
- **Incendio** = focos VIIRS a ≤ 1 km y ≤ 48 h; **activo** = foco en las últimas 24 h. Fuera fuentes fijas
  (focos en ≥ 4 de 7 días o ≥ 50 % sobre suelo desnudo/urbano/agua según ESA WorldCover).
- **Avance** = 10 % de la velocidad del viento (Cruz y Alexander, 2019), × factor de sequedad
  (1 si HR ≤ 30 %, 0 si HR ≥ 70 %), 0 si llueve ≥ 0,5 mm/h. Corredor = trayectoria hora a hora con ancho 25 % del avance.
- **Semáforo**: ROJO si ≥ 500 personas en el corredor de 24 h **y** el fuego está confirmado (≥ 3 focos en 24 h o ≥ 50 ha);
  ÁMBAR si ≥ 500 personas en 72 h o un solo foco amenaza a ≥ 500 personas (verificar en campo).
- **Limitaciones**: un foco de calor no es un incendio; las nubes esconden el fuego; no se modela pendiente ni combustible;
  la regla del 10 % es para bosque y matorral seco; WorldPop es de 2020; el modelo no está validado con perímetros reales.
""")
