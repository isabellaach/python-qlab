"""Guion revisado + mi voz clonada + imágenes del dashboard + música → reel.mp4 (1080×1920) con subtítulos.

Adaptado de mi reel de la Tarea 2 (flujo de la sesión 15 del curso): voz con Qwen3-TTS, control de calidad
y subtítulos con Whisper, cuadros con Pillow y video con ffmpeg (incluido en imageio-ffmpeg).

Uso:
    .venv/bin/python hacer_reel.py --voz recursos/mi_voz.m4a --texto-voz recursos/texto_voz.txt \
        --musica recursos/musica.mp3 --credito-musica "Título – Autor (Pixabay)"

Lee guion.json (revisado a mano) y recursos/img/ (capturas del dashboard, ver capturas.py).
Escribe en salidas/: reel.wav, reel.mp4, reel.srt, portada.png.
"""

import argparse
import json
import subprocess
import textwrap
from pathlib import Path

import imageio_ffmpeg
import jiwer
import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw, ImageFont

AQUI = Path(__file__).parent
SALIDAS = AQUI / "salidas"
IMG = AQUI / "recursos" / "img"
TABLERO = "isabellaach.github.io/python-qlab/tarea_3/web"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

ANCHO, ALTO, FPS = 1080, 1920, 30
PAUSA = 0.35          # silencio entre escenas (s)
MAX_ERROR = 0.25      # si Whisper entiende mal más del 25 % de las palabras, se repite la escena
AVISO_IA = "Voz generada con IA"

FONDO = (30, 26, 43)        # tinta del dashboard (#1E1A2B)
TEXTO = (242, 239, 248)
GRIS = (183, 177, 198)
NARANJA = (240, 138, 75)    # naranja "informal" en versión clara para fondo oscuro
MORADO = (169, 139, 240)
FUENTE_NEGRA = str(AQUI / "recursos" / "fuentes" / "DMSerifDisplay-Regular.ttf")   # la misma serif del dashboard (OFL)
FUENTE_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
FUENTE = "/System/Library/Fonts/Supplemental/Arial.ttf"


def fuente(ruta, tam):
    return ImageFont.truetype(ruta, tam)


# ---------- Voz ----------

# Limpieza de la grabación del celular: corta graves (golpes, aire), baja el ruido de fondo,
# quita silencios al inicio y al final y nivela el volumen
LIMPIAR_VOZ = ("highpass=f=80,afftdn=nf=-25,"
               "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.15,areverse,"
               "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.15,areverse,"
               "loudnorm=I=-18:TP=-2")


def a_wav(origen: Path, destino: Path, sr=24000, filtro=None):
    cmd = [FFMPEG, "-y", "-loglevel", "error", "-i", str(origen), "-ac", "1", "-ar", str(sr)]
    cmd += ["-af", filtro] if filtro else []
    subprocess.run(cmd + [str(destino)], check=True)


def escuchar(whisper, ruta: Path, **kw):
    """Whisper sobre un audio decodificado con ffmpeg (16 kHz, mono)."""
    tmp = SALIDAS / "_16k.wav"
    a_wav(ruta, tmp, sr=16000)
    audio, _ = sf.read(tmp, dtype="float32")
    segs, _ = whisper.transcribe(audio, language="es", **kw)
    return list(segs)


def error_palabras(esperado: str, oido: str) -> float:
    import re
    from num2words import num2words
    # Whisper escribe "3 372" o "161"; el guion los dice en palabras
    oido = re.sub(r"\d+(?:[ .,]\d{3})*", lambda m: " " + num2words(int(re.sub(r"\D", "", m.group())), lang="es") + " ", oido)
    limpiar = lambda s: " ".join(re.sub(r"[^\wáéíóúñü ]", " ", s.lower()).split())
    return jiwer.wer(limpiar(esperado), limpiar(oido))


