"""Paso 2 del flujo: del texto fuente al guion del reel (guion.json).

Uso:
    python guion.py --solo-prompt > prompt.txt          # pegar en chat.qwen.ai
    python guion.py --respuesta respuesta.txt           # validar lo que respondió Qwen

El control automático marca con ¡¡ toda cifra que no aparece tal cual en el texto
fuente. Eso no reemplaza la revisión humana (paso 3): una frase puede usar cifras
correctas y aun así afirmar algo falso.
"""

import argparse
import json
import re
import sys
from pathlib import Path

AQUI = Path(__file__).parent
TEXTO_DEFECTO = AQUI.parent / "tarea_data_raster" / "README.md"
SALIDAS = AQUI / "salidas"

PROMPT = """Eres guionista de reels de divulgación científica en español del Perú.
Convierte el TEXTO FUENTE en el guion de un reel vertical de 45 a 50 segundos,
narrado en primera persona por la autora del trabajo.

Reglas:
1. Exactamente 6 escenas. Entre 110 y 130 palabras en total sumando todas las "frase".
2. Escena 1: la pregunta del trabajo. Escenas 2 a 5: un hallazgo o dato cada una.
   Escena 6: una limitación honesta y el cierre.
3. "frase" es lo que se dice en voz alta: escribe los números EN PALABRAS
   (ej. "tres mil trescientas setenta y dos"), sin siglas difíciles de pronunciar.
4. "cifra" es el número que se ve en pantalla. Cópialo EXACTAMENTE como aparece
   en el texto fuente (mismos dígitos y unidades). Si una escena no tiene cifra, usa "".
5. "etiqueta": máximo 6 palabras que explican la cifra en pantalla.
6. No agregues nada que el texto fuente no diga. No exageres: el trabajo es una
   herramienta académica con pronósticos, no un sistema oficial ni en tiempo real.
7. Además escribe tres posts para acompañar el reel: "linkedin" (máx. 120 palabras),
   "x" (máx. 260 caracteres) y "instagram" (máx. 80 palabras, con 3 a 5 hashtags).

Responde SOLO con JSON válido, sin texto antes ni después, con esta forma:
{{
  "titulo": "...",
  "escenas": [
    {{"frase": "...", "cifra": "...", "etiqueta": "..."}}
  ],
  "posts": {{"linkedin": "...", "x": "...", "instagram": "..."}}
}}

TEXTO FUENTE:
<<<
{texto}
>>>
"""


def leer_texto(ruta: Path) -> str:
    if ruta.suffix.lower() == ".pdf":
        from pypdf import PdfReader
        return "\n".join(p.extract_text() or "" for p in PdfReader(ruta).pages)
    texto = ruta.read_text(encoding="utf-8")
    # Imágenes y bloques de código no aportan al guion
    texto = re.sub(r"```.*?```", "", texto, flags=re.S)
    texto = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", texto)
    texto = texto.split("## Cómo correrlo")[0]
    return re.sub(r"\n{3,}", "\n\n", texto).strip()


def normalizar(s: str) -> str:
    # "3 372", "3 372" y "3372" cuentan como la misma cifra
    return re.sub(r"[\s  ]", "", s).replace(",", ".")


def extraer_json(respuesta: str) -> dict:
    respuesta = re.sub(r"^```(?:json)?|```$", "", respuesta.strip(), flags=re.M)
    inicio, fin = respuesta.find("{"), respuesta.rfind("}")
    return json.loads(respuesta[inicio:fin + 1])


def revisar(guion: dict, texto: str) -> list[str]:
    fuente = normalizar(texto)
    avisos = []
    for i, e in enumerate(guion["escenas"], 1):
        for campo in ("cifra", "etiqueta"):
            for num in re.findall(r"\d[\d\s.,  ]*\d|\d", e.get(campo, "")):
                if normalizar(num) not in fuente:
                    e[campo] = e[campo].replace(num, f"¡¡{num}")
                    avisos.append(f"Escena {i}: {campo} «{num}» no aparece en el texto fuente")
        if re.search(r"\d", e["frase"]):
            avisos.append(f"Escena {i}: la frase tiene dígitos; deben ir en palabras")
    palabras = sum(len(e["frase"].split()) for e in guion["escenas"])
    if not 80 <= palabras <= 150:
        avisos.append(f"El guion tiene {palabras} palabras (lo esperado es 110-130)")
    return avisos


def a_markdown(guion: dict, avisos: list[str]) -> str:
    lineas = [f"# {guion['titulo']}", ""]
    palabras = sum(len(e["frase"].split()) for e in guion["escenas"])
    lineas += [f"{len(guion['escenas'])} escenas · {palabras} palabras · ~{palabras / 2.5:.0f} s", ""]
    for i, e in enumerate(guion["escenas"], 1):
        lineas += [f"## Escena {i} · {e['cifra'] or '(sin cifra)'} — {e['etiqueta']}", "", f"> {e['frase']}", ""]
    lineas += ["## Control automático", ""]
    lineas += [f"- {a}" for a in avisos] or ["- Todas las cifras aparecen tal cual en el texto fuente."]
    lineas += ["", "## Posts", ""]
    lineas += [f"**{red}:** {post}\n" for red, post in guion["posts"].items()]
    return "\n".join(lineas)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--texto", type=Path, default=TEXTO_DEFECTO)
    p.add_argument("--solo-prompt", action="store_true")
    p.add_argument("--respuesta", type=Path)
    args = p.parse_args()

    texto = leer_texto(args.texto)
    if args.solo_prompt:
        print(PROMPT.format(texto=texto))
        return
    if not args.respuesta:
        sys.exit("Usa --solo-prompt o --respuesta respuesta.txt")

    guion = extraer_json(args.respuesta.read_text(encoding="utf-8"))
    avisos = revisar(guion, texto)
    SALIDAS.mkdir(exist_ok=True)
    (SALIDAS / "guion.json").write_text(json.dumps(guion, ensure_ascii=False, indent=2), encoding="utf-8")
    (SALIDAS / "guion.md").write_text(a_markdown(guion, avisos), encoding="utf-8")
    print(f"{len(texto.split())} palabras de entrada → {len(guion['escenas'])} escenas")
    print("\n".join(avisos) or "Todas las cifras aparecen en el texto fuente.")
    print(f"Revisa {SALIDAS / 'guion.md'} contra la fuente antes de narrar.")


if __name__ == "__main__":
    main()
