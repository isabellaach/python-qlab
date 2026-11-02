"""Procesa la ENAHO 2015-2025: reconstruye la informalidad laboral, la valida y calcula los indicadores.

Uso:
    python scripts/procesar_datos.py --validar     # solo la validación contra ocupinf (2015-2023)
    python scripts/procesar_datos.py               # validación + todos los indicadores

Criterio de informalidad (ocupación principal, INEI):
  - Asalariados (empleado, obrero), trabajadores del hogar y "otro": formales si tienen seguro de salud
    (EsSalud, EPS o seguro privado) pagado por el centro de trabajo, o seguro de FF.AA./PNP si trabajan para
    las FF.AA./PNP. El resto es informal.
  - Empleadores e independientes: formales si el negocio está registrado en SUNAT (persona jurídica o
    persona natural con RUC), salvo en actividades agropecuarias (CIIU 01-03), que el INEI cuenta como
    sector informal.
  - Trabajadores familiares no remunerados: siempre informales.
Universo: población ocupada de 14 años a más (ocu500 == 1), ponderada con fac500a.
Intervalos de confianza: linealización de Taylor con conglomerados (conglome) y estratos (departamento × estrato).
"""
from __future__ import annotations

import argparse
import io
import json
import re
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
ORIG = RAIZ / "datos" / "originales"
PROC = RAIZ / "datos" / "procesados"
WEB = RAIZ / "web" / "data"
ANIOS = list(range(2015, 2026))
LLAVE = ["conglome", "vivienda", "hogar", "codperso"]
Z = 1.959964

DPTOS = {
    "01": "Amazonas", "02": "Áncash", "03": "Apurímac", "04": "Arequipa", "05": "Ayacucho", "06": "Cajamarca",
    "07": "Callao", "08": "Cusco", "09": "Huancavelica", "10": "Huánuco", "11": "Ica", "12": "Junín",
    "13": "La Libertad", "14": "Lambayeque", "15": "Lima", "16": "Loreto", "17": "Madre de Dios",
    "18": "Moquegua", "19": "Pasco", "20": "Piura", "21": "Puno", "22": "San Martín", "23": "Tacna",
    "24": "Tumbes", "25": "Ucayali",
}
COLS5 = ["ubigeo", "estrato", "ocu500", "ocupinf", "p207", "p208a", "p301a", "p506r4", "p507", "p510",
         "p510a1", "p511a", "p512a", "p512b", "fac500a", "i524a1", "i530a", "p558a5"]
COLS4 = ["p4191", "p4192", "p4193", "p4194", "p419a1", "p419a2", "p419a3", "p419a4"]


# ----------------------------------------------------------------------------------------------- lectura
def _dta(anio: int, modulo: str) -> tuple[zipfile.ZipFile, str]:
    zpath = next(ORIG.glob(f"enaho_{anio}_*_modulo{modulo}.zip"))
    z = zipfile.ZipFile(zpath)
    nombre = next(n for n in z.namelist() if re.search(rf"-{modulo[-1]}00\.dta$", n, re.I))
    return z, nombre


def leer(anio: int, modulo: str, cols: list[str]) -> pd.DataFrame:
    z, nombre = _dta(anio, modulo)
    df = pd.read_stata(io.BytesIO(z.read(nombre)), convert_categoricals=False)
    df.columns = [c.lower() for c in df.columns]
    return df[[c for c in LLAVE + cols if c in df.columns]]


def ocupinf_en_diccionario(anio: int) -> bool | None:
    """¿Aparece OCUPINF en el diccionario PDF oficial que viene en el zip del módulo 500?"""
    import fitz  # PyMuPDF
    z, _ = _dta(anio, "05")
    pdfs = [n for n in z.namelist() if "diccionario" in n.lower() and n.lower().endswith(".pdf")]
    if not pdfs:
        return None
    texto = "".join(p.get_text() for p in fitz.open(stream=z.read(pdfs[0]), filetype="pdf"))
    return bool(re.search(r"\bocupinf\b", texto, re.I))


