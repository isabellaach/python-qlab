"""Limpia la ENAHO 2024 del INEI: une personas (módulo 02) con hogares (módulo 34), construye la pobreza y valida.

    uv run .claude/skills/limpiando-enaho/scripts/limpiar.py            # desde la raíz de tarea_4
    uv run .claude/skills/limpiando-enaho/scripts/limpiar.py --anio 2024 --datos datos --salidas salidas

Entra:  datos/966-Modulo34.zip y datos/966-Modulo02.zip (bash scripts/descargar_datos.sh)
Sale:   salidas/personas_2024.parquet  una fila por residente habitual, con pobreza, área, departamento y factor
        salidas/hogares_2024.parquet   una fila por hogar, con peso_personas = factor07 × mieperho (método INEI)
        salidas/indicadores.csv        pobreza ponderada por grupo, con la muestra y la población expandida
        salidas/validacion.txt         cada verificación con APROBADA / FALLIDA
Si falla una validación esencial, escribe validacion.txt igual y termina con código 1: no se corrige nada a mano.

Método (ver reference.md): las cifras territoriales (nacional, área, departamento, Lima Metropolitana) siguen el
método oficial del INEI, la sumaria ponderada con factor07 × mieperho. Las de sexo y edad solo existen en el módulo
02 y se calculan con los residentes habituales ponderados con facpob07. La diferencia nacional es de 0.05 pp.
"""
import argparse
import io
import sys
import zipfile
from datetime import datetime
from pathlib import Path

import pandas as pd

CODIGO_INEI = {2024: 966}                                    # código de la ENAHO 2024 en el portal de microdatos
LLAVES = ["conglome", "vivienda", "hogar"]
LARGO_LLAVES = {"conglome": 6, "vivienda": 3, "hogar": 2, "codperso": 2}
DEPARTAMENTOS = {
    "01": "Amazonas", "02": "Áncash", "03": "Apurímac", "04": "Arequipa", "05": "Ayacucho", "06": "Cajamarca",
    "07": "Callao", "08": "Cusco", "09": "Huancavelica", "10": "Huánuco", "11": "Ica", "12": "Junín",
    "13": "La Libertad", "14": "Lambayeque", "15": "Lima", "16": "Loreto", "17": "Madre de Dios", "18": "Moquegua",
    "19": "Pasco", "20": "Piura", "21": "Puno", "22": "San Martín", "23": "Tacna", "24": "Tumbes", "25": "Ucayali"}
# Cifras de referencia del enunciado (INEI y Sesión 16). Solo se usan para comparar, nunca como resultado.
REFERENCIA = {"pobreza_nacional": 27.6, "residentes": 108_664, "departamentos": 25, "urbana": 24.8, "rural": 39.3,
              "extrema": 5.5, "lima_metropolitana": 28.2, "hogares": 33_691}
TOLERANCIA_NACIONAL = 0.1                                   # puntos porcentuales, según el enunciado
TOLERANCIA_GRUPOS = 0.15                                    # urbano, rural y otros: diferencias de redondeo
REF_DEPARTAMENTOS = Path(__file__).resolve().parents[2] / "mapeando-enaho" / "referencia_pobreza_departamento_2024.csv"


def leer_stata(zip_path: Path, patron: str, columnas: list[str]) -> pd.DataFrame:
    """Lee un .dta dentro del zip del INEI sin convertir etiquetas, con nombres en minúscula y llaves como texto."""
    with zipfile.ZipFile(zip_path) as z:
        nombre = next(n for n in z.namelist() if n.lower().endswith(".dta") and patron in n.lower()
                      and "12g" not in n.lower())          # la sumaria de 12 grupos de gasto es otra base
        crudo = io.BytesIO(z.read(nombre))
    df = pd.read_stata(crudo, convert_categoricals=False, preserve_dtypes=True)
    df.columns = [c.lower().replace("ñ", "n") for c in df.columns]           # «aÑo» → «ano»
    df = df.rename(columns={"ano": "anio"})
    faltan = set(columnas) - set(df.columns)
    if faltan:
        raise SystemExit(f"ERROR: {nombre} no tiene las columnas {sorted(faltan)}")
    df = df[columnas].copy()
    for k in [c for c in LARGO_LLAVES if c in df]:
        df[k] = df[k].astype(str).str.strip()
    return df, nombre


