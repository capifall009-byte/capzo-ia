# -*- coding: utf-8 -*-
"""Connexion Google (OAuth 2.0) pour Capzo IA.

Un clic suffit : Capzo demande a Google l'autorisation de lire les mails et
l'agenda, et Google lui donne un jeton. Plus besoin de mot de passe
d'application ni d'adresse iCal.

Configuration dans CapzoIA/.env :

    CAPZO_GOOGLE_CLIENT_ID=123...apps.googleusercontent.com
    CAPZO_GOOGLE_CLIENT_SECRET=GOCSPX-...
    CAPZO_SITE_URL=https://ton-site.onrender.com   (optionnel, pour le callback)

Le redirect URI a declarer dans Google Cloud Console est :
    <ton site>/api/google/callback
"""
import base64
import hashlib
import json
import os
import time
import urllib.parse
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKENS_FICHIER = os.path.join(BASE, "google_tokens.json")
STATE_FICHIER = os.path.join(BASE, "google_state.txt")


def _cle_visiteur():
    """Court hash de l'identifiant anonyme du navigateur courant.

    app.py place cet identifiant dans flask.g a chaque requete. Chaque
    visiteur dispose ainsi de ses propres jetons Google : sur le site public,
    personne ne peut lire le mail ou l'agenda d'un autre visiteur.
    """
    ident = "local"
    try:
        from flask import g, has_request_context
        if has_request_context():
            ident = getattr(g, "visiteur_id", None) or ident
    except Exception:
        pass
    return hashlib.sha256(str(ident).encode("utf-8")).hexdigest()[:24]


def _chemin_tokens():
    return os.path.join(BASE, "google_tokens_" + _cle_visiteur() + ".json")


def _chemin_state():
    return os.path.join(BASE, "google_state_" + _cle_visiteur() + ".txt")

CLIENT_ID = (os.environ.get("CAPZO_GOOGLE_CLIENT_ID") or "").strip()
CLIENT_SECRET = (os.environ.get("CAPZO_GOOGLE_CLIENT_SECRET") or "").strip()
SITE_URL = (os.environ.get("CAPZO_SITE_URL") or "").strip().rstrip("/")

SCOPES = [
    "openid", "email", "profile",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.events",
]
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