def narrar(escenas, voz: Path, ref_texto: str | None, modelo_tts: str, device: str, dtype: str, whisper):
    import torch
    from qwen_tts import Qwen3TTSModel

    ref = SALIDAS / "mi_voz.wav"
    a_wav(voz, ref, filtro=LIMPIAR_VOZ)
    oido = " ".join(s.text.strip() for s in escuchar(whisper, ref))
    print(f"Whisper oye en tu grabación: «{oido}»")
    if ref_texto:
        # El clon sale mejor con la transcripción exacta que con la de Whisper
        print(f"Diferencia con el texto leído: {error_palabras(ref_texto, oido):.0%}")
    ref_texto = ref_texto or oido

    # bfloat16 usa la mitad de memoria: el 1.7B en float32 no entra bien en una Mac de 16 GB
    tts = Qwen3TTSModel.from_pretrained(modelo_tts, device_map=device, dtype=getattr(torch, dtype))
    prompt = tts.create_voice_clone_prompt(ref_audio=str(ref), ref_text=ref_texto)

    audios, sr = [], None
    for i, e in enumerate(escenas, 1):
        tmp = SALIDAS / f"escena_{i}.wav"
        mejor = None
        for intento in range(3):
            wavs, sr = tts.generate_voice_clone(text=e["frase"], language="spanish", voice_clone_prompt=prompt)
            sf.write(tmp, wavs[0], sr)
            err = error_palabras(e["frase"], " ".join(s.text for s in escuchar(whisper, tmp)))
            print(f"Escena {i}, intento {intento + 1}: {len(wavs[0]) / sr:.1f} s, error {err:.0%}", flush=True)
            if mejor is None or err < mejor[0]:
                mejor = (err, wavs[0])
            if err <= MAX_ERROR:
                break
        sf.write(tmp, mejor[1], sr)  # se queda el intento con menos error
        audios.append(mejor[1])
    return audios, sr


# ---------- Subtítulos ----------

def palabras_con_tiempo(wav: Path, frase: str, inicio: float, whisper):
    """Texto del guion revisado con los tiempos de Whisper.

    Whisper solo da dónde empieza y termina el habla de la escena (transcribe mal
    números y nombres propios); las palabras se reparten en ese tramo según su largo.
    """
    oidas = [w for s in escuchar(whisper, wav, word_timestamps=True) for w in s.words]
    ini, fin = (oidas[0].start, oidas[-1].end) if oidas else (0.0, sf.info(wav).duration)
    tokens = frase.split()
    pesos = np.cumsum([0] + [len(w) + 1 for w in tokens])
    cortes = inicio + ini + (fin - ini) * pesos / pesos[-1]
    return [(cortes[i], cortes[i + 1], w) for i, w in enumerate(tokens)]


def grupos(palabras, n=4):
    """Junta las palabras de a n para mostrarlas en pantalla."""
    return [palabras[i:i + n] for i in range(0, len(palabras), n)]


def srt(por_escena) -> str:
    def t(x):
        h, r = divmod(x, 3600)
        m, s = divmod(r, 60)
        return f"{int(h):02}:{int(m):02}:{int(s):02},{int((s % 1) * 1000):03}"
    bloques = []
    for i, g in enumerate((g for p in por_escena for g in grupos(p, 7)), 1):
        bloques.append(f"{i}\n{t(g[0][0])} --> {t(g[-1][1])}\n{' '.join(w for _, _, w in g)}\n")
    return "\n".join(bloques)


# ---------- Cuadros ----------

def centrado(d, y, texto, f, color):
    w = d.textlength(texto, font=f)
    d.text(((ANCHO - w) / 2, y), texto, font=f, fill=color)


CAJA_IMG = (60, 330, 1020, 960)   # caja de la imagen de la escena
ZOOM = 0.05                        # acercamiento lento a lo largo de cada escena


def aviso_ia(img):
    """Etiqueta fija, arriba a la derecha, durante todo el video."""
    d = ImageDraw.Draw(img)
    f = fuente(FUENTE_BOLD, 26)
    w = d.textlength(AVISO_IA, font=f)
    x1, y0 = ANCHO - 90, 220
    d.rounded_rectangle((x1 - w - 66, y0, x1, y0 + 48), radius=24, fill=(58, 36, 20), outline=NARANJA, width=3)
    d.ellipse((x1 - w - 46, y0 + 18, x1 - w - 34, y0 + 30), fill=NARANJA)
    d.text((x1 - w - 22, y0 + 10), AVISO_IA, font=f, fill=NARANJA)