def tasa(df: pd.DataFrame, variable: str, peso: str) -> float:
    """Porcentaje ponderado: suma de pesos con la condición entre la suma de pesos."""
    return float((df[variable] * df[peso]).sum() / df[peso].sum() * 100)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--anio", type=int, default=2024)
    p.add_argument("--datos", default="datos")
    p.add_argument("--salidas", default="salidas")
    a = p.parse_args()
    if a.anio not in CODIGO_INEI:
        raise SystemExit(f"ERROR: solo está validado el año 2024 (código 966); pidieron {a.anio}.")
    cod = CODIGO_INEI[a.anio]
    datos, salidas = Path(a.datos), Path(a.salidas)
    zips = {m: datos / f"{cod}-Modulo{m}.zip" for m in ("34", "02")}
    for m, z in zips.items():
        if not z.exists():
            raise SystemExit(f"ERROR: falta {z}. Bájenlo con: bash scripts/descargar_datos.sh "
                             f"(https://proyectos.inei.gob.pe/iinei/srienaho/descarga/STATA/{cod}-Modulo{m}.zip)")
    salidas.mkdir(exist_ok=True)

    # 1-2. Leer y normalizar
    hogares, archivo_h = leer_stata(zips["34"], "sumaria", LLAVES + [
        "anio", "ubigeo", "dominio", "estrato", "pobreza", "factor07", "mieperho", "linea", "linpe", "gashog2d"])
    personas_todas, archivo_p = leer_stata(zips["02"], "-200", LLAVES + [
        "codperso", "p203", "p204", "p205", "p206", "p207", "p208a", "facpob07"])

    # 3. Residentes habituales: miembros presentes, o no miembros que están 30 días o más
    filtro = (((personas_todas.p204 == 1) & (personas_todas.p205 == 2))
              | ((personas_todas.p204 == 2) & (personas_todas.p206 == 1)))
    personas = personas_todas[filtro].copy()

    # 4. Unir personas (muchas) con su hogar (uno)
    unida = personas.merge(hogares, on=LLAVES, how="left", validate="m:1", indicator=True)

    # 5. Construir indicadores
    unida["ccdd"] = unida.ubigeo.str[:2]
    unida["departamento"] = unida.ccdd.map(DEPARTAMENTOS)
    unida["area"] = unida.estrato.le(5).map({True: "Urbana", False: "Rural"})
    unida["pobre"] = unida.pobreza.le(2).astype(int)                     # 1 extremo, 2 no extremo, 3 no pobre
    unida["pobre_extremo"] = unida.pobreza.eq(1).astype(int)
    unida["sexo"] = unida.p207.map({1: "Hombre", 2: "Mujer"})
    unida["edad"] = unida.p208a
    unida["grupo_edad"] = pd.cut(unida.edad, [-1, 17, 29, 44, 64, 200],
                                 labels=["0-17", "18-29", "30-44", "45-64", "65 y más"]).astype(str)
    unida["lima_metropolitana"] = unida.dominio.eq(8).astype(int)
    unida["anio"] = a.anio

    # 6. Validar
    chequeos = []                                                        # (nombre, ok, detalle, esencial)

    def chequear(nombre, ok, detalle, esencial=True):
        chequeos.append((nombre, bool(ok), detalle, esencial))

    for df, nombre, llaves in [(hogares, "hogares (módulo 34)", LLAVES),
                               (personas_todas, "personas (módulo 02)", LLAVES + ["codperso"])]:
        dup = int(df.duplicated(llaves).sum())
        chequear(f"Llaves únicas en {nombre}", dup == 0, f"{dup} duplicados con {llaves}")
        largos = {k: sorted(df[k].str.len().unique().tolist()) for k in llaves}
        chequear(f"Llaves de {nombre} como texto, con ceros iniciales",
                 all(v == [LARGO_LLAVES[k]] for k, v in largos.items()), f"largos {largos}")
    chequear("Hogares en la sumaria", len(hogares) == REFERENCIA["hogares"],
             f"{len(hogares):,} (referencia {REFERENCIA['hogares']:,})", esencial=False)
    chequear("Residentes habituales", len(personas) == REFERENCIA["residentes"],
             f"{len(personas):,} de {len(personas_todas):,} filas del módulo 02 (referencia "
             f"{REFERENCIA['residentes']:,})")
    sin_hogar = int((unida._merge != "both").sum())
    chequear("Unión m:1 sin duplicar ni perder personas", len(unida) == len(personas) and sin_hogar == 0,
             f"{len(personas):,} antes, {len(unida):,} después; {sin_hogar} personas sin hogar en la sumaria")
    codigos = sorted(unida.ccdd.unique())
    chequear("25 códigos territoriales (01 a 25)", codigos == sorted(DEPARTAMENTOS),
             f"{len(codigos)} códigos: {codigos[0]}…{codigos[-1]}; sin nombre: "
             f"{sorted(set(codigos) - set(DEPARTAMENTOS)) or 'ninguno'}")
    nulos = int(unida[["pobreza", "facpob07", "factor07", "estrato", "ubigeo"]].isna().sum().sum())
    chequear("Sin datos faltantes en pobreza, factores y ubicación", nulos == 0, f"{nulos} valores faltantes")
    chequear("Factores de expansión positivos", (unida.facpob07 > 0).all() and (hogares.factor07 > 0).all(),
             f"facpob07 mín. {unida.facpob07.min():.1f}; factor07 mín. {hogares.factor07.min():.1f}")
    poblacion = float(unida.facpob07.sum())
    chequear("Población expandida plausible (30 a 36 millones)", 30e6 < poblacion < 36e6,
             f"{poblacion:,.0f} personas con facpob07")

    # Pobreza nacional por dos caminos: el oficial del INEI (hogares × mieperho) y el de personas (facpob07)
    hogares["pobre"] = hogares.pobreza.le(2).astype(int)
    hogares["peso_personas"] = hogares.factor07 * hogares.mieperho
    pob_hogares = tasa(hogares, "pobre", "peso_personas")
    pob_personas = tasa(unida, "pobre", "facpob07")
    pob_simple = float(unida.pobre.mean() * 100)
    ref = REFERENCIA["pobreza_nacional"]
    chequear("Pobreza nacional (sumaria, factor07 × mieperho, método INEI)",
             abs(pob_hogares - ref) <= TOLERANCIA_NACIONAL, f"{pob_hogares:.2f} % (referencia {ref} % ± 0.1)")
    chequear("Pobreza nacional (personas, facpob07)", abs(pob_personas - ref) <= TOLERANCIA_NACIONAL,
             f"{pob_personas:.2f} % (referencia {ref} % ± 0.1)")
    chequear("La ponderación cambia el resultado (el promedio simple no sirve)", abs(pob_simple - pob_personas) > 1,
             f"sin ponderar {pob_simple:.2f} % frente a {pob_personas:.2f} % ponderado", esencial=False)
    hogares["pobre_extremo"] = hogares.pobreza.eq(1).astype(int)
    hogares["ccdd"] = hogares.ubigeo.str[:2]
    hogares["departamento"] = hogares.ccdd.map(DEPARTAMENTOS)
    hogares["area"] = hogares.estrato.le(5).map({True: "Urbana", False: "Rural"})
    hogares["lima_metropolitana"] = hogares.dominio.eq(8).astype(int)
    for clave, h, p_ in [("urbana", hogares[hogares.area == "Urbana"], unida[unida.area == "Urbana"]),
                         ("rural", hogares[hogares.area == "Rural"], unida[unida.area == "Rural"]),
                         ("lima_metropolitana", hogares[hogares.lima_metropolitana == 1],
                          unida[unida.lima_metropolitana == 1])]:
        valor = tasa(h, "pobre", "peso_personas")
        chequear(f"Pobreza {clave.replace('_', ' ')} (método INEI)",
                 abs(valor - REFERENCIA[clave]) <= TOLERANCIA_GRUPOS,
                 f"{valor:.2f} % (referencia {REFERENCIA[clave]} % ± {TOLERANCIA_GRUPOS}); con personas y "
                 f"facpob07 daría {tasa(p_, 'pobre', 'facpob07'):.2f} %", esencial=False)
    extrema = tasa(hogares, "pobre_extremo", "peso_personas")
    chequear("Pobreza extrema (método INEI)", abs(extrema - REFERENCIA["extrema"]) <= TOLERANCIA_GRUPOS,
             f"{extrema:.2f} % (referencia {REFERENCIA['extrema']} % ± {TOLERANCIA_GRUPOS})", esencial=False)

    # 7. Indicadores por grupo, todos ponderados. Territoriales: método INEI (hogares); individuales: personas.
    INEI, PERS = "hogares, factor07 × mieperho", "residentes habituales, facpob07"
    filas = [("Nacional", "Perú", hogares, INEI)]
    filas += [("Área", g, d, INEI) for g, d in hogares.groupby("area")]
    filas += [("Dominio", "Lima Metropolitana", hogares[hogares.lima_metropolitana == 1], INEI)]
    filas += [("Departamento", f"{c} {DEPARTAMENTOS[c]}", d, INEI) for c, d in hogares.groupby("ccdd")]
    filas += [("Nacional (personas)", "Perú", unida, PERS)]
    filas += [("Sexo", g, d, PERS) for g, d in unida.groupby("sexo")]
    filas += [("Grupo de edad", g, d, PERS) for g, d in unida.groupby("grupo_edad")]
    registros = []
    for t, c, d, metodo in filas:
        peso = "peso_personas" if metodo == INEI else "facpob07"
        registros.append({"grupo": t, "categoria": c, "pobreza_pct": round(tasa(d, "pobre", peso), 2),
                          "pobreza_extrema_pct": round(tasa(d, "pobre_extremo", peso), 2),
                          "poblacion_expandida": round(float(d[peso].sum())),
                          "muestra": len(d), "unidad_muestra": "hogares" if metodo == INEI else "personas",
                          "metodo": metodo})
    ind = pd.DataFrame(registros)
    ind["ccdd"] = ind.categoria.where(ind.grupo == "Departamento").str[:2]
    ind["anio"] = a.anio
    ind["fuente"] = f"INEI, ENAHO {a.anio}, módulos 34 (sumaria) y 02 (miembros); estimación ponderada"

    if REF_DEPARTAMENTOS.exists():
        ref_dep = pd.read_csv(REF_DEPARTAMENTOS, dtype={"ccdd": str}).rename(columns={"pobreza_pct": "referencia"})
        comp = ind.dropna(subset=["ccdd"]).merge(ref_dep[["ccdd", "referencia"]], on="ccdd", validate="1:1")
        dif = (comp.pobreza_pct - comp.referencia).abs().reset_index(drop=True)
        comp = comp.reset_index(drop=True)
        peor = comp.loc[dif.idxmax()]
        chequear("Pobreza de los 25 departamentos frente a la referencia de la Sesión 16", dif.max() <= 0.1,
                 f"diferencia máxima {dif.max():.2f} pp ({peor.categoria})", esencial=False)

    esenciales_fallidas = [c for c in chequeos if c[3] and not c[1]]
    lineas = [f"VALIDACIÓN ENAHO {a.anio}  ·  {datetime.now():%Y-%m-%d %H:%M}",
              f"Archivos: {archivo_h} ({len(hogares):,} hogares) y {archivo_p} ({len(personas_todas):,} personas)",
              "Unidad de análisis: residentes habituales; pobreza = pobreza <= 2; urbano = estrato <= 5.", ""]
    lineas += [f"[{'APROBADA' if ok else 'FALLIDA '}] {'(esencial) ' if es else ''}{n}: {d}"
               for n, ok, d, es in chequeos]
    aprob = sum(c[1] for c in chequeos)
    lineas += ["", f"Resumen: {aprob} de {len(chequeos)} verificaciones aprobadas; "
               f"{len(esenciales_fallidas)} esenciales fallidas.",
               "RESULTADO: " + ("VÁLIDO. La base se puede usar." if not esenciales_fallidas else
                                "NO VÁLIDO. No usen la base hasta resolver las fallas esenciales.")]
    (salidas / "validacion.txt").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print("\n".join(lineas))
    if esenciales_fallidas:
        sys.exit(1)

    columnas = LLAVES + ["codperso", "anio", "ubigeo", "ccdd", "departamento", "dominio", "estrato", "area",
                         "lima_metropolitana", "sexo", "edad", "grupo_edad", "p203", "pobreza", "pobre",
                         "pobre_extremo", "mieperho", "linea", "linpe", "gashog2d", "facpob07", "factor07"]
    unida[columnas].to_parquet(salidas / f"personas_{a.anio}.parquet", index=False)
    hogares[LLAVES + ["ubigeo", "ccdd", "departamento", "dominio", "estrato", "area", "lima_metropolitana",
                      "pobreza", "pobre", "pobre_extremo", "mieperho", "factor07", "peso_personas"]
            ].assign(anio=a.anio).to_parquet(salidas / f"hogares_{a.anio}.parquet", index=False)
    ind.to_csv(salidas / "indicadores.csv", index=False)
    print(f"\nGuardé {salidas / f'personas_{a.anio}.parquet'} ({len(unida):,} filas), "
          f"{salidas / f'hogares_{a.anio}.parquet'} ({len(hogares):,} filas) y {salidas / 'indicadores.csv'}")


if __name__ == "__main__":
    main()
