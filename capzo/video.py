# -*- coding: utf-8 -*-
"""Generation de videos MP4 a partir d'un texte.

Honnête : on ne peut pas faire de la video photorealistique (type Sora/Veo) sur ce
PC (pas de GPU) ni gratuitement sans cle. Capzo genere donc une vraie video MP4
avec images (Pollinations), voix off (edge-tts), sous-titres esthetiques graves
dans l'image et musique d'ambiance generee. C'est illimite et gratuit.
"""
import base64
import os
import shutil
import subprocess
import tempfile
import time
import uuid

from PIL import Image, ImageDraw, ImageFont

from . import images, voix

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSSIER = os.path.join(BASE, "uploads", "videos")
os.makedirs(DOSSIER, exist_ok=True)

try:
    import imageio_ffmpeg
    FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG = "ffmpeg"

FONT_CANDIDATS = [
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\segoeuib.ttf",
    r"C:\Windows\Fonts\calibrib.ttf",
    r"C:\Windows\Fonts\arial.ttf",
]


def _police(taille):
    for chemin in FONT_CANDIDATS:
        if os.path.exists(chemin):
            try:
                return ImageFont.truetype(chemin, taille)
            except Exception:
                continue
    return ImageFont.load_default()


def _ffmpeg(args, timeout=300):
    r = subprocess.run([FFMPEG] + list(args), capture_output=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or b"").decode("utf-8", "replace")[-400:])


def _segmenter(texte):
    texte = (texte or "").strip()
    if not texte:
        return []
    morceaux = []
    for phrase in __import__("re").split(r"(?<=[.!?…])\s+", texte):
        phrase = phrase.strip()
        if phrase:
            morceaux.append(phrase)
    if not morceaux:
        morceaux = [texte]
    # regrouper les phrases trop courtes
    sortie, courant = [], ""
    for m in morceaux:
        if len(courant) + len(m) + 1 <= 110:
            courant = (courant + " " + m).strip()
        else:
            if courant:
                sortie.append(courant)
            courant = m
    if courant:
        sortie.append(courant)
    return sortie[:6]


def _generer_image(prompt, segment, chemin):
    p = (prompt + ", " + segment[:90]).strip()[:500]
    full = "cinematic still, high quality, detailed, atmospheric lighting, " + p
    try:
        data_url = images.generer_data_url(full, seed=abs(hash(segment)) % 100000, taille=768)
        _, b64 = data_url.split(",", 1)
        data = base64.b64decode(b64)
        with open(chemin, "wb") as f:
            f.write(data)
        return chemin
    except Exception:
        img = Image.new("RGB", (768, 768), (18, 20, 32))
        d = ImageDraw.Draw(img)
        d.text((40, 360), "Capzo", fill=(80, 80, 100), font=_police(40))
        img.save(chemin)
        return chemin