def base_escena(e, titulo, n, total):
    img = Image.new("RGB", (ANCHO, ALTO), FONDO)
    d = ImageDraw.Draw(img)
    # Zonas seguras: nada importante en los 210 px de arriba ni en los 420 de abajo
    d.text((90, 231), titulo.upper(), font=fuente(FUENTE_BOLD, 26), fill=GRIS)
    d.text((90, 1840 - 420 + 40), "Fuente: INEI, ENAHO 2015–2025 · Elaboración propia", font=fuente(FUENTE, 26), fill=GRIS)
    if e.get("credito"):
        d.text((90, 1840 - 420 + 78), e["credito"], font=fuente(FUENTE, 24), fill=GRIS)
    d.rectangle((90, 292, 90 + (ANCHO - 180) * n / total, 298), fill=NARANJA)
    if e["cifra"]:
        centrado(d, 975, e["cifra"], fuente(FUENTE_NEGRA, 112), NARANJA)
        for j, linea in enumerate(textwrap.wrap(e["etiqueta"], 38)[:2]):
            centrado(d, 1110 + j * 50, linea, fuente(FUENTE_BOLD, 40), TEXTO)
    else:
        for j, linea in enumerate(textwrap.wrap(e["etiqueta"], 26)):
            centrado(d, 990 + j * 74, linea, fuente(FUENTE_NEGRA, 60), NARANJA)
    aviso_ia(img)
    return img


def recortar_blanco(foto):
    """Quita los márgenes casi blancos de una captura."""
    from PIL import ImageChops
    gris = ImageChops.invert(foto.convert("L")).point(lambda v: 255 if v > 18 else 0)
    caja = gris.getbbox()
    return foto.crop(caja) if caja else foto


def cubrir(foto):
    """Recorta la foto para llenar la caja completa (sin bordes), con esquinas redondeadas."""
    x0, y0, x1, y1 = CAJA_IMG
    W, H = x1 - x0, y1 - y0
    esc = max(W / foto.width, H / foto.height)
    f = foto.resize((int(foto.width * esc) + 1, int(foto.height * esc) + 1), Image.LANCZOS)
    l, t = (f.width - W) // 2, (f.height - H) // 3
    f = f.crop((l, t, l + W, t + H))
    mascara = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mascara).rounded_rectangle((0, 0, W - 1, H - 1), radius=28, fill=255)
    fondo = Image.new("RGB", (W, H), FONDO)
    fondo.paste(f, (0, 0), mascara)
    return fondo