def cargar(anio: int) -> pd.DataFrame:
    m5 = leer(anio, "05", COLS5)
    m4 = leer(anio, "04", COLS4)
    d = m5.merge(m4, on=LLAVE, how="left", validate="one_to_one")
    d = d[d["ocu500"] == 1].copy()
    d["anio"] = anio
    d["dpto"] = d["ubigeo"].astype(str).str.zfill(6).str[:2]
    d["informal"] = informalidad(d).astype(int)
    d["oficial"] = np.where(d["ocupinf"].isin([1, 2]), (d["ocupinf"] == 1).astype(float), np.nan) \
        if "ocupinf" in d else np.nan
    return d


# ----------------------------------------------------------------------------------------------- informalidad
def informalidad(d: pd.DataFrame, con_pension: bool = False) -> pd.Series:
    asal = d["p507"].isin([3, 4, 6, 7])
    indep = d["p507"].isin([1, 2])
    pagado = lambda tiene, quien: (d.get(tiene) == 1) & (d.get(quien) == 1)
    formal_asal = (pagado("p4191", "p419a1") | pagado("p4192", "p419a2") | pagado("p4193", "p419a3")
                   | ((d.get("p4194") == 1) & (d["p510"] == 1)))
    if con_pension and "p558a5" in d:
        formal_asal = formal_asal | (d["p558a5"] != 1) & d["p558a5"].notna() & (d["p510"].isin([2, 3]))
    agro = (d["p506r4"] // 100).isin([1, 2, 3])
    registrado = d["p510a1"].isin([1, 2]) & ~agro
    inf = pd.Series(True, index=d.index)
    inf[asal] = ~formal_asal[asal]
    inf[indep] = ~registrado[indep]
    inf[d["p507"] == 5] = True
    return inf


# ----------------------------------------------------------------------------------------------- estimación
def estimar(d: pd.DataFrame, y: str, por: list[str]) -> pd.DataFrame:
    """Proporción ponderada de `y` por dominio, con IC 95 % por linealización (conglomerados y estratos)."""
    d = d.assign(_estr=d["dpto"] + "_" + d["estrato"].astype(int).astype(str))
    n_h = d.groupby("_estr")["conglome"].nunique().rename("n_h")
    out = []
    for clave, g in d.groupby(por, dropna=True) if por else [((), d)]:
        w = g["fac500a"].to_numpy()
        yy = g[y].to_numpy(dtype=float)
        W = w.sum()
        p = (w * yy).sum() / W
        g = g.assign(_z=w * (yy - p) / W)
        t = g.groupby(["_estr", "conglome"])["_z"].sum().reset_index()
        s = t.groupby("_estr")["_z"].agg(S1="sum", S2=lambda v: (v ** 2).sum()).join(n_h)
        s = s[s["n_h"] > 1]
        var = (s["n_h"] / (s["n_h"] - 1) * (s["S2"] - s["S1"] ** 2 / s["n_h"])).sum()
        se = float(np.sqrt(max(var, 0)))
        fila = dict(zip(por, clave if isinstance(clave, tuple) else (clave,)))
        fila.update(tasa=100 * p, ee=100 * se, li=100 * (p - Z * se), ls=100 * (p + Z * se),
                    n=len(g), ocupados=W, casos=(w * yy).sum())
        out.append(fila)
    return pd.DataFrame(out)


def mediana_ponderada(v: np.ndarray, w: np.ndarray) -> float:
    o = np.argsort(v)
    v, w = v[o], w[o]
    c = np.cumsum(w)
    return float(v[np.searchsorted(c, c[-1] / 2)])


# ----------------------------------------------------------------------------------------------- categorías
def categorias(d: pd.DataFrame) -> pd.DataFrame:
    e = d["p208a"]
    d["edad"] = pd.cut(e, [13, 24, 44, 64, 200], labels=["14 a 24", "25 a 44", "45 a 64", "65 a más"]).astype(str)
    d["sexo"] = d["p207"].map({1: "Hombres", 2: "Mujeres"})
    d["area"] = np.where(d["estrato"] <= 5, "Urbana", "Rural")
    d["educacion"] = d["p301a"].map(lambda x: "Primaria o menos" if x in (1, 2, 3, 4, 12) else
                                    "Secundaria" if x in (5, 6) else "Superior técnica" if x in (7, 8) else
                                    "Universitaria" if x in (9, 10, 11) else None)
    tam = pd.Series(None, index=d.index, dtype=object)
    chica = d["p512a"] == 1
    tam[chica & (d["p512b"] <= 10)] = "1 a 10"
    tam[(chica & (d["p512b"] > 10)) | (d["p512a"] == 2)] = "11 a 50"
    tam[d["p512a"] == 3] = "51 a 100"
    tam[d["p512a"].isin([4, 5])] = "Más de 100"
    d["tamano"] = tam
    div = d["p506r4"] // 100
    ramas = [((1, 3), "Agropecuario y pesca"), ((5, 9), "Minería"), ((10, 33), "Manufactura"),
             ((41, 43), "Construcción"), ((45, 47), "Comercio"), ((49, 53), "Transporte"),
             ((55, 56), "Alojamiento y restaurantes"), ((84, 84), "Administración pública"),
             ((85, 88), "Educación y salud"), ((97, 98), "Trabajo del hogar")]
    r = pd.Series("Otros servicios", index=d.index, dtype=object)
    for (a, b), nom in ramas:
        r[div.between(a, b)] = nom
    r[div.isna()] = None
    d["rama"] = r
    d["categoria_ocup"] = d["p507"].map({1: "Empleador", 2: "Independiente", 3: "Asalariado", 4: "Asalariado",
                                         5: "Familiar no remunerado", 6: "Trabajador del hogar", 7: "Otro"})
    d["ingreso_mes"] = (d["i524a1"].fillna(0) + d["i530a"].fillna(0)) / 12
    return d


# ----------------------------------------------------------------------------------------------- principal
def validar(datos: dict[int, pd.DataFrame]) -> pd.DataFrame:
    filas = []
    for anio, d in datos.items():
        tiene = d["oficial"].notna().any()
        fila = {"anio": anio, "ocupinf_en_base": tiene, "ocupinf_en_diccionario": ocupinf_en_diccionario(anio),
                "n": len(d), "tasa_reconstruida": 100 * np.average(d["informal"], weights=d["fac500a"])}
        if tiene:
            v = d[d["oficial"].notna()]
            fila["tasa_oficial"] = 100 * np.average(v["oficial"], weights=v["fac500a"])
            fila["acuerdo_pct"] = 100 * np.average(v["informal"] == v["oficial"], weights=v["fac500a"])
            alt = informalidad(v, con_pension=True)
            fila["acuerdo_con_pension_pct"] = 100 * np.average(alt == v["oficial"], weights=v["fac500a"])
            fila["diferencia_pp"] = fila["tasa_reconstruida"] - fila["tasa_oficial"]
        filas.append(fila)
    return pd.DataFrame(filas)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--validar", action="store_true")
    args = ap.parse_args()
    PROC.mkdir(parents=True, exist_ok=True)

    datos = {}
    for a in ANIOS:
        datos[a] = cargar(a)
        print(f"{a}: {len(datos[a]):,} ocupados en la muestra", flush=True)

    val = validar(datos)
    val.round(2).to_csv(PROC / "validacion_informalidad.csv", index=False)
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(val.round(2).to_string(index=False))
    if args.validar:
        return

    d = categorias(pd.concat(datos.values(), ignore_index=True))
    d["dpto_nombre"] = d["dpto"].map(DPTOS)

    nac = estimar(d, "informal", ["anio"])
    ofi = val.set_index("anio")["tasa_oficial"] if "tasa_oficial" in val else None
    nac["tasa_oficial"] = nac["anio"].map(ofi)
    dep = estimar(d, "informal", ["anio", "dpto"])
    dep["departamento"] = dep["dpto"].map(DPTOS)

    dims = ["sexo", "edad", "area", "educacion", "tamano", "rama", "categoria_ocup"]
    grupos = []
    for dim in dims:
        g = d[d[dim].notna()].assign(_cat=lambda x: x[dim])
        a = estimar(g, "informal", ["anio", "_cat"]).assign(dpto="00")
        b = estimar(g, "informal", ["anio", "dpto", "_cat"])
        t = pd.concat([a, b]).rename(columns={"_cat": "categoria"}).assign(dimension=dim)
        tot = t.groupby(["anio", "dpto"])["ocupados"].transform("sum")
        t["participacion"] = 100 * t["ocupados"] / tot
        grupos.append(t)
    grupos = pd.concat(grupos, ignore_index=True)

    # el Estado: asalariados de la administración pública (p510 == 2), por tipo de contrato
    CONTRATOS = {1: "Nombrado o indefinido", 2: "Plazo fijo", 3: "Otro", 4: "Prácticas", 5: "Locación de servicios",
                 6: "CAS", 7: "Sin contrato", 8: "Otro"}
    est = d[(d["p510"] == 2) & d["p507"].isin([3, 4])].copy()
    est["contrato"] = est["p511a"].map(CONTRATOS).fillna("Otro")
    est["locacion"] = (est["p511a"] == 5).astype(int)
    estado_tasa = estimar(est, "informal", ["anio"]).assign(indicador="informalidad")
    estado_loc = estimar(est, "locacion", ["anio"]).assign(indicador="locacion")
    comp = (est.groupby(["anio", "contrato", "informal"])["fac500a"].sum().rename("trabajadores").reset_index())
    estado = {"tasas": pd.concat([estado_tasa, estado_loc], ignore_index=True), "composicion": comp}

    # ingresos: mediana mensual de la ocupación principal (soles corrientes), formal vs informal
    ing = []
    con = d[d["ingreso_mes"] > 0]
    for (anio, dp), g in list(con.groupby(["anio", "dpto"])) + [((a, "00"), g) for a, g in con.groupby("anio")]:
        fila = {"anio": anio, "dpto": dp}
        for k, nom in ((0, "formal"), (1, "informal")):
            h = g[g["informal"] == k]
            fila[f"mediana_{nom}"] = mediana_ponderada(h["ingreso_mes"].to_numpy(), h["fac500a"].to_numpy()) if len(h) else np.nan
            fila[f"n_{nom}"] = len(h)
        ing.append(fila)
    ing = pd.DataFrame(ing)
    ing["cociente"] = ing["mediana_informal"] / ing["mediana_formal"]

    # cambio 2019 -> 2025 por departamento (muestras independientes)
    p = dep.pivot(index="dpto", columns="anio", values=["tasa", "ee"])
    cambio = pd.DataFrame({
        "dpto": p.index, "departamento": p.index.map(DPTOS),
        "tasa_2019": p[("tasa", 2019)].values, "tasa_2025": p[("tasa", 2025)].values,
        "cambio_pp": (p[("tasa", 2025)] - p[("tasa", 2019)]).values,
        "ee_cambio": np.sqrt(p[("ee", 2019)] ** 2 + p[("ee", 2025)] ** 2).values,
    })
    cambio["significativo"] = (cambio["cambio_pp"].abs() > Z * cambio["ee_cambio"])

    for nombre, t in [("serie_nacional", nac), ("departamentos", dep), ("grupos", grupos),
                      ("ingresos", ing), ("cambio_2019_2025", cambio), ("estado_tasas", estado["tasas"]),
                      ("estado_contratos", estado["composicion"])]:
        t.round(3).to_csv(PROC / f"{nombre}.csv", index=False)
    WEB.mkdir(parents=True, exist_ok=True)
    paquete = {k: json.loads(v.round(2).to_json(orient="records", force_ascii=False))
               for k, v in [("nacional", nac), ("departamentos", dep), ("grupos", grupos), ("ingresos", ing),
                            ("cambio", cambio), ("validacion", val), ("estado_tasas", estado["tasas"]),
                            ("estado_contratos", estado["composicion"])]}
    paquete["dptos"] = DPTOS
    (WEB / "datos.json").write_text(json.dumps(paquete, ensure_ascii=False), encoding="utf-8")
    print("Listo:", sorted(p.name for p in PROC.glob("*.csv")))


if __name__ == "__main__":
    main()
