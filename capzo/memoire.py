# -*- coding: utf-8 -*-
"""Mémoire persistante par visiteur : faits et historique.

Capzo se souvient des préférences (faits) et des discussions précédentes pour
personnaliser ses réponses. Tout reste isolé par visiteur (cookie capzo_vid).
"""
import hashlib
import json
import os
import re
import time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAX_FAITS = 120
MAX_HISTORIQUE = 150
MAX_CHARS = 24000


def _cle_visiteur():
    ident = "local"
    try:
        from flask import g, has_request_context
        if has_request_context():
            ident = getattr(g, "visiteur_id", None) or ident
    except Exception:
        pass
    return hashlib.sha256(str(ident).encode("utf-8")).hexdigest()[:24]


def _chemin():
    return os.path.join(BASE, "memoire_" + _cle_visiteur() + ".json")


def _lire():
    try:
        with open(_chemin(), "r", encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict):
            d.setdefault("faits", [])
            d.setdefault("historique", [])
            return d
    except Exception:
        pass
    return {"faits": [], "historique": []}


def _ecrire(d):
    try:
        texte = json.dumps(d, ensure_ascii=False)
        while len(texte) > MAX_CHARS and d.get("historique"):
            d["historique"].pop(0)
            texte = json.dumps(d, ensure_ascii=False)
        with open(_chemin(), "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def faits():
    return list(_lire().get("faits", []))


def historique():
    return list(_lire().get("historique", []))


def ajouter_fait(texte):
    texte = (texte or "").strip()
    if not texte or len(texte) < 3:
        return False
    d = _lire()
    if texte not in d["faits"]:
        d["faits"].append(texte)
        d["faits"] = d["faits"][-MAX_FAITS:]
        _ecrire(d)
    return True


def supprimer_fait(index):
    try:
        i = int(index)
    except (TypeError, ValueError):
        return False
    d = _lire()
    if 0 <= i < len(d.get("faits", [])):
        d["faits"].pop(i)
        _ecrire(d)
        return True
    return False


def effacer_tout():
    try:
        os.remove(_chemin())
    except FileNotFoundError:
        pass
    except Exception:
        pass
    return True


def detecter_et_stocker(message):
    t = (message or "").strip()
    if not t or len(t) > 600:
        return []
    trouves = []
    motifs = [
        (r"(?:souviens[- ]toi que|rappelle[- ]toi que|retiens que|note que|"
         r"n'oublie pas que|m[ée]morise que)\s*(.+)", ""),
        (r"(?:je m'appelle|mon nom est|appelle[- ]moi)\s+(.+)", "Prénom/nom"),
        (r"(?:j'habite (?:à|a|au|aux)|je vis (?:à|a|au|aux)|je suis de|je viens de)\s+(.+)", "Lieu"),
        (r"(?:mon anniversaire (?:est|c'est)|je suis n[ée] le)\s+(.+)", "Anniversaire"),
        (r"(?:mon m[ée]tier|mon travail|ma profession)\s*(?:est|c'est)\s*(.+)", "Métier"),
        (r"(?:je travaille|j'[ée]tudie|je fais des [ée]tudes)\s+(.+)", "Activité"),
        (r"(?:je pr[ée]f[èe]re|ma pr[ée]f[ée]rence (?:est|c'est)|je privil[ée]gie)\s*(.+)", "Préférence"),
        (r"(?:j'aime|j'adore|j'appr[ée]cie)\s*(.+)", "Aime"),
        (r"(?:je n'aime pas|j'ai horreur de|je d[ée]teste|je hais)\s*(.+)", "N'aime pas"),
        (r"(?:[àa] l'avenir|d[ée]sormais|dor[ée]navant|"
         r"[àa] partir de maintenant)\s*,?\s*(.+)", "Consigne"),
        (r"(?:r[ée]ponds|parle|[ée]cris)[- ]moi\s+(toujours\s+.+)", "Ton/style"),
        (r"(?:utilise|emploie)\s+(toujours\s+.+)", "Consigne"),
        (r"(?:je suis allergique (?:à|a|au|aux)|je suis intol[ée]rant (?:à|a|au|aux))\s*(.+)", "Santé"),
        (r"(?:mon objectif|mes objectifs|mon but|mon projet)\s*(?:est|c'est|:)\s*(.+)", "Objectif"),
    ]
    for motif, etiquette in motifs:
        for m in re.finditer(motif, t, re.IGNORECASE):
            clause = m.group(1).strip().rstrip(".!?")
            clause = re.sub(r"\s+", " ", clause)
            if 3 <= len(clause) <= 240:
                fait = (etiquette + " : " + clause) if etiquette else clause
                ajouter_fait(fait)
                if clause not in trouves:
                    trouves.append(clause)
    return trouves


def ajouter_message(role, contenu):
    contenu = contenu if isinstance(contenu, str) else str(contenu or "")
    contenu = contenu.strip()
    if not contenu:
        return False
    if role == "user":
        detecter_et_stocker(contenu)
    extrait = contenu[:200].replace("\n", " ")
    return ajouter_historique(("U: " if role == "user" else "A: ") + extrait)


def ajouter_historique(texte):
    texte = (texte or "").strip()
    if not texte or len(texte) < 6:
        return False
    d = _lire()
    if texte not in d["historique"]:
        d["historique"].append(texte)
        d["historique"] = d["historique"][-MAX_HISTORIQUE:]
        _ecrire(d)
    return True


def contexte():
    d = _lire()
    morceaux = []
    if d.get("faits"):
        morceaux.append("Faits/préférences de l'utilisateur (à respecter) : " +
                        " ; ".join(d["faits"][-45:]))
    if d.get("historique"):
        morceaux.append("Souvenirs récents : " + " | ".join(d["historique"][-15:]))
    if not morceaux:
        return ""
    return ("\n\n=== MÉMOIRE (personnalisation) ===\n" + "\n".join(morceaux) +
            "\nUtilise cette mémoire pour personnaliser tes réponses, sans la répéter mot pour mot.")


def etat():
    d = _lire()
    return {"faits": d.get("faits", []), "historique": d.get("historique", []),
            "nombre": len(d.get("faits", [])) + len(d.get("historique", []))}