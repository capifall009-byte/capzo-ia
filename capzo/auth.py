# -*- coding: utf-8 -*-
"""Connexion obligatoire mais SANS mot de passe, isolée par visiteur.

Un visiteur est reconnu par le cookie anonyme ``capzo_vid`` posé par app.py.
Aucun email + mot de passe n'est jamais demandé ni stocké : seulement le
résultat d'une connexion officielle Google ou GitHub (OAuth 2.0).

Les fichiers de session restent locaux au serveur (Render : système éphémère,
l'utilisateur se reconnecte simplement après un redéploiement).
"""
import hashlib
import json
import os
import time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CIVILITES = ("neutre", "monsieur", "madame")


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
    return os.path.join(BASE, "utilisateur_" + _cle_visiteur() + ".json")


def _lire():
    try:
        with open(_chemin(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _ecrire(data):
    try:
        chemin = _chemin()
        temporaire = chemin + ".tmp"
        with open(temporaire, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(temporaire, chemin)
    except Exception:
        pass


def connecter(fournisseur, email=None, nom=None, photo=None):
    """Enregistre le résultat d'un OAuth réussi pour ce visiteur."""
    data = _lire()
    data.update({
        "fournisseur": str(fournisseur or "").lower(),
        "email": email or data.get("email"),
        "nom": nom or data.get("nom"),
        "photo": photo or data.get("photo"),
        "civilite": data.get("civilite") or "neutre",
        "connecte_le": int(time.time()),
    })
    _ecrire(data)
    return profil()


def profil():
    """Données publiques de la session (jamais de jeton ici)."""
    d = _lire()
    return {
        "connecte": bool(d.get("fournisseur") and (d.get("email") or d.get("nom"))),
        "fournisseur": d.get("fournisseur"),
        "email": d.get("email"),
        "nom": d.get("nom"),
        "photo": d.get("photo"),
        "civilite": d.get("civilite") or "neutre",
    }


def est_connecte():
    p = profil()
    if p["connecte"]:
        return True
    # Migration : un visiteur déjà connecté avant l'ajout du portail garde l'accès.
    try:
        from . import apple_auth, github_auth, google_auth
        if (google_auth.etat() or {}).get("pret"):
            return True
        if (github_auth.etat() or {}).get("pret"):
            return True
        if (apple_auth.etat() or {}).get("pret"):
            return True
    except Exception:
        pass
    return False


def definir_civilite(valeur):
    v = str(valeur or "").strip().lower()
    if v not in CIVILITES:
        return False
    d = _lire()
    d["civilite"] = v
    _ecrire(d)
    return True


def deconnecter():
    """Efface la session locale. Les jetons liés restent gérés par leur module."""
    try:
        os.remove(_chemin())
    except FileNotFoundError:
        pass
    except Exception:
        pass
    try:
        from . import apple_auth, github_auth, google_auth
        google_auth.deconnecter()
        github_auth.deconnecter()
        apple_auth.deconnecter()
    except Exception:
        pass
    return True


def fournisseurs():
    """Fournisseurs de connexion activés côté serveur (sans révéler de secret)."""
    return {
        "google": bool(os.environ.get("CAPZO_GOOGLE_CLIENT_ID")
                       and os.environ.get("CAPZO_GOOGLE_CLIENT_SECRET")),
        "github": bool(os.environ.get("CAPZO_GITHUB_CLIENT_ID")
                       and os.environ.get("CAPZO_GITHUB_CLIENT_SECRET")),
        "apple": bool(os.environ.get("CAPZO_APPLE_CLIENT_ID") and (
            os.environ.get("CAPZO_APPLE_CLIENT_SECRET") or
            (os.environ.get("CAPZO_APPLE_TEAM_ID") and
             os.environ.get("CAPZO_APPLE_KEY_ID") and
             (os.environ.get("CAPZO_APPLE_PRIVATE_KEY") or
              os.environ.get("CAPZO_APPLE_KEY_FILE"))))),
    }


def etat():
    p = profil()
    p["connecte"] = est_connecte()
    p["fournisseurs"] = fournisseurs()
    p["civilites"] = list(CIVILITES)
    return p