def _envelopper_texte(texte, largeur_px, police):
    mots = (texte or "").split()
    lignes, courante = [], ""
    # estime ~10 px par caractere pour arial 34
    max_chars = max(20, largeur_px // 18)
    for mot in mots:
        if len(courante) + len(mot) + 1 <= max_chars:
            courante = (courante + " " + mot).strip()
        else:
            if courante:
                lignes.append(courante)
            courante = mot
    if courante:
        lignes.append(courante)
    return lignes[:3]


def _bruler_sous_titre(img_path, out_path, texte):
    img = Image.open(img_path).convert("RGB")
    # redimensionner en 1280x720 (cover)
    cible = (1280, 720)
    ratio = max(cible[0] / img.width, cible[1] / img.height)
    nw, nh = int(img.width * ratio), int(img.height * ratio)
    img = img.resize((nw, nh), Image.LANCZOS)
    x0, y0 = (nw - cible[0]) // 2, (nh - cible[1]) // 2
    img = img.crop((x0, y0, x0 + cible[0], y0 + cible[1]))

    if texte:
        draw = ImageDraw.Draw(img, "RGBA")
        police = _police(38)
        lignes = _envelopper_texte(texte, 1180, police)
        # hauteur du bloc
        hauteur_ligne = 46
        bloc = len(lignes) * hauteur_ligne + 18
        y_base = 720 - bloc - 28
        # fond semi-transparent
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        od.rounded_rectangle([40, y_base - 10, 1240, y_base + bloc + 4],
                             radius=14, fill=(0, 0, 0, 150))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(img)
        y = y_base
        for ligne in lignes:
            # ombre
            draw.text((65, y + 2), ligne, font=police, fill=(0, 0, 0, 230))
            draw.text((62, y), ligne, font=police, fill=(255, 255, 255, 255))
            y += hauteur_ligne
    img.save(out_path, "JPEG", quality=92)


def _silence(duree, chemin):
    _ffmpeg(["-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", f"{duree:.2f}",
             "-q:a", "9", "-y", chemin])


def _construire_narration(tts_liste, durees, sortie):
    tmp = os.path.dirname(sortie)
    liste = os.path.join(tmp, "audio_liste.txt")
    with open(liste, "w", encoding="utf-8") as f:
        for i, (tts, dur) in enumerate(zip(tts_liste, durees)):
            if tts and os.path.exists(tts):
                f.write(f"file '{tts.replace(chr(92), '/')}'\n")
            else:
                sil = os.path.join(tmp, f"sil_{i}.mp3")
                _silence(dur, sil)
                f.write(f"file '{sil.replace(chr(92), '/')}'\n")
            f.write(f"duration {dur:.2f}\n")
        # evite le trou final
        dernier = tts_liste[-1] if tts_liste else None
        if dernier and os.path.exists(dernier):
            f.write(f"file '{dernier.replace(chr(92), '/')}'\n")
        else:
            f.write(f"file '{os.path.join(tmp, 'sil_' + str(len(durees)-1) + '.mp3').replace(chr(92), '/')}'\n")
    _ffmpeg(["-f", "concat", "-safe", "0", "-i", liste, "-c:a", "libmp3lame", "-q:a", "6", "-y", sortie])


def _generer_musique(duree, sortie):
    # Pad ambient : quelques sinusoïdes douces, volume tres bas, fade in/out
    filtres = ("[0][1][2]amix=inputs=3:duration=first,"
               "volume=0.07,afade=t=in:st=0:d=2,afade=t=out:st={d}:d=2".format(d=max(1, duree - 2)))
    _ffmpeg([
        "-f", "lavfi", "-i", f"sine=frequency=196:duration={duree:.2f}",
        "-f", "lavfi", "-i", f"sine=frequency=294:duration={duree:.2f}",
        "-f", "lavfi", "-i", f"sine=frequency=392:duration={duree:.2f}",
        "-filter_complex", filtres,
        "-c:a", "libmp3lame", "-q:a", "6", "-y", sortie,
    ], timeout=120)


def _mixer_audio(narration, musique, sortie):
    _ffmpeg([
        "-i", narration, "-i", musique,
        "-filter_complex", "[1]volume=0.18[m];[0][m]amix=inputs=2:duration=first:dropout_transition=2",
        "-c:a", "aac", "-b:a", "128k", "-y", sortie,
    ])


def _convertir_audio(src, dst):
    _ffmpeg(["-i", src, "-c:a", "aac", "-b:a", "128k", "-y", dst])


def generer(prompt, narration, sous_titres=True, musique=True):
    """Genere une video MP4. Retourne le chemin URL relatif (/api/video/<id>.mp4)."""
    ident = uuid.uuid4().hex[:10]
    sortie = os.path.join(DOSSIER, ident + ".mp4")
    tmp = tempfile.mkdtemp(prefix="capzo_vid_")
    try:
        segments = _segmenter(narration)
        if not segments:
            segments = [narration or prompt or "Une scene se dessine."]
        durees = [max(3.0, min(8.0, len(s) / 12.0 + 1.5)) for s in segments]

        # images
        imgs = []
        for i, seg in enumerate(segments):
            chemin = os.path.join(tmp, f"img_{i}.jpg")
            _generer_image(prompt, seg, chemin)
            imgs.append(chemin)

        # sous-titres graves dans l'image
        subs = []
        for i, (seg, _) in enumerate(zip(segments, durees)):
            out = os.path.join(tmp, f"sub_{i}.jpg")
            _bruler_sous_titre(imgs[i], out, seg if sous_titres else "")
            subs.append(out)

        # voix off
        tts_liste = []
        for seg in segments:
            audio, _ = voix.synthese(seg)
            if audio:
                chemin = os.path.join(tmp, f"tts_{len(tts_liste)}.mp3")
                with open(chemin, "wb") as f:
                    f.write(audio)
                tts_liste.append(chemin)
            else:
                tts_liste.append(None)

        narration_mp3 = os.path.join(tmp, "narration.mp3")
        _construire_narration(tts_liste, durees, narration_mp3)

        total = sum(durees)
        audio_final = os.path.join(tmp, "audio.m4a")
        if musique:
            music_mp3 = os.path.join(tmp, "music.mp3")
            try:
                _generer_musique(total, music_mp3)
                _mixer_audio(narration_mp3, music_mp3, audio_final)
            except Exception:
                _convertir_audio(narration_mp3, audio_final)
        else:
            _convertir_audio(narration_mp3, audio_final)

        # concat des images
        liste = os.path.join(tmp, "liste.txt")
        with open(liste, "w", encoding="utf-8") as f:
            for i, dur in enumerate(durees):
                f.write(f"file '{subs[i].replace(chr(92), '/')}'\n")
                f.write(f"duration {dur:.2f}\n")
            f.write(f"file '{subs[-1].replace(chr(92), '/')}'\n")

        _ffmpeg([
            "-f", "concat", "-safe", "0", "-i", liste,
            "-i", audio_final,
            "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,"
                   "pad=1280:720:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
            "-r", "24", "-c:a", "aac", "-b:a", "128k",
            "-shortest", "-movflags", "+faststart", "-y", sortie,
        ], timeout=300)

        return "/api/video/" + ident + ".mp4"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
