# -*- coding: utf-8 -*-
"""Hub de connecteurs sociaux : Instagram, TikTok et passerelle Windsor IA.

Principe volontairement simple et sûr :
- OAuth officiel uniquement (Meta / TikTok), jamais d'email + mot de passe ;
- un jeton par visiteur, stocké dans un fichier local isolé ;
- Windsor IA est une passerelle générique : on lui donne une URL et une clé
  d'API via les variables d'environnement, sans jamais écrire la clé dans le code.

Variables Render possibles :
    CAPZO_IG_APP_ID, CAPZO_IG_APP_SECRET          (Instagram via Meta)
    CAPZO_IG_USER, CAPZO_IG_TOKEN                  (Instagram mode existant)
    CAPZO_TIKTOK_CLIENT_KEY, CAPZO_TIKTOK_CLIENT_SECRET
    CAPZO_TIKTOK_SCOPE                             (défaut : user.info.basic)
    CAPZO_WINDSOR_URL, CAPZO_WINDSOR_KEY, CAPZO_WINDSOR_NOM
"""
import hashlib
import json
import os
import time
import urllib.parse
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
META_VERSION = (os.environ.get("CAPZO_META_VERSION") or "v21.0").strip()
TIKTOK_SCOPE = (os.environ.get("CAPZO_TIKTOK_SCOPE") or "user.info.basic").strip()

IG_ID = (os.environ.get("CAPZO_IG_APP_ID") or "").strip()
IG_SECRET = (os.environ.get("CAPZO_IG_APP_SECRET") or "").strip()
TT_KEY = (os.environ.get("CAPZO_TIKTOK_CLIENT_KEY") or "").strip()
TT_SECRET = (os.environ.get("CAPZO_TIKTOK_CLIENT_SECRET") or "").strip()
WINDSOR_URL = (os.environ.get("CAPZO_WINDSOR_URL") or "").strip().rstrip("/")
WINDSOR_KEY = (os.environ.get("CAPZO_WINDSOR_KEY") or "").strip()
WINDSOR_NOM = (os.environ.get("CAPZO_WINDSOR_NOM") or "Windsor IA").strip()

FOURNISSEURS = ("instagram", "tiktok", "windsor")


def _cle_visiteur():
    ident = "local"
    try:
        from flask import g, has_request_context
        if has_request_context():
            ident = getattr(g, "visiteur_id", None) or ident
    except Exception:
        pass
    return hashlib.sha256(str(ident).encode("utf-8")).hexdigest()[:24]


def _chemin(service, suffixe):
    return os.path.join(BASE, "social_" + service + "_" + suffixe + "_" + _cle_visiteur() + ".json")


