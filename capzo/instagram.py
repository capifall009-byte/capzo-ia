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


def _appel(chemin, methode="GET", params=None, timeout=40, jeton=None):
    params = dict(params or {})
    params["access_token"] = jeton or TOKEN
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


def _identifier(jeton=None, utilisateur=None):
    """Resout le jeton et l'identifiant Instagram (env ou jeton colle dans l'appli)."""
    jeton = (jeton or TOKEN or "").strip()
    utilisateur = (utilisateur or UTILISATEUR or "").strip()
    if not jeton:
        raise RuntimeError(
            "Instagram n'est pas connecte. Ouvre le panneau des connecteurs (🔌) "
            "et colle un jeton d'acces Meta, ou ajoute CAPZO_IG_TOKEN dans Render.")
    if not utilisateur:
        # Le visiteur n'a donne que son jeton : on demande a Meta quel compte IG y est lie.
        data = _appel("/me", params={
            "fields": "id,name,accounts{id,name,instagram_account{id,username}}"
        }, jeton=jeton)
        if "error" in data:
            raise RuntimeError(_erreur(data))
        comptes = ((data.get("accounts") or {}).get("data")) or []
        for compte in comptes:
            ig = compte.get("instagram_account") or {}
            if ig.get("id"):
                utilisateur = str(ig["id"])
                break
        if not utilisateur:
            for compte in comptes:
                pid = compte.get("id")
                if not pid:
                    continue
                info = _appel("/" + str(pid), params={
                    "fields": "instagram_account{id,username}"}, jeton=jeton)
                ig = info.get("instagram_account") or {}
                if ig.get("id"):
                    utilisateur = str(ig["id"])
                    break
        if not utilisateur:
            raise RuntimeError(
                "Compte Instagram introuvable avec ce jeton. Colle aussi l'identifiant "
                "du compte professionnel (champ « ID du compte ») dans le panneau.")
    return jeton, utilisateur


def profil(jeton=None, utilisateur=None):
    jeton, utilisateur = _identifier(jeton, utilisateur)
    data = _appel("/" + utilisateur, params={
        "fields": "username,name,biography,followers_count,follows_count,media_count,"
                  "profile_picture_url"}, jeton=jeton)
    if "error" in data:
        return None, _erreur(data)
    return data, None


def medias(nombre=5, jeton=None, utilisateur=None):
    jeton, utilisateur = _identifier(jeton, utilisateur)
    data = _appel("/" + utilisateur + "/media", params={
        "fields": "id,caption,media_type,media_product_type,permalink,thumbnail_url,"
                  "like_count,comments_count,timestamp",
        "limit": max(1, min(int(nombre or 5), 20))}, jeton=jeton)
    if "error" in data:
        return [], _erreur(data)
    return data.get("data", []), None


def publier_video(url_video, legende="", attendre=90, jeton=None, utilisateur=None):
    """Publie un Reel. La video doit etre accessible par une URL PUBLIQUE (https)."""
    jeton, utilisateur = _identifier(jeton, utilisateur)
    if not str(url_video or "").startswith("https://"):
        return None, ("Il faut une adresse vidéo publique en https (Meta doit pouvoir la "
                      "télécharger). Héberge le fichier sur ton site Capzo, puis réessaie.")
    creation = _appel("/" + utilisateur + "/media", "POST", {
        "media_type": "REELS", "video_url": url_video,
        "caption": (legende or "")[:2000], "share_to_feed": "true"}, jeton=jeton)
    if "error" in creation or not creation.get("id"):
        return None, _erreur(creation)
    ident = creation["id"]

    limite = time.time() + max(20, int(attendre or 90))
    statut = "IN_PROGRESS"
    while time.time() < limite:
        info = _appel("/" + ident, params={"fields": "status_code,status"}, jeton=jeton)
        statut = (info.get("status_code") or "").upper()
        if statut == "FINISHED":
            break
        if statut in ("ERROR", "EXPIRED"):
            return None, "Meta a refusé la vidéo : " + (info.get("status") or statut)
        time.sleep(4)
    if statut != "FINISHED":
        return None, ("La vidéo est encore en traitement chez Meta. Réessaie dans une minute "
                      "(identifiant de publication : " + ident + ").")

    publication = _appel("/" + utilisateur + "/media_publish", "POST",
                         {"creation_id": ident}, jeton=jeton)
    if "error" in publication or not publication.get("id"):
        return None, _erreur(publication)
    media_id = publication["id"]
    lien = _appel("/" + media_id, params={"fields": "permalink"}, jeton=jeton)
    return {"id": media_id, "lien": lien.get("permalink")}, None
