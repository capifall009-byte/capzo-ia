# -*- coding: utf-8 -*-
"""Connexion Apple (Sign in with Apple) pour Capzo IA — sans mot de passe.

Configuration dans Render :
    CAPZO_APPLE_CLIENT_ID      (Services ID, ex : com.capzo.ia.web)
    CAPZO_APPLE_CLIENT_SECRET  (JWT généré par Apple, valable 6 mois maximum)
  OU, pour générer le JWT automatiquement :
    CAPZO_APPLE_TEAM_ID
    CAPZO_APPLE_KEY_ID
    CAPZO_APPLE_PRIVATE_KEY    (contenu du .p8, les \n sont acceptés)
    ou CAPZO_APPLE_KEY_FILE    (chemin local vers le .p8)

Redirect URI à déclarer dans Apple Developer :
    https://capzo-ia.onrender.com/api/apple/callback
Apple renvoie le résultat en POST (response_mode=form_post).
"""
import base64
import hashlib
import json
import os
import time
import urllib.parse
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENT_ID = (os.environ.get("CAPZO_APPLE_CLIENT_ID") or "").strip()
SECRET_FIXE = (os.environ.get("CAPZO_APPLE_CLIENT_SECRET") or "").strip()
TEAM_ID = (os.environ.get("CAPZO_APPLE_TEAM_ID") or "").strip()
KEY_ID = (os.environ.get("CAPZO_APPLE_KEY_ID") or "").strip()
PRIVATE_KEY = (os.environ.get("CAPZO_APPLE_PRIVATE_KEY") or "").strip()
KEY_FILE = (os.environ.get("CAPZO_APPLE_KEY_FILE") or "").strip()
SITE_URL = (os.environ.get("CAPZO_SITE_URL") or "").strip().rstrip("/")
AUTH_URL = "https://appleid.apple.com/auth/authorize"
TOKEN_URL = "https://appleid.apple.com/auth/token"


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
    return os.path.join(BASE, "apple_session_" + _cle_visiteur() + ".json")


def _chemin_state():
    return os.path.join(BASE, "apple_state_" + _cle_visiteur() + ".txt")


def configure():
    return bool(CLIENT_ID and (SECRET_FIXE or (TEAM_ID and KEY_ID and (PRIVATE_KEY or KEY_FILE))))


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
    return {"configure": configure(), "pret": bool(d.get("email") or d.get("nom")),
            "email": d.get("email"), "nom": d.get("nom")}


def client_secret():
    """Secret client Apple : fourni ou généré en ES256 (PyJWT + cryptography)."""
    if SECRET_FIXE:
        return SECRET_FIXE, None
    if not (TEAM_ID and KEY_ID and (PRIVATE_KEY or KEY_FILE)):
        return None, "Apple n'est pas configuré côté serveur."
    cle = PRIVATE_KEY.replace("\\n", "\n")
    if not cle and KEY_FILE:
        try:
            with open(KEY_FILE, "r", encoding="utf-8") as f:
                cle = f.read()
        except Exception as e:
            return None, "Clé Apple illisible : " + str(e)[:120]
    try:
        import jwt  # PyJWT[crypto]
    except Exception:
        return None, ("PyJWT[crypto] manquant sur le serveur (ajoute PyJWT[crypto] "
                      "aux dépendances).")
    maintenant = int(time.time())
    try:
        secret = jwt.encode(
            {"iss": TEAM_ID, "iat": maintenant, "exp": maintenant + 3600 * 5,
             "aud": "https://appleid.apple.com", "sub": CLIENT_ID},
            cle, algorithm="ES256", headers={"kid": KEY_ID})
    except Exception as e:
        return None, "Signature Apple impossible : " + str(e)[:120]
    return secret, None


def redirect_uri_par_defaut(url_racine):
    racine = SITE_URL or (url_racine or "").rstrip("/")
    return racine + "/api/apple/callback"


def _generer_state():
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
        return None, ("Apple n'est pas configuré. Ajoute CAPZO_APPLE_CLIENT_ID et "
                      "CAPZO_APPLE_CLIENT_SECRET dans Render (voir NOUVEAUTES.md).")
    secret, erreur = client_secret()
    if erreur:
        return None, erreur
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": redirect_uri_par_defaut(url_racine),
        "response_type": "code id_token",
        "scope": "name email",
        "response_mode": "form_post",
        "state": _generer_state(),
    }
    return AUTH_URL + "?" + urllib.parse.urlencode(params), None


def _payload_jwt(token):
    try:
        partie = token.split(".")[1]
        partie += "=" * (-len(partie) % 4)
        return json.loads(base64.urlsafe_b64decode(partie).decode("utf-8", "replace"))
    except Exception:
        return {}


def callback(donnees, arguments, url_racine):
    """donnees = request.form, arguments = request.args. Retourne (ok, infos, erreur)."""
    code = donnees.get("code") or arguments.get("code")
    state = donnees.get("state") or arguments.get("state")
    if not code or not verifier_state(state):
        return False, None, "Etat Apple invalide ou expiré."
    secret, erreur = client_secret()
    if erreur:
        return False, None, erreur
    corps = urllib.parse.urlencode({
        "client_id": CLIENT_ID, "client_secret": secret, "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri_par_defaut(url_racine),
    }).encode("utf-8")
    req = urllib.request.Request(
        TOKEN_URL, data=corps, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "CapzoIA"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            jetons = json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:
        return False, None, "Echange Apple impossible : " + str(e)[:140]
    if "access_token" not in jetons and "id_token" not in jetons:
        return False, None, str(jetons.get("error") or "Pas de jeton Apple.")[:140]
    promesse = _payload_jwt(jetons.get("id_token") or "")
    email = promesse.get("email")
    nom = ""
    brut_user = donnees.get("user")
    if brut_user:
        try:
            u = json.loads(brut_user)
            nom = " ".join(x for x in (u.get("name", {}).get("firstName"),
                                       u.get("name", {}).get("lastName")) if x)
        except Exception:
            pass
    nom = nom or email or "Compte Apple"
    # On ne garde que l'identité : aucun jeton Apple n'est écrit sur le serveur.
    _ecrire({"email": email, "nom": nom, "connecte_le": int(time.time())})
    return True, {"email": email, "nom": nom}, None


def deconnecter():
    try:
        os.remove(_chemin_tokens())
    except FileNotFoundError:
        pass
    except Exception:
        pass
    return True
