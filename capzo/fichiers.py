# -*- coding: utf-8 -*-
"""Lecture des pieces jointes : texte, PDF, images et videos.

Tout est fait en local : aucun fichier n'est envoye sur Internet.
"""
import base64
import io
import os
import re
import subprocess
import tempfile

from PIL import Image

TEXT_EXT = {
    ".txt", ".md", ".markdown", ".csv", ".tsv", ".json", ".log", ".ini", ".cfg",
    ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".htm", ".css", ".xml", ".yml",
    ".yaml", ".toml", ".bat", ".cmd", ".ps1", ".sh", ".sql", ".c", ".h", ".cpp",
    ".java", ".php", ".rb", ".go", ".rs",
}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff"}
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".wmv", ".flv"}

MAX_TEXTE = 8000
MAX_B64 = None  # pas de limite utile : les images sont redimensionnees


def genre(nom, mime=""):
    ext = os.path.splitext(nom or "")[1].lower()
    mime = (mime or "").lower()
    if ext in IMAGE_EXT or mime.startswith("image/"):
        return "image"
    if ext in VIDEO_EXT or mime.startswith("video/"):
        return "video"
    if ext == ".pdf" or mime == "application/pdf":
        return "pdf"
    if ext in TEXT_EXT or mime.startswith("text/") or mime in ("application/json", "application/xml"):
        return "texte"
    return "autre"


def _lire_pdf(chemin, maxi=MAX_TEXTE):
    try:
        from pypdf import PdfReader  # optionnel
    except Exception:
        return ""
    try:
        lecteur = PdfReader(chemin)
        morceaux = []
        for page in lecteur.pages[:20]:
            morceaux.append(page.extract_text() or "")
            if sum(len(m) for m in morceaux) > maxi:
                break
        return "\n".join(morceaux).strip()[:maxi]
    except Exception:
        return ""


def extraire_texte(chemin, maxi=MAX_TEXTE):
    """Renvoie le texte d'un fichier (ou une chaine vide)."""
    if not chemin or not os.path.isfile(chemin):
        return ""
    ext = os.path.splitext(chemin)[1].lower()
    if ext == ".pdf":
        return _lire_pdf(chemin, maxi)
    try:
        with open(chemin, "rb") as f:
            brut = f.read(maxi * 4)
    except Exception:
        return ""
    for encodage in ("utf-8", "utf-16", "cp1252", "latin-1"):
        try:
            return brut.decode(encodage)[:maxi].strip()
        except Exception:
            continue
    return brut.decode("utf-8", "replace")[:maxi].strip()


def image_b64(chemin, max_cote=1024, qualite=85):
    """Redimensionne l'image et la renvoie en base64 (JPEG)."""
    try:
        with Image.open(chemin) as im:
            im = im.convert("RGB")
            im.thumbnail((max_cote, max_cote))
            tampon = io.BytesIO()
            im.save(tampon, "JPEG", quality=qualite, optimize=True)
        return base64.b64encode(tampon.getvalue()).decode("ascii")
    except Exception:
        return ""


def _duree(chemin):
    sortie = ""
    try:
        sortie = subprocess.run(
            [_ffmpeg(), "-i", chemin],
            capture_output=True, timeout=30,
        ).stderr.decode("utf-8", "replace")
    except Exception:
        pass
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", sortie or "")
    if not m:
        return 0.0
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def _ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def frames_video_b64(chemin, nombre=2, max_cote=768):
    """Extrait quelques images d'une video et les renvoie en base64."""
    images = []
    duree = _duree(chemin)
    if duree <= 0:
        instants = [0]
    else:
        pas = duree / (nombre + 1)
        instants = [pas * (i + 1) for i in range(nombre)]
    dossier = tempfile.mkdtemp(prefix="capzo_frame_")
    for i, t in enumerate(instants):
        sortie = os.path.join(dossier, f"f{i}.jpg")
        try:
            subprocess.run(
                [_ffmpeg(), "-y", "-ss", f"{t:.2f}", "-i", chemin, "-frames:v", "1",
                 "-vf", f"scale='min({max_cote},iw)':-2", sortie],
                capture_output=True, timeout=60,
            )
        except Exception:
            continue
        if os.path.isfile(sortie) and os.path.getsize(sortie) > 0:
            b64 = image_b64(sortie, max_cote=max_cote)
            if b64:
                images.append(b64)
        try:
            os.remove(sortie)
        except Exception:
            pass
    try:
        os.rmdir(dossier)
    except Exception:
        pass
    return images
