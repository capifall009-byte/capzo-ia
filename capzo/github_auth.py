# -*- coding: utf-8 -*-
"""Connexion GitHub (OAuth 2.0) pour Capzo IA — sans mot de passe.

A déclarer dans https://github.com/settings/developers → OAuth Apps :
    Authorization callback URL : https://capzo-ia.onrender.com/api/github/callback

Variables Render :
    CAPZO_GITHUB_CLIENT_ID
    CAPZO_GITHUB_CLIENT_SECRET
"""
import hashlib
import json
import os
import time
import urllib.parse
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENT_ID = (os.environ.get("CAPZO_GITHUB_CLIENT_ID") or "").strip()
CLIENT_SECRET = (os.environ.get("CAPZO_GITHUB_CLIENT_SECRET") or "").strip()
SITE_URL = (os.environ.get("CAPZO_SITE_URL") or "").strip().rstrip("/")
AUTH_URL = "https://github.com/login/oauth/authorize"
TOKEN_URL = "https://github.com/login/oauth/access_token"
API_URL = "https://api.github.com"
SCOPES = "read:user user:email"


def _cle_visiteur():
    ident = "local"
    try:
        from flask import g, has_request_context
        if has_request_context():
            ident = getattr(g, "visiteur_id", None) or ident
    except Exception:
        pass
    return hashlib.sha256(str(ident).encode("utf-8")).hexdigest()[:24]


def _chemin_tokens():
    return os.path.join(BASE, "github_tokens_" + _cle_visiteur() + ".json")


def _chemin_state():
    return os.path.join(BASE, "github_state_" + _cle_visiteur() + ".txt")


def configure():
    return bool(CLIENT_ID and CLIENT_SECRET)


def _lire():
    try:
        with open(_chemin_tokens(), "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _ecrire(d):
    try:
        with open(_chemin_tokens(), "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def etat():
    d = _lire()
    return {
        "configure": configure(),
        "pret": bool(d.get("access_token")),
        "login": d.get("login"),
        "email": d.get("email"),
        "nom": d.get("nom"),
    }


def redirect_uri_par_defaut(url_racine):
    racine = SITE_URL or (url_racine or "").rstrip("/")
    return racine + "/api/github/callback"


def generer_state():
    import secrets
    state = secrets.token_urlsafe(24)
    try:
        with open(_chemin_state(), "w", encoding="utf-8") as f:
            f.write(state + "\n" + str(int(time.time())))
    except Exception:
        pass
    return state


def verifier_state(state):
    try:
        with open(_chemin_state(), "r", encoding="utf-8") as f:
            lignes = f.read().splitlines()
        if len(lignes) < 2 or state != lignes[0]:
            return False
        if int(time.time()) - int(lignes[1]) > 600:
            return False
        return True
    except Exception:
        return False


def url_connexion(url_racine):
    if not configure():
        return None, ("GitHub n'est pas configuré. Ajoute CAPZO_GITHUB_CLIENT_ID et "
                      "CAPZO_GITHUB_CLIENT_SECRET dans Render.")
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": redirect_uri_par_defaut(url_racine),
        "scope": SCOPES,
        "state": generer_state(),
        "allow_signup": "true",
    }
    return AUTH_URL + "?" + urllib.parse.urlencode(params), None


def _api(chemin, jeton):
    req = urllib.request.Request(
        API_URL + chemin,
        headers={"Authorization": "Bearer " + jeton,
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "CapzoIA"},
    )
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def echanger_code(code, url_racine):
    if not configure():
        return False, None, "GitHub non configuré."
    data = urllib.parse.urlencode({
        "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
        "code": code, "redirect_uri": redirect_uri_par_defaut(url_racine),
    }).encode("utf-8")
    req = urllib.request.Request(
        TOKEN_URL, data=data, method="POST",
        headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded",
                 "User-Agent": "CapzoIA"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            jetons = json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:
        return False, None, "Echange du code impossible : " + str(e)[:160]
    jeton = jetons.get("access_token")
    if not jeton:
        return False, None, jetons.get("error_description") or jetons.get("error") or "Pas de jeton."
    info = {"access_token": jeton, "portee": jetons.get("scope", "")}
    try:
        u = _api("/user", jeton)
        info["login"] = u.get("login")
        info["nom"] = u.get("name") or u.get("login")
        info["photo"] = u.get("avatar_url")
        info["email"] = u.get("email")
    except Exception:
        pass
    if not info.get("email"):
        try:
            mails = _api("/user/emails", jeton)
            favori = next((m for m in mails if m.get("primary")), None)
            info["email"] = (favori or {}).get("email") or (mails[0].get("email") if mails else None)
        except Exception:
            pass
    _ecrire(info)
    return True, info, None


def deconnecter():
    try:
        os.remove(_chemin_tokens())
    except FileNotFoundError:
        pass
    except Exception:
        pass
    return True
