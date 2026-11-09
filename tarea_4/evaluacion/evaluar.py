"""Evaluación de la Parte 4: las mismas 10 preguntas sin y con el MCP y las skills, contra respuestas verificadas.

    uv run evaluacion/evaluar.py                      # modos A y B, 10 preguntas, con Sonnet
    uv run evaluacion/evaluar.py --modos A --ids enaho_cusco

Adaptado de evaluar.py de la Sesión 04. Cada pregunta se hace en una sesión nueva e independiente de Claude Code
(claude -p --no-session-persistence), que debe responder un JSON con el valor (y valor_2 en las mixtas).

Modo A (sin MCP ni skills): sin ninguna herramienta (--tools ""), sin servidores MCP (--strict-mcp-config sin
  --mcp-config), sin skills (--disable-slash-commands) y desde una carpeta vacía fuera del proyecto, así que no
  puede ver ningún archivo, tampoco preguntas.csv.
Modo B (con MCP y skills): desde tarea_4/, con el MCP bcrp (.mcp.json), las skills del proyecto (Skill), Read y
  Bash limitado a «uv run .claude/skills/...» (los scripts de las skills) y a los comandos de solo lectura que
  Claude Code permite por defecto; una línea de sistema le indica usar el MCP para el BCRP y las skills para la ENAHO. Se le niega leer evaluacion/, informes/
  y evidencias_ia/, donde están las respuestas esperadas y el informe.

Guarda la conversación completa de cada llamada (stream-json, con las herramientas habilitadas y las usadas) en
evidencias_ia/evaluacion/modo_{A,B}/<id>.jsonl, ya sanitizada, y escribe evaluacion/resultados.csv.
Las respuestas esperadas se fijaron antes de correr esto (commit de preguntas.csv) y no se cambian después.
"""
import argparse
import json
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
EVIDENCIAS = RAIZ / "evidencias_ia" / "evaluacion"
SKILLS = RAIZ / ".claude" / "skills"
ESQUEMA = {"type": "object", "required": ["valor", "valor_2", "fuente"],
           "properties": {"valor": {"type": ["number", "null"]}, "valor_2": {"type": ["number", "null"]},
                          "fuente": {"type": "string"}}}
INSTRUCCION = ("Responde con un solo número en «valor», en la unidad que pide la pregunta (si la pregunta pide dos "
               "cifras, la segunda va en «valor_2»; si no, valor_2 es null). Si no puedes saberlo con certeza, pon "
               "null: no estimes. En «fuente» di de dónde sale la cifra (serie, periodo, archivo o herramienta). "
               "Usa las herramientas que tengas disponibles si las necesitas.\n\n")
MODOS = {
    "A": ["--tools", "", "--strict-mcp-config", "--disable-slash-commands"],
    "B": ["--tools", "Bash,Read,Skill", "--strict-mcp-config", "--mcp-config", str(RAIZ / ".mcp.json"),
          "--allowedTools", "mcp__bcrp", "Skill", "Read", "Bash(uv run .claude/skills:*)",
          f"Bash(uv run {SKILLS}:*)",
          "--disallowedTools", "mcp__fetch", "Read(./evaluacion/**)", "Read(./informes/**)",
          "Read(./evidencias_ia/**)",
          "--append-system-prompt", "Trabajas en el proyecto tarea_4. Para cifras del BCRP usa el MCP bcrp; para cifras "
          "de la ENAHO 2024 usa las skills del proyecto (limpiando-enaho, graficando-enaho, mapeando-enaho) o sus "
          "salidas en salidas/."],
}
DESCRIPCION_MODOS = {
    "A": "Sin MCP ni skills: ninguna herramienta, sin servidores MCP, skills desactivadas, carpeta vacía",
    "B": "Con MCP bcrp + skills (limpiando/graficando/mapeando-enaho) + Read + Bash(uv run .claude/skills)",
}


def sanitizar(texto):
    """Quita la ruta personal y el correo antes de guardar la evidencia."""
    return texto.replace(str(Path.home()), "~").replace("isabella8albarran@gmail.com", "<correo>")


