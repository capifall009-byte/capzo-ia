# -*- coding: utf-8 -*-
"""Mémoire persistante de Capzo, isolée par visiteur.

Conserve des faits (préférences, informations importantes) et l'historique
récent des échanges, afin que Capzo se souvienne d'une session à l'autre
et d'un appareil à l'autre.
"""
import hashlib
import json
import os
import time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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
            data = json.load(f)
        if not isinstance(data, dict):
            data = {}
    except Exception:
        data = {}
    data.setdefault("faits", [])
    data.setdefault("historique", [])
    return data


def _ecrire(data):
    try:
        with open(_chemin(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def faits():
    return list(_lire().get("faits") or [])


def ajouter_fait(texte):
    texte = (texte or "").strip()
    if not texte:
        return False
    data = _lire()
    if texte not in data["faits"]:
        data["faits"].append(texte[:300])
        data["faits"] = data["faits"][-60:]
        _ecrire(data)
    return True


def supprimer_fait(index):
    data = _lire()
    try:
        index = int(index)
    except (TypeError, ValueError):
        return False
    if 0 <= index < len(data["faits"]):
        del data["faits"][index]
        _ecrire(data)
        return True
    return False


def effacer_faits():
    data = _lire()
    data["faits"] = []
    _ecrire(data)


def historique():
    return list(_lire().get("historique") or [])


def ajouter_message(role, contenu):
    if role not in ("user", "assistant") or not contenu:
        return False
    data = _lire()
    data["historique"].append({"role": role, "content": str(contenu)[:1500],
                               "t": int(time.time())})
    data["historique"] = data["historique"][-80:]
    _ecrire(data)
    return True


def effacer_historique():
    data = _lire()
    data["historique"] = []
    _ecrire(data)


def effacer_tout():
    try:
        os.remove(_chemin())
    except FileNotFoundError:
        pass


def contexte():
    """Texte à injecter dans le prompt système."""
    data = _lire()
    morceaux = []
    if data.get("faits"):
        morceaux.append("Faits mémorisés sur l'utilisateur :\n- " +
                        "\n- ".join(data["faits"]))
    hist = (data.get("historique") or [])[-12:]
    if hist:
        lignes = []
        for m in hist:
            prefixe = "Utilisateur" if m.get("role") == "user" else "Capzo"
            lignes.append(prefixe + " : " + str(m.get("content", ""))[:400])
        morceaux.append("Échanges récents à ne pas oublier :\n" + "\n".join(lignes))
    return "\n\n".join(morceaux)