def encajar(foto):
    """Ajusta la captura a la caja sin deformarla, sobre una tarjeta clara con bordes redondeados."""
    x0, y0, x1, y1 = CAJA_IMG
    W, H = x1 - x0, y1 - y0
    tarjeta = Image.new("RGB", (W, H), FONDO)
    d = ImageDraw.Draw(tarjeta)
    d.rounded_rectangle((0, 0, W - 1, H - 1), radius=28, fill=(246, 243, 238))
    f = recortar_blanco(foto)
    esc = min((W - 48) / f.width, (H - 48) / f.height)
    f = f.resize((int(f.width * esc), int(f.height * esc)), Image.LANCZOS)
    tarjeta.paste(f, ((W - f.width) // 2, (H - f.height) // 2))
    return tarjeta


def pegar_imagen(img, foto, avance):
    """Pega la imagen de la escena con un zoom lento (avance de 0 a 1). `foto` puede ser una lista de cuadros (animación)."""
    if foto is None:
        return
    if isinstance(foto, list):  # mapa animado: recorre los años a lo largo de la escena
        k = min(len(foto) - 1, int(avance * len(foto) * 1.25))
        foto = foto[k]
        z = 1.0
    else:
        z = 1 + ZOOM * avance
    x0, y0, x1, y1 = CAJA_IMG
    w, h = foto.width / z, foto.height / z
    cx, cy = foto.width / 2, foto.height / 2
    caja = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
    img.paste(foto.resize((x1 - x0, y1 - y0), Image.BILINEAR, box=caja), (x0, y0))


def dibujar_subtitulo(img, grupo, t):
    d = ImageDraw.Draw(img)
    f = fuente(FUENTE_BOLD, 58)
    texto = " ".join(w for _, _, w in grupo)
    lineas = textwrap.wrap(texto, 24, break_long_words=False)
    y = 1245
    k = 0
    for linea in lineas:
        x = (ANCHO - d.textlength(linea, font=f)) / 2
        for palabra in linea.split():
            ini, fin, _ = grupo[k]
            color = NARANJA if ini <= t < fin + 0.05 else TEXTO
            d.text((x, y), palabra, font=f, fill=color, stroke_width=3, stroke_fill=(0, 0, 0))
            x += d.textlength(palabra + " ", font=f)
            k += 1
        y += 76


def anotar_anio(tarjeta, anio):
    """Año grande sobre el mapa animado."""
    d = ImageDraw.Draw(tarjeta)
    d.text((tarjeta.width - 300, tarjeta.height - 170), str(anio), font=fuente(FUENTE_NEGRA, 110), fill=(74, 44, 130))
    return tarjeta


def cierre(autor, fuentes, musica):
    img = Image.new("RGB", (ANCHO, ALTO), FONDO)
    d = ImageDraw.Draw(img)
    centrado(d, 470, "Explora el tablero", fuente(FUENTE_NEGRA, 72), NARANJA)
    centrado(d, 575, TABLERO, fuente(FUENTE_BOLD, 34), MORADO)
    centrado(d, 760, autor, fuente(FUENTE_BOLD, 58), TEXTO)
    y = 860
    for linea in textwrap.wrap("Datos: " + fuentes, 40):
        centrado(d, y, linea, fuente(FUENTE, 38), GRIS); y += 50
    if musica:
        for linea in textwrap.wrap("Música: " + musica, 40):
            centrado(d, y + 10, linea, fuente(FUENTE, 34), GRIS); y += 46
    for linea in textwrap.wrap("Foto: Diego Delso (Wikimedia Commons), CC BY-SA 4.0", 40):
        centrado(d, y + 10, linea, fuente(FUENTE, 34), GRIS); y += 46
    centrado(d, y + 70, AVISO_IA + " (Qwen3-TTS, a partir de mi voz)", fuente(FUENTE_BOLD, 38), NARANJA)
    aviso_ia(img)
    return img


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--voz", type=Path, required=True)
    p.add_argument("--texto-voz", type=Path, help="lo que dices en la grabación, palabra por palabra")
    p.add_argument("--autor", default="Isabella Albarrán")
    p.add_argument("--fuente", default="INEI, Encuesta Nacional de Hogares (ENAHO) 2015–2025")
    p.add_argument("--musica", type=Path, help="pista de fondo con licencia de uso")
    p.add_argument("--credito-musica", default="")
    p.add_argument("--vol-musica", type=float, default=0.12, help="volumen de la música (la voz queda en 1.0)")
    p.add_argument("--tts", default="Qwen/Qwen3-TTS-12Hz-1.7B-Base")
    p.add_argument("--device", default="mps")
    p.add_argument("--dtype", default="bfloat16", choices=["bfloat16", "float16", "float32"])
    p.add_argument("--reusar-voz", action="store_true", help="usa los salidas/escena_*.wav ya narrados")
    args = p.parse_args()

    from faster_whisper import WhisperModel
    whisper = WhisperModel("small", device="cpu", compute_type="int8")
    SALIDAS.mkdir(exist_ok=True)
    guion = json.loads((AQUI / "guion.json").read_text(encoding="utf-8"))
    escenas = guion["escenas"]
    if any("¡¡" in e["cifra"] + e["etiqueta"] for e in escenas):
        raise SystemExit("Hay cifras marcadas con ¡¡ en guion.json: corrígelas antes de narrar.")

    # 4. Voz
    if args.reusar_voz:
        leidos = [sf.read(SALIDAS / f"escena_{i}.wav", dtype="float32") for i in range(1, len(escenas) + 1)]
        audios, sr = [a for a, _ in leidos], leidos[0][1]
    else:
        ref_texto = args.texto_voz.read_text(encoding="utf-8").strip() if args.texto_voz else None
        audios, sr = narrar(escenas, args.voz, ref_texto, args.tts, args.device, args.dtype, whisper)
    silencio = np.zeros(int(PAUSA * sr), dtype=np.float32)
    inicios, partes, t = [], [], 0.0
    for a in audios:
        inicios.append(t)
        partes += [a.astype(np.float32), silencio]
        t += len(a) / sr + PAUSA
    cola = 2.5  # segundos de cierre
    partes.append(np.zeros(int(cola * sr), dtype=np.float32))
    wav = SALIDAS / "reel.wav"
    sf.write(wav, np.concatenate(partes), sr)
    duracion = t + cola

    # 5. Subtítulos: tiempos de Whisper escena por escena, texto del guion
    por_escena = [palabras_con_tiempo(SALIDAS / f"escena_{i}.wav", e.get("subtitulo") or e["frase"], inicios[i - 1], whisper)
                  for i, e in enumerate(escenas, 1)]
    (SALIDAS / "reel.srt").write_text(srt(por_escena), encoding="utf-8")
    subt = [g for p in por_escena for g in grupos(p)]

    bases = [base_escena(e, guion["titulo"], i + 1, len(escenas)) for i, e in enumerate(escenas)]
    def cargar(nombre):
        if nombre == "mapa_anim":
            return [anotar_anio(encajar(Image.open(IMG / f"mapa_{a}.png").convert("RGB")), a) for a in range(2015, 2026)]
        img = Image.open(IMG / f"{nombre}.png").convert("RGB")
        return cubrir(img) if nombre == "foto" else encajar(img)
    fotos = [cargar(e["imagen"]) if e.get("imagen") else None for e in escenas]
    portada = bases[0].copy()
    pegar_imagen(portada, fotos[0], 0)
    portada = portada  # la portada no lleva subtítulos
    portada.save(SALIDAS / "portada.png")
    final = cierre(args.autor, args.fuente, args.credito_musica)

    video = subprocess.Popen([
        FFMPEG, "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{ANCHO}x{ALTO}", "-r", str(FPS), "-i", "-",
        "-i", str(wav),
        *(["-stream_loop", "-1", "-i", str(args.musica)] if args.musica else []),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium", "-crf", "23",
        *(["-filter_complex",
           f"[2:a]volume={args.vol_musica},afade=t=in:d=1.5,afade=t=out:st={duracion - 3:.2f}:d=3[m];"
           f"[1:a][m]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[a]",
           "-map", "0:v", "-map", "[a]"] if args.musica else ["-af", "loudnorm=I=-14:TP=-1.5:LRA=11"]),
        "-c:a", "aac", "-b:a", "128k", "-ar", "48000",
        "-shortest", "-movflags", "+faststart", str(SALIDAS / "reel.mp4"),
    ], stdin=subprocess.PIPE)
    for f in range(int(duracion * FPS)):
        t = f / FPS
        if t >= duracion - cola:
            img = final
        else:
            n = max(i for i, ini in enumerate(inicios) if ini <= t)
            fin_escena = inicios[n + 1] if n + 1 < len(inicios) else duracion - cola
            img = bases[n].copy()
            pegar_imagen(img, fotos[n], (t - inicios[n]) / (fin_escena - inicios[n]))
            g = next((g for g in subt if g[0][0] - 0.1 <= t <= g[-1][1] + 0.2), None)
            if g:
                dibujar_subtitulo(img, g, t)
        video.stdin.write(img.tobytes())
    video.stdin.close()
    video.wait()

    print(f"Listo: {SALIDAS / 'reel.mp4'} ({duracion:.1f} s)")


if __name__ == "__main__":
    main()