def preguntar(q, modo, modelo, carpeta_vacia):
    cmd = ["claude", "-p", INSTRUCCION + q.pregunta, "--output-format", "stream-json", "--verbose",
           "--json-schema", json.dumps(ESQUEMA), "--no-session-persistence", "--model", modelo, *MODOS[modo]]
    t = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900,
                              cwd=carpeta_vacia if modo == "A" else RAIZ)
        salida, error_proceso = proc.stdout, proc.stderr.strip()
    except subprocess.TimeoutExpired as e:
        salida, error_proceso = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or ""), \
            "tiempo agotado (900 s)"
    segundos = round(time.time() - t, 1)

    (EVIDENCIAS / f"modo_{modo}").mkdir(parents=True, exist_ok=True)
    (EVIDENCIAS / f"modo_{modo}" / f"{q.id}.jsonl").write_text(sanitizar(salida))

    habilitadas, usadas, errores, final = [], [], [], {}
    for linea in salida.splitlines():
        try:
            m = json.loads(linea)
        except json.JSONDecodeError:
            continue
        if m.get("type") == "system" and m.get("subtype") == "init":
            habilitadas = [h for h in m.get("tools", []) if h != "StructuredOutput"]
        elif m.get("type") == "assistant":
            for b in m["message"].get("content", []):
                if b.get("type") == "tool_use" and b["name"] != "StructuredOutput":
                    nombre = b["name"]
                    if nombre == "Skill":
                        nombre += f"({b['input'].get('skill', b['input'].get('command', ''))})"
                    elif nombre == "Bash":
                        nombre += f"({b['input'].get('command', '')[:70]})"
                    usadas.append(nombre)
        elif m.get("type") == "user":
            for b in m.get("message", {}).get("content", []) if isinstance(m.get("message", {}).get("content"),
                                                                            list) else []:
                if b.get("type") == "tool_result" and b.get("is_error"):
                    c = b.get("content")
                    c = c if isinstance(c, str) else " ".join(x.get("text", "") for x in c or [])
                    errores.append(c.strip().replace("\n", " ")[:160])
        elif m.get("type") == "result":
            final = m
    if final.get("is_error") or not final:
        errores.append(f"resultado con error: {str(final.get('result', error_proceso))[:160]}")
    r = final.get("structured_output") or {}
    return {"valor": r.get("valor"), "valor_2": r.get("valor_2"), "fuente": sanitizar(r.get("fuente", "")),
            "herramientas_habilitadas": ", ".join(habilitadas) or "ninguna",
            "herramientas_usadas": sanitizar(" → ".join(usadas)) or "ninguna", "errores": sanitizar(" | ".join(errores)),
            "segundos": segundos, "turnos": final.get("num_turns"), "costo_usd": final.get("total_cost_usd")}


def calificar(q, r):
    """correcta / incorrecta / sin respuesta, con la tolerancia fijada en preguntas.csv."""
    pares = [(r["valor"], q.respuesta_esperada, q.tolerancia)]
    if pd.notna(q.respuesta_esperada_2):
        pares.append((r["valor_2"], q.respuesta_esperada_2, q.tolerancia_2))
    if all(v is None for v, _, _ in pares):
        return "sin respuesta"
    return "correcta" if all(v is not None and abs(v - e) <= t for v, e, t in pares) else "incorrecta"


def texto(v1, v2):
    v = lambda x: "null" if x is None or (isinstance(x, float) and pd.isna(x)) else f"{x:g}"
    return v(v1) if v2 is None or (isinstance(v2, float) and pd.isna(v2)) else f"{v(v1)} | {v(v2)}"


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--modos", nargs="+", default=["A", "B"], choices=list(MODOS))
    p.add_argument("--modelo", default="sonnet")
    p.add_argument("--ids", nargs="*", help="solo estas preguntas (para probar)")
    p.add_argument("--paralelo", type=int, default=4)
    a = p.parse_args()

    preguntas = pd.read_csv(AQUI / "preguntas.csv")
    if a.ids:
        preguntas = preguntas[preguntas.id.isin(a.ids)]
    casos = [(q, m) for m in a.modos for q in preguntas.itertuples()]
    print(f"{len(casos)} sesiones independientes de claude -p con {a.modelo}...")
    with tempfile.TemporaryDirectory(prefix="modoA_") as vacia, ThreadPoolExecutor(a.paralelo) as ex:
        respuestas = list(ex.map(lambda c: preguntar(c[0], c[1], a.modelo, vacia), casos))

    filas = [{"id": q.id, "tipo": q.tipo, "modo": m, "descripcion_modo": DESCRIPCION_MODOS[m], "modelo": a.modelo,
              "pregunta": q.pregunta,
              "respuesta_esperada": texto(q.respuesta_esperada, q.respuesta_esperada_2),
              "tolerancia": texto(q.tolerancia, q.tolerancia_2), "unidad": q.unidad,
              "respuesta_generada": texto(r["valor"], r["valor_2"]), "resultado": calificar(q, r),
              "fuente_citada": r["fuente"], "fuente_verificacion": q.fuente_verificacion,
              "herramientas_habilitadas": r["herramientas_habilitadas"],
              "herramientas_usadas": r["herramientas_usadas"], "segundos": r["segundos"], "turnos": r["turnos"],
              "costo_usd": r["costo_usd"], "errores": r["errores"]}
             for (q, m), r in zip(casos, respuestas)]
    res = pd.DataFrame(filas)
    destino = AQUI / ("resultados.csv" if not a.ids else "resultados_prueba.csv")
    res.to_csv(destino, index=False)

    print("\n" + res.pivot(index="id", columns="modo", values="respuesta_generada").to_string())
    print("\n" + res.pivot(index="id", columns="modo", values="resultado").to_string())
    tabla = res.groupby("modo").resultado.value_counts().unstack(fill_value=0)
    tabla["segundos_promedio"] = res.groupby("modo").segundos.mean().round(1)
    print("\n" + tabla.to_string() + f"\n\n-> {destino}")
