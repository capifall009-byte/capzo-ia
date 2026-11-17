# -*- coding: utf-8 -*-
"""Connecteur Instagram (API Graph officielle de Meta).

Configuration dans CapzoIA/.env :

    CAPZO_IG_USER=17841400000000000     (identifiant du compte professionnel)
    CAPZO_IG_TOKEN=EAAG...              (jeton longue duree de l'app Meta)

Necessite un compte Instagram **professionnel** relie a une page Facebook,
et une app sur developers.facebook.com avec le produit "Instagram Graph API".
"""
import json
import os
import time
import urllib.parse
import urllib.request

VERSION = "v21.0"
BASE = "https://graph.facebook.com/" + VERSION

TOKEN = (os.environ.get("CAPZO_IG_TOKEN") or "").strip()
UTILISATEUR = (os.environ.get("CAPZO_IG_USER") or "").strip()

PRET = bool(TOKEN and UTILISATEUR)


def etat():
    return {"pret": PRET, "compte": UTILISATEUR or None}


def _erreur(data):
    e = (data or {}).get("error") or {}
    return e.get("error_user_msg") or e.get("message") or "Erreur Instagram inconnue."


def _appel(chemin, methode="GET", params=None, timeout=40):
    params = dict(params or {})
    params["access_token"] = TOKEN
    url = BASE + chemin
    if methode == "GET":
        url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": "CapzoIA"})
    else:
        req = urllib.request.Request(url, data=urllib.parse.urlencode(params).encode(),
                                     method="POST",
                                     headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8", "replace"))
        except Exception:
            raise RuntimeError("Instagram : erreur HTTP " + str(e.code))
    except Exception as e:
        raise RuntimeError("Instagram injoignable : " + str(e)[:160])


def _verifier():
    if not PRET:
        raise RuntimeError(
            "Instagram n'est pas configure. Ajoute CAPZO_IG_USER et CAPZO_IG_TOKEN "
            "dans CapzoIA/.env (compte professionnel + app Meta).")


def profil():
    _verifier()
    data = _appel("/" + UTILISATEUR, params={
        "fields": "username,name,biography,followers_count,follows_count,media_count,"
                  "profile_picture_url"})
    if "error" in data:
        return None, _erreur(data)
    return data, None


def medias(nombre=5):
    _verifier()
    data = _appel("/" + UTILISATEUR + "/media", params={
        "fields": "id,caption,media_type,media_product_type,permalink,thumbnail_url,"
                  "like_count,comments_count,timestamp",
        "limit": max(1, min(int(nombre or 5), 20))})
    if "error" in data:
        return [], _erreur(data)
    return data.get("data", []), None


def publier_video(url_video, legende="", attendre=90):
    """Publie un Reel. La video doit etre accessible par une URL PUBLIQUE (https)."""
    _verifier()
    if not str(url_video or "").startswith("https://"):
        return None, ("Il faut une adresse vidéo publique en https (Meta doit pouvoir la "
                      "télécharger). Héberge le fichier sur ton site Capzo, puis réessaie.")
    creation = _appel("/" + UTILISATEUR + "/media", "POST", {
        "media_type": "REELS", "video_url": url_video,
        "caption": (legende or "")[:2000], "share_to_feed": "true"})
    if "error" in creation or not creation.get("id"):
        return None, _erreur(creation)
    ident = creation["id"]

    limite = time.time() + max(20, int(attendre or 90))
    statut = "IN_PROGRESS"
    while time.time() < limite:
        info = _appel("/" + ident, params={"fields": "status_code,status"})
        statut = (info.get("status_code") or "").upper()
        if statut == "FINISHED":
            break
        if statut in ("ERROR", "EXPIRED"):
            return None, "Meta a refusé la vidéo : " + (info.get("status") or statut)
        time.sleep(4)
    if statut != "FINISHED":
        return None, ("La vidéo est encore en traitement chez Meta. Réessaie dans une minute "
                      "(identifiant de publication : " + ident + ").")

    publication = _appel("/" + UTILISATEUR + "/media_publish", "POST", {"creation_id": ident})
    if "error" in publication or not publication.get("id"):
        return None, _erreur(publication)
    media_id = publication["id"]
    lien = _appel("/" + media_id, params={"fields": "permalink"})
    return {"id": media_id, "lien": lien.get("permalink")}, None