def _charger_tokens():
    try:
        with open(_chemin_tokens(), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _sauver_tokens(data):
    try:
        with open(_chemin_tokens(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _supprimer_tokens():
    try:
        os.remove(_chemin_tokens())
    except FileNotFoundError:
        pass


def etat():
    t = _charger_tokens()
    pret = bool(t.get("access_token") or t.get("refresh_token"))
    return {
        "pret": pret,
        "email": t.get("email"),
        "scopes": t.get("scopes", []),
        "configure": bool(CLIENT_ID and CLIENT_SECRET),
    }


def redirect_uri_par_defaut(url_racine):
    racine = (SITE_URL or (url_racine or "").rstrip("/"))
    return racine + "/api/google/callback"


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
        if len(lignes) < 2:
            return False
        if state != lignes[0]:
            return False
        if int(time.time()) - int(lignes[1]) > 600:
            return False
        return True
    except Exception:
        return False


def url_connexion(url_racine):
    if not (CLIENT_ID and CLIENT_SECRET):
        return None, ("Google n'est pas configure. Ajoute CAPZO_GOOGLE_CLIENT_ID et "
                      "CAPZO_GOOGLE_CLIENT_SECRET dans CapzoIA/.env (voir README).")
    state = generer_state()
    redirect = redirect_uri_par_defaut(url_racine)
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": redirect,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return AUTH_URL + "?" + urllib.parse.urlencode(params), None


def _post_token(params):
    data = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(TOKEN_URL, data=data, method="POST",
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def echanger_code(code, url_racine):
    if not (CLIENT_ID and CLIENT_SECRET):
        return False, "Google non configure."
    redirect = redirect_uri_par_defaut(url_racine)
    try:
        jetons = _post_token({
            "code": code, "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
            "redirect_uri": redirect, "grant_type": "authorization_code"})
    except Exception as e:
        return False, "Echange du code impossible : " + str(e)[:160]
    if "access_token" not in jetons:
        return False, jetons.get("error_description") or jetons.get("error") or "Pas de jeton."
    tokens = _charger_tokens()
    tokens["access_token"] = jetons["access_token"]
    if jetons.get("refresh_token"):
        tokens["refresh_token"] = jetons["refresh_token"]
    tokens["expiry"] = int(time.time()) + int(jetons.get("expires_in", 3600)) - 60
    tokens["scopes"] = jetons.get("scope", "").split()
    # email du compte
    try:
        req = urllib.request.Request(USERINFO_URL,
                                    headers={"Authorization": "Bearer " + tokens["access_token"]})
        with urllib.request.urlopen(req, timeout=20) as r:
            info = json.loads(r.read().decode("utf-8", "replace"))
        tokens["email"] = info.get("email")
        tokens["nom"] = info.get("name")
    except Exception:
        pass
    _sauver_tokens(tokens)
    return True, tokens.get("email") or "compte Google"


def rafraichir_si_expire():
    tokens = _charger_tokens()
    if not tokens.get("access_token"):
        return False
    if int(time.time()) < int(tokens.get("expiry", 0)):
        return True
    if not tokens.get("refresh_token"):
        return False
    try:
        jetons = _post_token({
            "refresh_token": tokens["refresh_token"],
            "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
            "grant_type": "refresh_token"})
    except Exception:
        return False
    if "access_token" not in jetons:
        return False
    tokens["access_token"] = jetons["access_token"]
    tokens["expiry"] = int(time.time()) + int(jetons.get("expires_in", 3600)) - 60
    _sauver_tokens(tokens)
    return True


def deconnecter():
    _supprimer_tokens()
    return True


def _jeton():
    if not rafraichir_si_expire():
        return None
    return _charger_tokens().get("access_token")


def _get(url, params=None, timeout=30):
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + _jeton(),
                                               "User-Agent": "CapzoIA"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _post(url, data, timeout=30):
    req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), method="POST",
                                 headers={"Authorization": "Bearer " + _jeton(),
                                          "Content-Type": "application/json",
                                          "User-Agent": "CapzoIA"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


# ---------------------------------------------------------------- Gmail
def gmail_lire(nombre=5, non_lus=False):
    if not _jeton():
        return [], "Google non connecte."
    nombre = max(1, min(int(nombre or 5), 15))
    params = {"maxResults": nombre}
    if non_lus:
        params["q"] = "is:unread"
    try:
        liste = _get("https://gmail.googleapis.com/gmail/v1/users/me/messages", params)
    except Exception as e:
        return [], "Lecture Gmail impossible : " + str(e)[:160]
    ids = [m["id"] for m in (liste.get("messages") or [])]
    mails = []
    for ident in ids:
        try:
            m = _get("https://gmail.googleapis.com/gmail/v1/users/me/messages/" + ident,
                     {"format": "metadata",
                      "metadataHeaders": "Subject,From,Date"})
        except Exception:
            continue
        entetes = {h["name"]: h["value"] for h in (m.get("payload", {}).get("headers") or [])}
        mails.append({
            "de": entetes.get("From", ""),
            "sujet": entetes.get("Subject", "(sans sujet)"),
            "date": entetes.get("Date", ""),
            "extrait": (m.get("snippet") or "")[:400],
            "lu": "UNREAD" not in (m.get("labelIds") or []),
        })
    return mails, None


def gmail_envoyer(destinataire, sujet, corps):
    if not _jeton():
        return False, "Google non connecte."
    import email as _email
    from email.message import EmailMessage
    msg = EmailMessage()
    msg["To"] = destinataire
    msg["Subject"] = (sujet or "(sans objet)")[:180]
    msg.set_content(corps or "")
    brut = msg.as_bytes()
    brut_b64 = base64.urlsafe_b64encode(brut).decode("ascii").rstrip("=")
    try:
        _post("https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
              {"raw": brut_b64})
        return True, "Mail envoye a " + destinataire + " (via Google)."
    except Exception as e:
        return False, "Envoi impossible : " + str(e)[:160]


# ---------------------------------------------------------------- Calendar
def calendar_lire(jours=7, limite=15):
    if not _jeton():
        return [], "Google non connecte."
    maintenant = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    fin = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + max(1, int(jours or 7)) * 86400))
    try:
        data = _get("https://www.googleapis.com/calendar/v3/calendars/primary/events", {
            "timeMin": maintenant, "timeMax": fin, "singleEvents": "true",
            "orderBy": "startTime", "maxResults": limite})
    except Exception as e:
        return [], "Lecture de l'agenda impossible : " + str(e)[:160]
    evts = []
    for e in (data.get("items") or []):
        debut = (e.get("start") or {}).get("dateTime") or (e.get("start") or {}).get("date") or ""
        fin_e = (e.get("end") or {}).get("dateTime") or (e.get("end") or {}).get("date") or ""
        try:
            debut_txt = time.strftime("%Y-%m-%d %H:%M", time.strptime(debut[:16].replace("T", " "), "%Y-%m-%d %H:%M"))
        except Exception:
            debut_txt = debut
        try:
            fin_txt = time.strftime("%H:%M", time.strptime(fin_e[:16].replace("T", " "), "%Y-%m-%d %H:%M"))
        except Exception:
            fin_txt = ""
        evts.append({"titre": e.get("summary") or "(sans titre)",
                     "debut": debut_txt, "fin": fin_txt,
                     "lieu": e.get("location") or ""})
    return evts, None


def calendar_creer(titre, debut, duree_min=60, lieu="", description=""):
    if not _jeton():
        return None, "Google non connecte."
    try:
        t = time.strptime(str(debut).replace("T", " ")[:16], "%Y-%m-%d %H:%M")
    except Exception:
        return None, "Date invalide. Utilise le format AAAA-MM-JJ HH:MM."
    depart = int(time.mktime(t))
    fin = depart + max(15, int(duree_min or 60)) * 60
    corps = {
        "summary": (titre or "Rendez-vous")[:180],
        "start": {"dateTime": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(depart)),
                  "timeZone": time.tzname[0] if time.tzname else "UTC"},
        "end": {"dateTime": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(fin)),
                "timeZone": time.tzname[0] if time.tzname else "UTC"},
    }
    if lieu:
        corps["location"] = lieu[:180]
    if description:
        corps["description"] = description[:500]
    try:
        data = _post("https://www.googleapis.com/calendar/v3/calendars/primary/events", corps)
        return {"ok": True, "mode": "google", "titre": titre, "debut": debut,
                "duree": duree_min, "lieu": lieu,
                "lien": data.get("htmlLink")}, None
    except Exception as e:
        return None, "Creation impossible : " + str(e)[:160]
