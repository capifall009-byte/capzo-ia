# -*- coding: utf-8 -*-
"""Voix neuronales pour Capzo IA.

Utilise edge-tts (voix Microsoft, gratuit, sans cle API).
Si Internet manque, l'appelant retombe sur la voix du navigateur.
"""
import asyncio
import hashlib
import re
import threading

try:
    import edge_tts
    DISPONIBLE = True
except Exception:  # pragma: no cover
    edge_tts = None
    DISPONIBLE = False

# Voix francaises proposees (nom technique -> libelle lisible)
VOIX = [
    {"id": "fr-FR-DeniseNeural", "nom": "Denise · femme, chaleureuse (France)"},
    {"id": "fr-FR-HenriNeural", "nom": "Henri · homme, hyper-réaliste (France)"},
    {"id": "fr-FR-EloiseNeural", "nom": "Éloïse · jeune (France)"},
    {"id": "fr-FR-RemyMultilingualNeural", "nom": "Rémy · homme, moderne (multilingue)"},
    {"id": "fr-CA-SylvieNeural", "nom": "Sylvie · femme (Québec)"},
    {"id": "fr-CA-AntoineNeural", "nom": "Antoine · homme (Québec)"},
]
VOIX_DEFAUT = "fr-FR-HenriNeural"

_cache = {}
_cache_ordre = []
_cache_max = 40
_verrou = threading.Lock()


def _nettoyer_cache():
    while len(_cache_ordre) > _cache_max:
        vieux = _cache_ordre.pop(0)
        _cache.pop(vieux, None)


def couper_en_phrases(texte, max_chars=220):
    """Decoupe un texte en morceaux courts, jouables pendant le flux."""
    texte = (texte or "").strip()
    if not texte:
        return []
    # on coupe apres . ! ? … ; ou tous les max_chars
    morceaux = re.split(r"(?<=[.!?…])\s+", texte)
    sortie, courant = [], ""
    for m in morceaux:
        m = m.strip()
        if not m:
            continue
        if len(courant) + len(m) + 1 <= max_chars:
            courant = (courant + " " + m).strip()
        else:
            if courant:
                sortie.append(courant)
            while len(m) > max_chars:
                sortie.append(m[:max_chars])
                m = m[max_chars:]
            courant = m
    if courant:
        sortie.append(courant)
    return sortie


def _lancer(coro):
    """Execute une coroutine edge-tts dans un event loop prive (thread-safe)."""
    try:
        return asyncio.run(coro)
    except RuntimeError:
        boucle = asyncio.new_event_loop()
        try:
            return boucle.run_until_complete(coro)
        finally:
            boucle.close()


async def _generer(texte, voix, debit, hauteur):
    communication = edge_tts.Communicate(texte, voix, rate=debit, pitch=hauteur)
    audio = bytearray()
    async for morceau in communication.stream():
        if morceau.get("type") == "audio" and morceau.get("data"):
            audio.extend(morceau["data"])
    return bytes(audio)


def synthese(texte, voix=VOIX_DEFAUT, debit="+0%", hauteur="+0Hz"):
    """Retourne (audio_mp3, erreur). audio_mp3 vaut None en cas d'echec."""
    texte = (texte or "").strip()
    if not texte:
        return None, "Texte vide."
    if not DISPONIBLE:
        return None, "edge-tts n'est pas installe (pip install edge-tts)."
    if voix not in {v["id"] for v in VOIX}:
        voix = VOIX_DEFAUT

    cle = hashlib.sha1((voix + "|" + debit + "|" + hauteur + "|" + texte).encode("utf-8")).hexdigest()
    with _verrou:
        if cle in _cache:
            return _cache[cle], None

    try:
        audio = _lancer(_generer(texte[:1200], voix, debit, hauteur))
    except Exception as e:  # pas d'internet, service indisponible...
        return None, str(e)[:200]
    if not audio:
        return None, "Aucun audio recu."

    with _verrou:
        _cache[cle] = audio
        _cache_ordre.append(cle)
        _nettoyer_cache()
    return audio, None
