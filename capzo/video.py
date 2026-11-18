# -*- coding: utf-8 -*-
"""Generation de videos MP4 a partir d'un texte.

Honnête : on ne peut pas faire de la video photorealistique (type Sora/Veo) sur ce
PC (pas de GPU) ni gratuitement sans cle. Capzo genere donc une vraie video MP4
avec images (Pollinations), voix off (edge-tts), sous-titres esthetiques graves
dans l'image et musique d'ambiance generee. C'est illimite et gratuit.
"""
import base64
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
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

_STOP = {"dans", "avec", "pour", "cette", "leur", "plus", "sont", "elle", "ils",
         "les", "des", "une", "aux", "sur", "par", "que", "qui", "est", "ont",
         "son", "ses", "mon", "mes", "ton", "tes", "notre", "votre", "leurs",
         "depuis", "entre", "vers", "sans", "sous", "dont", "alors", "puis",
         "ainsi", "aussi", "encore", "toujours", "jamais", "tout", "tous",
         "toute", "toutes", "mais", "nous", "vous", "comme", "cela", "ete",
         "etre", "fait", "faire"}

FONT_CANDIDATS = [
    os.path.join(BASE, "static", "fonts", "DejaVuSans-Bold.ttf"),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
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
    try:
        return ImageFont.load_default(size=taille)
    except Exception:
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


def _photo_wikimedia(requete, chemin):
    """Photo reelle libre de droits (Wikimedia Commons), sans aucune cle API."""
    requete = (requete or "").strip()
    if not requete:
        return False
    params = {
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": requete, "gsrnamespace": "6", "gsrlimit": "6",
        "prop": "imageinfo", "iiprop": "url", "iiurlwidth": "1280",
    }
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    entetes = {"User-Agent": "CapzoIA/1.0 (video)"}
    try:
        req = urllib.request.Request(url, headers=entetes)
        with urllib.request.urlopen(req, timeout=25) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
    except Exception:
        return False
    pages = (data.get("query") or {}).get("pages") or {}
    for page in pages.values():
        for info in (page.get("imageinfo") or []):
            lien = info.get("thumburl") or info.get("url")
            if not lien:
                continue
            if not lien.lower().split("?")[0].endswith((".jpg", ".jpeg", ".png")):
                continue
            try:
                req = urllib.request.Request(lien, headers=entetes)
                with urllib.request.urlopen(req, timeout=40) as r:
                    b = r.read()
                if len(b) > 8000:
                    with open(chemin, "wb") as f:
                        f.write(b)
                    return True
            except Exception:
                continue
    return False


def _fond_degrade(titre, chemin):
    """Dernier recours : un fond degrade propre avec le titre, jamais du noir."""
    largeur, hauteur = 1280, 720
    img = Image.new("RGB", (largeur, hauteur))
    d = ImageDraw.Draw(img)
    for y in range(hauteur):
        f = y / float(hauteur)
        d.line([(0, y), (largeur, y)],
               fill=(int(10 + 26 * f), int(16 + 34 * f), int(44 + 74 * f)))
    d.ellipse([largeur - 420, -180, largeur + 180, 380], fill=(30, 52, 110))
    d.ellipse([-160, hauteur - 260, 340, hauteur + 160], fill=(18, 32, 74))
    titre = (titre or "Capzo").strip()
    lignes, police, y = [titre], _police(56), 0
    for taille in (56, 48, 42, 36, 30):
        police = _police(taille)
        lignes = _envelopper_texte(titre, 1100, police)
        if len(lignes) <= 2:
            break
    hauteur_ligne = int(round(police.size * 1.28)) if hasattr(police, "size") else 64
    y = hauteur // 2 - (len(lignes) * hauteur_ligne) // 2
    for ligne in lignes:
        d.text((80, y), ligne, font=police, fill=(238, 240, 250))
        y += hauteur_ligne
    d.text((80, y + 6), "Capzo IA", font=_police(26), fill=(150, 162, 190))
    img.save(chemin, "JPEG", quality=92)
    return chemin


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
        pass
    # 2e chance : photo reelle libre (Wikimedia Commons)
    texte_base = (prompt or "") + " " + (segment or "")
    jetons = [re.sub(r"[^\w\-]+", "", m) for m in texte_base.split()]
    jetons = [m for m in jetons if len(m) > 3 and m.lower() not in _STOP]
    essais = []
    if jetons:
        essais.append(" ".join(jetons[:4]))
        if len(jetons) >= 2:
            essais.append(" ".join(jetons[:2]))
    for requete in essais:
        try:
            if _photo_wikimedia(requete, chemin):
                return chemin
        except Exception:
            continue
    # 3e chance : fond degrade avec le titre (jamais une image noire)
    return _fond_degrade(segment or prompt, chemin)


def _envelopper_texte(texte, largeur_px, police):
    mots = (texte or "").split()
    lignes, courante = [], ""
    mesure = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    for mot in mots:
        essai = (courante + " " + mot).strip()
        try:
            largeur = mesure.textlength(essai, font=police)
        except Exception:
            largeur = len(essai) * 20
        if largeur <= largeur_px or not courante:
            courante = essai
        else:
            lignes.append(courante)
            courante = mot
    if courante:
        lignes.append(courante)
    if len(lignes) > 3:
        lignes = lignes[:2] + [" ".join(lignes[2:])]
    return lignes


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
