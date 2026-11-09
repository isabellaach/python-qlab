"""Convierte las conversaciones de Claude Code (JSONL de ~/.claude/projects/...) en markdown sanitizado.

    uv run scripts/exportar_conversaciones.py

Incluye los mensajes de la usuaria, las respuestas de Claude, cada llamada a una herramienta con su entrada y el
resultado (recortado). Sanitiza: la ruta personal pasa a «~», se quita el correo, se omiten los recordatorios
internos del sistema (<system-reminder>, que traen memoria y contexto del entorno), el razonamiento interno y las
imágenes en base64. Se detiene si encuentra algo con forma de clave o token.
"""
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ORIGEN = Path.home() / ".claude/projects/-Users-isabellaalbarran-Documents-Github-python-qlab-tarea-4"
SESIONES = {   # id de la sesión → (archivo de salida, título)
    "5cfe65dd-2846-465a-9b77-7dba761f50c8": ("desarrollo/01_sesion_desarrollo.md",
                                             "Sesión de desarrollo de la Tarea 4 (servidor MCP, skills, evaluación)"),
    "8b3e1701-68ec-4f07-939a-7679361c43b8": ("mcp/02_transcripcion_completa_demo_mcp.md",
                                             "Demo del MCP bcrp: transcripción completa"),
    "aa5a55c4-c952-44f3-9a7e-41b4ac63ec26": ("skills/02_transcripcion_completa_demo_skills.md",
                                             "Demo de las skills ENAHO: transcripción completa"),
    "3aaad362-b3e6-45d8-ae11-5787c34a92c3": ("integracion/02_transcripcion_completa_ejecucion_integrada.md",
                                             "Ejecución integrada: transcripción completa"),
}
SECRETOS = re.compile(r"sk-ant-[A-Za-z0-9_-]{10,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
                      r"AKIA[0-9A-Z]{16}|xox[bp]-[A-Za-z0-9-]{10,}")
MAX_RESULTADO = 2500


def sanitizar(t: str) -> str:
    t = re.sub(r"<system-reminder>.*?</system-reminder>", "", t, flags=re.S)
    t = t.replace(str(Path.home()), "~").replace("/private/tmp/claude-501", "<tmp>")
    t = re.sub(r"[A-Za-z0-9._%+-]+@gmail\.com", "<correo>", t)
    t = t.replace("isabella8albarran", "<correo>").replace("isabellaalbarran", "<usuario>")
    t = re.sub(r"[A-Za-z0-9+/=]{400,}", "[datos en base64 omitidos]", t)
    return t.strip()


def texto_de(contenido) -> str:
    if isinstance(contenido, str):
        return contenido
    partes = []
    for b in contenido or []:
        if b.get("type") == "text":
            partes.append(b["text"])
        elif b.get("type") == "image":
            partes.append("[imagen]")
    return "\n".join(partes)


def recortar(t: str, n=MAX_RESULTADO) -> str:
    return t if len(t) <= n else t[:n] + f"\n… [{len(t) - n} caracteres más omitidos]"


def convertir(jsonl: Path, titulo: str) -> str:
    salida = [f"# {titulo}\n", f"Sesión `{jsonl.stem}` de Claude Code, exportada y sanitizada con "
              "`scripts/exportar_conversaciones.py`.\n"]
    privados = set()                       # llamadas que leyeron la memoria personal de Claude Code
    for linea in jsonl.read_text().splitlines():
        m = json.loads(linea)
        if m.get("isSidechain") or m.get("type") not in ("user", "assistant"):
            continue
        hora = m.get("timestamp", "")[11:16]
        cont = m["message"].get("content")
        if m["type"] == "user":
            if isinstance(cont, list) and any(b.get("type") == "tool_result" for b in cont):
                for b in cont:
                    if b.get("type") == "tool_result" and b.get("tool_use_id") in privados:
                        salida.append("*[Resultado omitido: notas personales de la memoria de Claude Code]*\n")
                    elif b.get("type") == "tool_result":
                        t = recortar(sanitizar(texto_de(b.get("content"))))
                        error = " (error)" if b.get("is_error") else ""
                        if t:
                            salida.append(f"<details><summary>Resultado{error}</summary>\n\n```text\n{t}\n```\n"
                                          "</details>\n")
                continue
            t = sanitizar(texto_de(cont))
            if t:
                etiqueta = "Resumen automático del contexto" if m.get("isCompactSummary") else "Usuaria"
                salida.append(f"## {etiqueta} · {hora} UTC\n\n{t}\n")
        else:
            for b in cont or []:
                if b.get("type") == "text" and b["text"].strip():
                    salida.append(f"**Claude** · {hora} UTC\n\n{sanitizar(b['text'])}\n")
                elif b.get("type") == "tool_use":
                    if "/memory/" in json.dumps(b["input"]):
                        privados.add(b["id"])
                    entrada = recortar(sanitizar(json.dumps(b["input"], ensure_ascii=False, indent=1)), 4000)
                    salida.append(f"`{b['name']}`\n\n```json\n{entrada}\n```\n")
    return "\n".join(salida)


if __name__ == "__main__":
    for sesion, (destino, titulo) in SESIONES.items():
        md = convertir(ORIGEN / f"{sesion}.jsonl", titulo)
        if SECRETOS.search(md):
            sys.exit(f"ALTO: {destino} tiene algo con forma de clave o token; revisar antes de publicar.")
        ruta = RAIZ / "evidencias_ia" / destino
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(md)
        print(f"{ruta.relative_to(RAIZ)}: {len(md) / 1024:.0f} KB")
    for export in (RAIZ / "evidencias_ia").glob("*/01_*.md"):   # exportaciones con /export: misma sanitización
        export.write_text(sanitizar(export.read_text()) + "\n")