def _lire(service):
    try:
        with open(_chemin(service, "jeton"), "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _ecrire(service, data):
    try:
        with open(_chemin(service, "jeton"), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _etat_oauth(service):
    d = _lire(service)
    return {
        "pret": bool(d.get("access_token")),
        "compte": d.get("compte") or d.get("nom") or d.get("open_id"),
        "connecte_le": d.get("connecte_le"),
    }


def etat():
    """Etat affiché dans le panneau. Aucune clé ni jeton n'est renvoyé."""
    try:
        from . import instagram
        ig_local = instagram.etat()
    except Exception:
        ig_local = {"pret": False, "compte": None}
    ig = _etat_oauth("instagram")
    tt = _etat_oauth("tiktok")
    return {
        "instagram": {
            "pret": ig["pret"] or bool(ig_local.get("pret")),
            "compte": ig["compte"] or ig_local.get("compte"),
            "configure": bool(IG_ID and IG_SECRET) or bool(ig_local.get("pret")),
            "methode": "oauth" if (IG_ID and IG_SECRET) else ("compte" if ig_local.get("pret") else "aucune"),
        },
        "tiktok": {
            "pret": tt["pret"],
            "compte": tt["compte"],
            "configure": bool(TT_KEY and TT_SECRET),
            "methode": "oauth" if (TT_KEY and TT_SECRET) else "aucune",
        },
        "windsor": {
            "pret": bool(WINDSOR_URL),
            "configure": bool(WINDSOR_URL and WINDSOR_KEY),
            "nom": WINDSOR_NOM,
            "methode": "cle-api" if (WINDSOR_URL and WINDSOR_KEY) else "aucune",
        },
    }


def _url_base(url_racine):
    site = (os.environ.get("CAPZO_SITE_URL") or "").strip().rstrip("/")
    return site or (url_racine or "").rstrip("/")


def _generer_state(service):
    import secrets
    state = secrets.token_urlsafe(24)
    try:
        with open(_chemin(service, "state"), "w", encoding="utf-8") as f:
            f.write(state + "\n" + str(int(time.time())))
    except Exception:
        pass
    return state


def verifier_state(service, state):
    try:
        with open(_chemin(service, "state"), "r", encoding="utf-8") as f:
            lignes = f.read().splitlines()
        if len(lignes) < 2 or state != lignes[0]:
            return False
        if int(time.time()) - int(lignes[1]) > 600:
            return False
        return True
    except Exception:
        return False


def url_connexion(service, url_racine):
    """Retourne (url, erreur). Windsor n'a pas d'OAuth : il utilise une clé API."""
    service = (service or "").lower()
    redirect = _url_base(url_racine) + "/api/social/" + service + "/callback"
    if service == "instagram":
        if not (IG_ID and IG_SECRET):
            return None, ("Instagram OAuth non configuré. Ajoute CAPZO_IG_APP_ID et "
                          "CAPZO_IG_APP_SECRET dans Render, puis déclare le callback "
                          "https://capzo-ia.onrender.com/api/social/instagram/callback.")
        params = {
            "client_id": IG_ID,
            "redirect_uri": redirect,
            "response_type": "code",
            "scope": "instagram_basic,instagram_content_publish",
            "state": _generer_state(service),
        }
        return ("https://www.facebook.com/" + META_VERSION + "/dialog/oauth?" +
                urllib.parse.urlencode(params)), None
    if service == "tiktok":
        if not (TT_KEY and TT_SECRET):
            return None, ("TikTok OAuth non configuré. Ajoute CAPZO_TIKTOK_CLIENT_KEY et "
                          "CAPZO_TIKTOK_CLIENT_SECRET dans Render, puis déclare le callback "
                          "https://capzo-ia.onrender.com/api/social/tiktok/callback.")
        params = {
            "client_key": TT_KEY,
            "redirect_uri": redirect,
            "response_type": "code",
            "scope": TIKTOK_SCOPE,
            "state": _generer_state(service),
        }
        return "https://www.tiktok.com/v2/auth/authorize/?" + urllib.parse.urlencode(params), None
    if service == "windsor":
        return None, ("Windsor IA n'utilise pas d'OAuth : renseigne CAPZO_WINDSOR_URL "
                      "(URL de l'API) et CAPZO_WINDSOR_KEY (clé d'API) dans Render.")
    return None, "Connecteur inconnu."


def _post_json(url, payload):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "CapzoIA"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _get_json(url, jeton=None):
    entetes = {"User-Agent": "CapzoIA", "Accept": "application/json"}
    if jeton:
        entetes["Authorization"] = "Bearer " + jeton
    req = urllib.request.Request(url, headers=entetes)
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def callback(service, code, url_racine):
    """Echange le code OAuth et enregistre le compte. Retourne (ok, message)."""
    service = (service or "").lower()
    redirect = _url_base(url_racine) + "/api/social/" + service + "/callback"
    try:
        if service == "instagram":
            params = urllib.parse.urlencode({
                "client_id": IG_ID, "client_secret": IG_SECRET,
                "code": code, "redirect_uri": redirect,
                "grant_type": "authorization_code",
            })
            with urllib.request.urlopen("https://graph.facebook.com/" + META_VERSION +
                                        "/oauth/access_token?" + params, timeout=30) as r:
                data = json.loads(r.read().decode("utf-8", "replace"))
            jeton = data.get("access_token")
            if not jeton:
                return False, data.get("error", {}).get("message", "Pas de jeton Meta.")[:160]
            compte = ""
            try:
                moi = _get_json("https://graph.facebook.com/" + META_VERSION +
                                "/me?fields=name&access_token=" + urllib.parse.quote(jeton))
                compte = moi.get("name") or ""
            except Exception:
                pass
        elif service == "tiktok":
            data = _post_json("https://open-api.tiktok.com/oauth/access_token/", {
                "client_key": TT_KEY, "client_secret": TT_SECRET,
                "code": code, "grant_type": "authorization_code",
                "redirect_uri": redirect,
            })
            bloc = data.get("data") or {}
            jeton = bloc.get("access_token")
            if not jeton:
                return False, str(data.get("error") or "Pas de jeton TikTok.")[:160]
            compte = bloc.get("open_id") or ""
        else:
            return False, "Connecteur inconnu."
    except Exception as e:
        return False, "Connexion impossible : " + str(e)[:160]
    _ecrire(service, {"access_token": jeton, "compte": compte,
                      "connecte_le": int(time.time())})
    return True, compte or "compte connecté"


def jeton(service):
    """Retourne (jeton, identifiant) enregistres pour ce visiteur, sans rien divulguer."""
    d = _lire(service)
    return d.get("access_token") or None, d.get("compte") or None


def deconnecter(service):
    try:
        os.remove(_chemin(service, "jeton"))
    except FileNotFoundError:
        pass
    except Exception:
        pass
    return True


def connecter_token(service, token, compte=None):
    """Enregistre un jeton d'acces deja obtenu (collage manuel), sans OAuth."""
    service = (service or "").lower()
    token = (token or "").strip()
    if service not in FOURNISSEURS or not token:
        return False
    _ecrire(service, {"access_token": token, "compte": compte or "compte connecté",
                      "connecte_le": int(time.time())})
    return True


def tester_windsor():
    """Vérifie la passerelle sans jamais renvoyer la clé d'API."""
    if not (WINDSOR_URL and WINDSOR_KEY):
        return {"ok": False,
                "message": "Windsor IA non configuré : CAPZO_WINDSOR_URL et CAPZO_WINDSOR_KEY."}
    try:
        req = urllib.request.Request(
            WINDSOR_URL,
            headers={"Authorization": "Bearer " + WINDSOR_KEY,
                     "User-Agent": "CapzoIA", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            code = r.status
        return {"ok": 200 <= code < 300, "message": "Passerelle joignable (HTTP " + str(code) + ")."}
    except Exception as e:
        return {"ok": False, "message": "Passerelle injoignable : " + str(e)[:140]}
