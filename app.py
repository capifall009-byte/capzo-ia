# -*- coding: utf-8 -*-
"""CAPZO IA — version locale, 100% gratuite, sans cle API.
Lancement : python app.py   (ou double-clic sur lancer.bat)
"""
import json
import os
import re
import sys
import threading
import time
import urllib.parse
import uuid
import webbrowser

from flask import (Flask, Response, g, jsonify, redirect, render_template, render_template_string,
                   request, send_from_directory, stream_with_context)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE = os.path.dirname(os.path.abspath(__file__))


def _charger_env(chemin=None):
    """Charge CapzoIA/.env (cle API, identifiants) sans dependance externe.

    Les variables deja definies dans le systeme restent prioritaires.
    """
    chemin = chemin or os.path.join(BASE, ".env")
    try:
        with open(chemin, "r", encoding="utf-8") as f:
            for ligne in f:
                ligne = ligne.strip()
                if not ligne or ligne.startswith("#") or "=" not in ligne:
                    continue
                if ligne.lower().startswith("export "):
                    ligne = ligne[7:]
                cle, valeur = ligne.split("=", 1)
                cle = cle.strip()
                valeur = valeur.strip().strip('"').strip("'")
                if cle and cle not in os.environ:
                    os.environ[cle] = valeur
    except FileNotFoundError:
        pass
    except Exception:
        pass


_charger_env()

from capzo import (agent, anim, apple_auth, auth, connecteurs, fichiers, github_auth,  # noqa: E402
                   google_auth, images, instagram, llm, memoire, quiz, social, video, voix)

UPLOADS = os.path.join(BASE, "uploads")
os.makedirs(UPLOADS, exist_ok=True)

app = Flask(__name__,
            template_folder=os.path.join(BASE, "templates"),
            static_folder=os.path.join(BASE, "static"))

app.config["MAX_CONTENT_LENGTH"] = 120 * 1024 * 1024  # 120 Mo par envoi

MAX_MESSAGES = 20
MAX_CHARS = 2000
MOT_DE_PASSE = (os.environ.get("CAPZO_MOT_DE_PASSE") or "").strip()


@app.before_request
def _proteger():
    """Mot de passe optionnel : utile quand l'appli est publiee sur Internet."""
    if not MOT_DE_PASSE:
        return None
    libre = ("/static", "/manifest.webmanifest", "/sw.js", "/favicon.ico")
    if request.path.startswith(libre):
        return None
    if request.path == "/partage":
        return None  # le partage Android n'envoie pas d'en-tete d'authentification
    auth = request.authorization
    if auth and auth.username == "capzo" and auth.password == MOT_DE_PASSE:
        return None
    return Response("Acces protege par mot de passe.", 401,
                    {"WWW-Authenticate": 'Basic realm="Capzo IA"'})


@app.before_request
def _identifier_visiteur():
    """Identifiant anonyme par navigateur : separe les comptes Google des visiteurs."""
    vid = request.cookies.get("capzo_vid") or ""
    if len(vid) != 32 or any(c not in "0123456789abcdef" for c in vid):
        vid = uuid.uuid4().hex
    g.visiteur_id = vid


@app.after_request
def _poser_cookie_visiteur(reponse):
    vid = getattr(g, "visiteur_id", None)
    if vid:
        reponse.set_cookie("capzo_vid", vid, max_age=60 * 60 * 24 * 365,
                           samesite="Lax", httponly=True)
    return reponse


# Connexion OAuth : optionnelle. Capzo reste utilisable sans compte ; seules les
# fonctions mail/agenda/réseaux sociaux exigent une connexion (vérifiée par
# chaque connecteur). Aucune porte bloquante à l'accueil.
# Les callbacks et endpoints d'état restent publics.
PUBLIC_API = {
    "/api/etat", "/api/auth/etat",
    "/api/google/etat", "/api/google/url", "/api/google/connexion", "/api/google/callback",
    "/api/github/etat", "/api/github/connexion", "/api/github/callback",
    "/api/apple/etat", "/api/apple/connexion", "/api/apple/callback",
    "/api/social/etat",
}
PUBLIC_API_PREFIXES = ("/api/social/",)


# Pieces jointes gardees en memoire pour la session en cours
PIECES = {}
PIECES_MAX = 40

# Catalogue de cerveaux proposables (installation en un clic)
CATALOGUE = [
    {"nom": "qwen2.5:0.5b", "taille": "0,4 Go", "note": "ultra rapide, idees simples"},
    {"nom": "qwen2.5:1.5b", "taille": "1,0 Go", "note": "rapide, bon equilibre (defaut)"},
    {"nom": "qwen2.5:3b", "taille": "1,9 Go", "note": "meilleure qualite, plus lent"},
    {"nom": "llama3.2:1b", "taille": "1,3 Go", "note": "tres rapide, autre style"},
    {"nom": "llama3.2:3b", "taille": "2,0 Go", "note": "bon en francais"},
    {"nom": "gemma2:2b", "taille": "1,6 Go", "note": "Google, reponses concises"},
    {"nom": "phi3.5", "taille": "2,2 Go", "note": "raisonnement et maths"},
    {"nom": "moondream", "taille": "1,7 Go", "note": "vision : photos et videos"},
    {"nom": "llava-phi3", "taille": "2,9 Go", "note": "vision + dialogue"},
]
INSTALLATIONS = {}


def _nettoyer_pieces():
    if len(PIECES) <= PIECES_MAX:
        return
    for cle, _ in sorted(PIECES.items(), key=lambda kv: kv[1]["t"])[:len(PIECES) - PIECES_MAX]:
        PIECES.pop(cle, None)


@app.route("/")
def index():
    site_url = (os.environ.get("CAPZO_SITE_URL") or request.url_root).rstrip("/") + "/"
    return render_template("index.html", site_url=site_url)


MANIFESTE = {
    "name": "capzo ia — assistant, images et vidéos",
    "short_name": "capzo ia",
    "description": "Assistant IA : chat, modes Build/Religion/Adulte/Histoire, images, vidéos, fichiers, Google/GitHub et réseaux sociaux.",
    "categories": ["productivity", "utilities"],
    "shortcuts": [
        {"name": "Nouvelle discussion", "short_name": "Discuter", "url": "/?mode=general",
         "icons": [{"src": "/static/icons/icon-192.png", "sizes": "192x192"}]},
        {"name": "Mode Build", "short_name": "Build", "url": "/?mode=build",
         "icons": [{"src": "/static/icons/icon-192.png", "sizes": "192x192"}]}
    ],
    "lang": "fr",
    "start_url": "/",
    "scope": "/",
    "display": "standalone",
    "orientation": "portrait",
    "background_color": "#0f172a",
    "theme_color": "#4f46e5",
    "icons": [
        {"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
        {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png"},
        {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
    ],
    "share_target": {
        "action": "/partage",
        "method": "POST",
        "enctype": "multipart/form-data",
        "params": {
            "title": "titre", "text": "texte", "url": "lien",
            "files": [{
                "name": "fichiers",
                "accept": ["image/*", "video/*", "application/pdf", "text/plain", "text/*"],
            }],
        },
    },
}


@app.route("/manifest.webmanifest")
def manifeste():
    return Response(json.dumps(MANIFESTE, ensure_ascii=False),
                    mimetype="application/manifest+json")


@app.route("/sw.js")
def service_worker():
    reponse = send_from_directory(app.static_folder, "sw.js")
    reponse.headers["Cache-Control"] = "no-cache"
    reponse.headers["Service-Worker-Allowed"] = "/"
    return reponse


@app.route("/robots.txt")
def robots_txt():
    site = (os.environ.get("CAPZO_SITE_URL") or request.url_root).rstrip("/")
    corps = "User-agent: *\nAllow: /\nSitemap: " + site + "/sitemap.xml\n"
    return Response(corps, mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap_xml():
    site = (os.environ.get("CAPZO_SITE_URL") or request.url_root).rstrip("/")
    corps = ('<?xml version="1.0" encoding="UTF-8"?>\n'
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
             '  <url><loc>' + site + '/</loc><changefreq>weekly</changefreq><priority>1.0</priority></url>\n'
             '</urlset>\n')
    return Response(corps, mimetype="application/xml")


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(os.path.join(app.static_folder, "icons"), "icon-192.png",
                               mimetype="image/png")


PARTAGE_PAGE = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>capzo ia — partage</title>
<style>
body{background:#0f172a;color:#f8fafc;font-family:system-ui,sans-serif;display:flex;
align-items:center;justify-content:center;min-height:100vh;margin:0;padding:24px;text-align:center}
a{display:inline-block;margin-top:18px;background:#4f46e5;color:#fff;padding:12px 22px;
border-radius:14px;text-decoration:none;font-weight:600}
p{opacity:.75;font-size:14px}
</style></head><body><div>
<h2>📎 {{ n }} fichier(s) ajouté(s)</h2>
<p>Capzo va les ouvrir dans la discussion.</p>
{% if texte %}<p>« {{ texte }} »</p>{% endif %}
<a href="/">Ouvrir Capzo</a>
</div>
<script>
try{ localStorage.setItem('capzo_partage', JSON.stringify({{ ids|tojson }})); }catch(e){}
setTimeout(function(){ location.replace('/'); }, 900);
</script></body></html>"""


@app.route("/partage", methods=["POST"])
def partage():
    """Cible du partage Android/iOS : recevoir une photo/video depuis une autre app."""
    fichiers_recus = request.files.getlist("fichiers") or request.files.getlist("files")
    ids = []
    for f in fichiers_recus[:4]:
        if f and f.filename:
            try:
                ids.append(_enregistrer_piece(f)["id"])
            except Exception:
                pass
    texte = (request.form.get("texte") or request.form.get("text") or "").strip()
    return render_template_string(PARTAGE_PAGE, n=len(ids), ids=ids, texte=texte[:200])


@app.route("/api/etat")
def api_etat():
    nom = llm.modele_actif() or llm.API_MODEL or llm.OLLAMA_MODEL
    return jsonify({"moteur": llm.moteur_actuel(), "modele": nom})


@app.route("/api/voix/liste")
def api_voix_liste():
    return jsonify({"disponible": voix.DISPONIBLE, "voix": voix.VOIX,
                    "defaut": voix.VOIX_DEFAUT})


@app.route("/api/voix", methods=["POST"])
def api_voix():
    """Transforme un morceau de texte en MP3 (voix neuronale gratuite)."""
    body = request.get_json(force=True, silent=True) or {}
    texte = str(body.get("texte") or "").strip()
    if not texte or len(texte) > 1200:
        return jsonify({"error": "Texte vide ou trop long."}), 400
    audio, erreur = voix.synthese(
        texte,
        voix=str(body.get("voix") or voix.VOIX_DEFAUT),
        debit=str(body.get("debit") or "+0%"),
    )
    if not audio:
        return jsonify({"error": erreur or "Synthese impossible."}), 503
    return Response(audio, mimetype="audio/mpeg",
                    headers={"Cache-Control": "private, max-age=3600"})


@app.route("/api/connecteurs")
def api_connecteurs():
    """Etat des connecteurs (mail, agenda, Instagram) + outils disponibles."""
    return jsonify({
        "mail": connecteurs.etat()["mail"],
        "agenda": connecteurs.etat()["agenda"],
        "instagram": instagram.etat(),
        "sociaux": social.etat(),
        "session": auth.etat(),
        "outils": [t["function"]["name"] for t in agent.OUTILS],
        "cloud": bool(llm.CLOUD_PRET),
        "modele_cloud": llm.API_MODEL or None,
    })


@app.route("/api/agenda/ics/<nom>")
def api_agenda_ics(nom):
    """Telecharge un rendez-vous .ics (l'agenda du telephone l'ouvre en un clic)."""
    if not re.match(r"^[a-f0-9]{6,32}\.ics$", nom or ""):
        return jsonify({"error": "Fichier invalide."}), 404
    dossier = os.path.join(UPLOADS, "agenda")
    if not os.path.exists(os.path.join(dossier, nom)):
        return jsonify({"error": "Rendez-vous introuvable."}), 404
    return send_from_directory(dossier, nom, mimetype="text/calendar",
                               as_attachment=True, download_name="capzo-rendez-vous.ics")


@app.route("/api/google/etat")
def api_google_etat():
    return jsonify(google_auth.etat())


@app.route("/api/google/url")
def api_google_url():
    url, erreur = google_auth.url_connexion(request.url_root)
    if erreur:
        return jsonify({"error": erreur}), 400
    return jsonify({"url": url, "redirect_uri": google_auth.redirect_uri_par_defaut(request.url_root)})


@app.route("/api/google/connexion")
def api_google_connexion():
    url, erreur = google_auth.url_connexion(request.url_root)
    if erreur:
        return redirect("/?connexion=echec&fournisseur=google&msg=" +
                        urllib.parse.quote(str(erreur)[:180]))
    return redirect(url)


@app.route("/api/google/callback")
def api_google_callback():
    code = request.args.get("code")
    state = request.args.get("state")
    erreur = request.args.get("error")
    if erreur:
        return redirect("/?google=refuse")
    if not code or not google_auth.verifier_state(state):
        return redirect("/?google=etat_invalide")
    ok, info = google_auth.echanger_code(code, request.url_root)
    if not ok:
        return redirect("/?google=echec&msg=" + urllib.parse.quote(info[:120]))
    p = google_auth.profil()
    auth.connecter("google", p.get("email"), p.get("nom"), p.get("photo"))
    return redirect("/?connexion=ok&email=" + urllib.parse.quote(info))


@app.route("/api/google/deconnexion", methods=["POST"])
def api_google_deconnexion():
    google_auth.deconnecter()
    return jsonify({"ok": True})


# ------------------------------------------------------------------ portail
@app.route("/api/auth/etat")
def api_auth_etat():
    return jsonify(auth.etat())


@app.route("/api/auth/civilite", methods=["POST"])
def api_auth_civilite():
    body = request.get_json(force=True, silent=True) or {}
    if not auth.definir_civilite(body.get("civilite")):
        return jsonify({"error": "Civilité invalide."}), 400
    return jsonify(auth.etat())


@app.route("/api/auth/deconnexion", methods=["POST"])
def api_auth_deconnexion():
    auth.deconnecter()
    return jsonify({"ok": True})


# ------------------------------------------------------------------ mémoire
@app.route("/api/memoire", methods=["GET"])
def api_memoire_lire():
    return jsonify({"faits": memoire.faits(), "historique": memoire.historique(),
                    "contexte": memoire.contexte()})


@app.route("/api/memoire", methods=["POST"])
def api_memoire_ajouter():
    body = request.get_json(force=True, silent=True) or {}
    texte = (body.get("texte") or "").strip()
    if not texte:
        return jsonify({"error": "Texte vide."}), 400
    memoire.ajouter_fait(texte)
    return jsonify({"ok": True, "faits": memoire.faits()})


@app.route("/api/memoire", methods=["DELETE"])
def api_memoire_effacer():
    body = request.get_json(force=True, silent=True) or {}
    if "index" in body:
        memoire.supprimer_fait(body.get("index"))
    elif body.get("tout") or not body:
        memoire.effacer_tout()
    return jsonify({"ok": True, "faits": memoire.faits(), "historique": memoire.historique()})


@app.route("/api/memoire/message", methods=["POST"])
def api_memoire_message():
    body = request.get_json(force=True, silent=True) or {}
    role = body.get("role")
    contenu = body.get("contenu") or body.get("content")
    if role in ("user", "assistant") and contenu:
        memoire.ajouter_message(role, contenu)
    return jsonify({"ok": True})


@app.route("/api/historique", methods=["GET"])
def api_historique():
    return jsonify({"historique": memoire.historique()})


# ------------------------------------------------------------------ GitHub
@app.route("/api/github/etat")
def api_github_etat():
    return jsonify(github_auth.etat())


@app.route("/api/github/connexion")
def api_github_connexion():
    url, erreur = github_auth.url_connexion(request.url_root)
    if erreur:
        return redirect("/?connexion=echec&fournisseur=github&msg=" +
                        urllib.parse.quote(str(erreur)[:180]))
    return redirect(url)


@app.route("/api/github/callback")
def api_github_callback():
    code = request.args.get("code")
    state = request.args.get("state")
    erreur = request.args.get("error")
    if erreur:
        return redirect("/?connexion=refuse")
    if not code or not github_auth.verifier_state(state):
        return redirect("/?connexion=etat_invalide")
    ok, info, msg = github_auth.echanger_code(code, request.url_root)
    if not ok:
        return redirect("/?connexion=echec&msg=" + urllib.parse.quote(str(msg)[:120]))
    auth.connecter("github", (info or {}).get("email"), (info or {}).get("nom"),
                   (info or {}).get("photo"))
    return redirect("/?connexion=ok&email=" + urllib.parse.quote(
        (info or {}).get("email") or (info or {}).get("login") or "GitHub"))


# ------------------------------------------------------------------ Apple
@app.route("/api/apple/etat")
def api_apple_etat():
    return jsonify(apple_auth.etat())


@app.route("/api/apple/connexion")
def api_apple_connexion():
    url, erreur = apple_auth.url_connexion(request.url_root)
    if erreur:
        return redirect("/?connexion=echec&fournisseur=apple&msg=" +
                        urllib.parse.quote(str(erreur)[:180]))
    return redirect(url)


@app.route("/api/apple/callback", methods=["GET", "POST"])
def api_apple_callback():
    donnees = request.form
    arguments = request.args
    erreur = arguments.get("error") or donnees.get("error")
    if erreur:
        return redirect("/?connexion=refuse")
    code = donnees.get("code") or arguments.get("code")
    state = donnees.get("state") or arguments.get("state")
    if not code or not apple_auth.verifier_state(state):
        return redirect("/?connexion=etat_invalide")
    ok, info, msg = apple_auth.callback(donnees, arguments, request.url_root)
    if not ok:
        return redirect("/?connexion=echec&msg=" + urllib.parse.quote(str(msg)[:120]))
    auth.connecter("apple", (info or {}).get("email"), (info or {}).get("nom"), None)
    return redirect("/?connexion=ok&email=" + urllib.parse.quote(
        (info or {}).get("email") or "Apple"))


# -------------------------------------------------- réseaux sociaux / Windsor
@app.route("/api/social/etat")
def api_social_etat():
    return jsonify(social.etat())


@app.route("/api/social/<service>/url")
def api_social_url(service):
    url, erreur = social.url_connexion(service, request.url_root)
    if erreur:
        return jsonify({"error": erreur}), 400
    return jsonify({"url": url})


@app.route("/api/social/<service>/callback")
def api_social_callback(service):
    code = request.args.get("code")
    state = request.args.get("state")
    erreur = request.args.get("error")
    propre = (service or "").lower()
    if erreur:
        return redirect("/?social=" + propre + "&resultat=refuse")
    if not code or not social.verifier_state(propre, state):
        return redirect("/?social=" + propre + "&resultat=etat_invalide")
    ok, info = social.callback(propre, code, request.url_root)
    if not ok:
        return redirect("/?social=" + propre + "&resultat=echec&msg=" +
                        urllib.parse.quote(str(info)[:120]))
    return redirect("/?social=" + propre + "&resultat=ok")


@app.route("/api/social/<service>/deconnexion", methods=["POST"])
def api_social_deconnexion(service):
    social.deconnecter(service)
    return jsonify({"ok": True})


@app.route("/api/social/<service>/token", methods=["POST"])
def api_social_token(service):
    body = request.get_json(force=True, silent=True) or {}
    token = str(body.get("token") or "").strip()
    if not social.connecter_token(service, token, body.get("compte")):
        return jsonify({"error": "Jeton invalide ou service inconnu."}), 400
    return jsonify({"ok": True})


@app.route("/api/social/windsor/test")
def api_social_windsor_test():
    return jsonify(social.tester_windsor())


@app.route("/api/video/<nom>")
def api_video(nom):
    if not nom or "/" in nom or "\\" in nom or not nom.endswith(".mp4"):
        return jsonify({"error": "Fichier invalide."}), 404
    dossier = os.path.join(UPLOADS, "videos")
    if not os.path.exists(os.path.join(dossier, nom)):
        return jsonify({"error": "Video introuvable."}), 404
    return send_from_directory(dossier, nom, mimetype="video/mp4",
                               as_attachment=False)
    try:
        installes = llm.modeles_chat()
    except Exception:
        installes = []
    vision = set(llm.modeles_vision()) if installes else set()
    return jsonify({
        "actif": llm.modele_actif(),
        "modeles": [{"nom": n, "vision": n in vision} for n in installes],
        "vision": bool(vision),
    })


def _enregistrer_piece(f):
    """Sauvegarde un fichier et l'analyse en local. Retourne les infos publiques."""
    nom = os.path.basename(f.filename).replace("\\", "_")
    ident = uuid.uuid4().hex[:10]
    chemin = os.path.join(UPLOADS, ident + "_" + nom)
    f.save(chemin)

    try:
        taille = os.path.getsize(chemin)
    except Exception:
        taille = 0
    g = fichiers.genre(nom, f.mimetype)
    texte = fichiers.extraire_texte(chemin) if g in ("texte", "pdf") else ""
    description = ""
    apercu = ""

    if g == "image":
        b64 = fichiers.image_b64(chemin)
        apercu = "data:image/jpeg;base64," + b64 if b64 else ""
        if b64:
            description = llm.decrire_images(
                [b64], "Decris cette image en francais en 3 phrases : sujet, couleurs, ambiance."
            )
    elif g == "video":
        images_v = fichiers.frames_video_b64(chemin, nombre=2)
        if images_v:
            apercu = "data:image/jpeg;base64," + images_v[0]
            description = llm.decrire_images(
                images_v, "Ces images viennent d'une video. Decris en francais la scene, en 3 phrases."
            )

    PIECES[ident] = {"nom": nom, "genre": g, "texte": texte, "description": description,
                     "taille": taille, "chemin": chemin, "t": time.time(),
                     "apercu": apercu}
    _nettoyer_pieces()

    return {"id": ident, "nom": nom, "genre": g, "taille": taille,
            "apercu": apercu, "description": description,
            "extrait": (texte[:300] + ("…" if len(texte) > 300 else ""))}


@app.route("/api/upload", methods=["POST"])
def api_upload():
    """Recoit un fichier (photo, video, document), l'analyse en local."""
    f = request.files.get("fichier")
    if not f or not f.filename:
        return jsonify({"error": "Aucun fichier recu."}), 400
    infos = _enregistrer_piece(f)
    infos["vision"] = bool(llm.modeles_vision())
    return jsonify(infos)


@app.route("/api/piece/<ident>")
def api_piece(ident):
    """Infos d'une piece jointe (utilise par le partage depuis le telephone)."""
    p = PIECES.get(str(ident))
    if not p:
        return jsonify({"error": "Piece introuvable (redemarrage du serveur ?)."}), 404
    return jsonify({"id": ident, "nom": p["nom"], "genre": p["genre"],
                    "taille": p["taille"], "apercu": p["apercu"]})


def _bloc_fichiers(identifiants):
    """Transforme les pieces jointes en texte utilisable par le modele."""
    if not isinstance(identifiants, list):
        return ""
    morceaux, total = [], 0
    for ident in identifiants[:6]:
        p = PIECES.get(str(ident))
        if not p:
            continue
        tete = f"- {p['nom']} ({p['genre']})"
        corps = p["description"] or p["texte"]
        if not corps:
            corps = "fichier recu, pas de texte exploitable."
        corps = corps[:2500]
        morceaux.append(tete + " :\n" + corps)
        total += len(corps)
        if total > 6000:
            break
    if not morceaux:
        return ""
    return ("\n\n[Fichiers joints par l'utilisateur]\n" + "\n".join(morceaux) +
            "\n[Fin des fichiers joints]")


def _preparer_profil(body):
    """Profil d'usage : general, education, code ou loisir."""
    profil = (body.get("profil") or "general").lower()
    return profil if profil in llm.PROFILS else "general"


def _preparer(body):
    """Valide la conversation et ajoute les pieces jointes au dernier message."""
    brut = body.get("messages") if isinstance(body.get("messages"), list) else []
    messages = [
        {"role": m.get("role"), "content": str(m.get("content", ""))[:MAX_CHARS]}
        for m in brut[-MAX_MESSAGES:]
        if isinstance(m, dict) and m.get("role") in ("user", "assistant") and m.get("content")
    ]
    if not messages or messages[-1]["role"] != "user":
        return None, None, None, None, None
    mode = (body.get("mode") or "auto").lower()
    if mode not in ("auto", "local", "online"):
        mode = "auto"
    modele = (body.get("modele") or "").strip() or None
    if modele in ("auto", "local", "online"):
        modele = None
    bloc = _bloc_fichiers(body.get("fichiers"))
    if bloc:
        messages[-1]["content"] = messages[-1]["content"] + bloc
    memoire = str(body.get("memoire") or "").strip()[:4000]
    return messages, mode, modele, _preparer_profil(body), memoire


@app.route("/api/chat", methods=["POST"])
def api_chat():
    body = request.get_json(force=True, silent=True) or {}
    messages, mode, modele, profil = _preparer(body)
    if messages is None:
        return jsonify({"error": "Format de conversation invalide."}), 400
    profil = llm.profil_auto(profil, messages[-1]["content"])

    memoire_ctx = memoire.contexte()
    memoire.ajouter_message("user", messages[-1]["content"])
    try:
        type_reponse, contenu = llm.decide(messages, mode=mode, modele=modele, profil=profil,
                                           memoire=memoire_ctx)
    except Exception as e:
        return jsonify({"error": f"Impossible de joindre le service IA ({e})."}), 502

    if type_reponse == "text":
        memoire.ajouter_message("assistant", contenu)
        reponse = {"text": contenu}
        m = re.search(r"R[ée]essaie dans (\d+) s", contenu or "")
        if m:
            reponse["retry_after"] = int(m.group(1))
        return jsonify(reponse)

    if type_reponse == "image":
        memoire.ajouter_message("assistant", contenu.get("text", "Voici ton image."))
        try:
            image = images.generer_data_url(contenu["prompt"], seed=abs(hash(contenu["prompt"])) % 100000)
            return jsonify({"text": contenu.get("text", "Voici ton image."), "image": image})
        except Exception as e:
            return jsonify({"text": "Je n'ai pas reussi a generer l'image (" + str(e) + ").",
                            "error": "image"}), 200

    # animation
    memoire.ajouter_message("assistant", contenu.get("text", "Voici ta petite animation."))
    try:
        resultat = anim.fabriquer(contenu.get("prompt", ""), contenu.get("narration", ""))
        return jsonify({"text": contenu.get("text", "Voici ta petite animation."),
                        "animation": resultat})
    except Exception as e:
        return jsonify({"text": "Je n'ai pas reussi a generer l'animation (" + str(e) + ").",
                        "error": "animation"}), 200


def _media_deja_pret(type_reponse, contenu):
    """Fabrique l'image, l'animation ou la video et renvoie le dict JSON."""
    if type_reponse == "image":
        try:
            image = images.generer_data_url(contenu["prompt"], seed=abs(hash(contenu["prompt"])) % 100000)
            return {"text": contenu.get("text", "Voici ton image."), "image": image}
        except Exception as e:
            return {"text": "Je n'ai pas reussi a generer l'image (" + str(e) + ").", "error": "image"}
    if type_reponse == "video":
        try:
            url = video.generer(contenu.get("prompt", ""), contenu.get("narration", ""),
                                sous_titres=contenu.get("sous_titres", True),
                                musique=contenu.get("musique", True))
            return {"text": contenu.get("text", "Voici ta video."), "video": url}
        except Exception as e:
            return {"text": "Je n'ai pas reussi a generer la video (" + str(e) + ").", "error": "video"}
    try:
        resultat = anim.fabriquer(contenu.get("prompt", ""), contenu.get("narration", ""))
        return {"text": contenu.get("text", "Voici ta petite animation."), "animation": resultat}
    except Exception as e:
        return {"text": "Je n'ai pas reussi a generer l'animation (" + str(e) + ").", "error": "animation"}


@app.route("/api/chat/stream", methods=["POST"])
def api_chat_stream():
    """Reponse en flux : le texte s'affiche pendant qu'il est genere."""
    body = request.get_json(force=True, silent=True) or {}
    messages, mode, modele, profil = _preparer(body)
    reflexion = (body.get("reflexion") or "equilibre").lower()
    if reflexion not in ("rapide", "equilibre", "approfondi"):
        reflexion = "equilibre"
    if messages is not None:
        profil = llm.profil_auto(profil, messages[-1]["content"])
    system = llm.systeme_pour(profil)
    _memoire_ctx = memoire.contexte()
    if _memoire_ctx:
        system = system + "\n\n" + _memoire_ctx

    def evt(charge):
        return "data: " + json.dumps(charge, ensure_ascii=False) + "\n\n"

    @stream_with_context
    def flux():
        if messages is None:
            yield evt({"type": "error", "text": "Format de conversation invalide."})
            return

        if messages is not None:
            memoire.ajouter_message("user", messages[-1]["content"])
        demande = messages[-1]["content"]

        # Sans cle cloud, le petit modele local produit des quiz approximatifs :
        # on utilise un generateur deterministe (instantane et fiable).
        if not llm.CLOUD_PRET and quiz.est_demande_quiz(demande):
            quiz_txt = quiz.generer(demande)
            if quiz_txt:
                yield evt({"type": "attente", "text": "Je prépare le quiz…"})
                for morceau in quiz_txt.splitlines(keepends=True):
                    yield evt({"type": "delta", "text": morceau})
                memoire.ajouter_message("assistant", quiz_txt)
                yield evt({"type": "fin"})
                return

        if llm.veut_media(demande):
            yield evt({"type": "attente", "text": "Preparation du media..."})
            try:
                type_reponse, contenu = llm.decide(messages, mode=mode, modele=modele,
                                                  profil=profil)
            except Exception as e:
                yield evt({"type": "error", "text": f"Impossible de joindre le service IA ({e})."})
                return
            if type_reponse == "text":
                memoire.ajouter_message("assistant", contenu if isinstance(contenu, str) else str(contenu))
                yield evt({"type": "message", "payload": {"text": contenu}})
            else:
                pret = _media_deja_pret(type_reponse, contenu)
                memoire.ajouter_message("assistant", pret.get("text", "") if isinstance(pret, dict) else "")
                yield evt({"type": "message", "payload": pret})
            return

        if agent.detecter_intention(demande):
            yield evt({"type": "attente", "text": "Je consulte tes connecteurs…"})
            try:
                for genre, valeur in agent.repondre(messages, system, mode=mode,
                                                    modele=modele, reflexion=reflexion,
                                                    profil=profil):
                    if genre == "delta":
                        yield evt({"type": "delta", "text": valeur})
                    elif genre == "stats":
                        yield evt({"type": "stats", "stats": valeur})
                    elif genre in ("outil", "ouvrir", "lien"):
                        yield evt({"type": genre, **(valeur or {})})
            except Exception as e:
                yield evt({"type": "error", "text": f"Connecteur indisponible ({e})."})
            memoire.ajouter_message("assistant", complet)
            yield evt({"type": "fin"})
            return

        try:
            for genre, valeur in llm.chat_stream(messages, system=system, mode=mode,
                                                 modele=modele, reflexion=reflexion,
                                                 profil=profil):
                if genre == "delta":
                    yield evt({"type": "delta", "text": valeur})
                else:
                    yield evt({"type": "stats", "stats": valeur})
        except Exception as e:
            yield evt({"type": "error", "text": f"Moteur IA indisponible ({e})."})
        memoire.ajouter_message("assistant", complet)
        yield evt({"type": "fin"})

    return Response(flux(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/api/modeles")
def api_modeles():
    """Modeles de chat installes : alimente le selecteur du header."""
    try:
        installes = llm.modeles_chat()
    except Exception:
        installes = llm._modeles_installes()
    try:
        vision = set(llm.modeles_vision())
    except Exception:
        vision = set()
    return jsonify({
        "actif": llm.modele_actif(),
        "moteur": llm.moteur_actuel(),
        "modeles": [{"nom": n, "vision": n in vision} for n in installes],
    })


@app.route("/api/cerveaux")
def api_cerveaux():
    """Modeles installes + catalogue a installer."""
    try:
        installes = set(llm._modeles_installes())
    except Exception:
        installes = set()
    liste = []
    for m in CATALOGUE:
        base = m["nom"].split(":")[0]
        present = any(i == m["nom"] or i.startswith(base + ":") for i in installes)
        liste.append({**m, "installe": present,
                      "en_cours": INSTALLATIONS.get(m["nom"], {}).get("etat") == "encours"})
    return jsonify({"installes": sorted(installes), "catalogue": liste,
                    "vision": bool(llm.modeles_vision())})


@app.route("/api/installer", methods=["POST"])
def api_installer():
    """Installe un cerveau Ollama en arriere-plan."""
    body = request.get_json(force=True, silent=True) or {}
    nom = str(body.get("nom") or "").strip()
    if not nom or len(nom) > 60 or " " in nom:
        return jsonify({"error": "Nom de modele invalide."}), 400
    if INSTALLATIONS.get(nom, {}).get("etat") == "encours":
        return jsonify({"ok": True, "etat": "deja en cours"})

    def travail():
        INSTALLATIONS[nom] = {"etat": "encours", "debut": time.time()}
        try:
            import shutil
            import subprocess
            exe = shutil.which("ollama") or "ollama"
            p = subprocess.run([exe, "pull", nom], capture_output=True, timeout=3600)
            INSTALLATIONS[nom] = {"etat": "fini" if p.returncode == 0 else "echec",
                                  "debut": time.time()}
        except Exception as e:
            INSTALLATIONS[nom] = {"etat": "echec", "erreur": str(e), "debut": time.time()}

    threading.Thread(target=travail, daemon=True).start()
    return jsonify({"ok": True, "etat": "encours", "nom": nom})


@app.route("/api/chauffe")
def api_chauffe():
    """Charge le modele en memoire pour que la premiere question soit rapide."""
    def travail():
        try:
            llm.decharger_autres()
            llm.complete("ok", system="Reponds par ok.", timeout=600)
        except Exception:
            pass
    threading.Thread(target=travail, daemon=True).start()
    return jsonify({"ok": True, "moteur": llm.moteur_actuel()})


def _ip_locale():
    """Adresse IP du PC sur le reseau (pour ouvrir Capzo depuis un telephone)."""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def main():
    env_port = os.environ.get("PORT")
    hote = (os.environ.get("CAPZO_HOST") or ("0.0.0.0" if env_port else "127.0.0.1")).strip()
    try:
        port = int(env_port or os.environ.get("CAPZO_PORT") or "5050")
    except ValueError:
        port = 5050

    local = "http://127.0.0.1:" + str(port)
    print("=" * 60)
    print("  CAPZO IA — version locale sans cle API")
    print("  Ordinateur : " + local)
    if hote in ("0.0.0.0", "::", ""):
        print("  Telephone  : http://" + _ip_locale() + ":" + str(port) + "  (meme Wi-Fi)")
    print("  (Ctrl+C pour arreter)")
    print("=" * 60)

    if os.environ.get("CAPZO_NO_BROWSER") != "1":
        threading.Timer(1.2, lambda: webbrowser.open(local)).start()
    app.run(host=hote or "127.0.0.1", port=port, threaded=True, use_reloader=False)


@app.route("/google9cad14f7ffb7c207.html")
def google_search_console_verification():
    """Fichier de verification Google Search Console."""
    return Response("google-site-verification: google9cad14f7ffb7c207.html",
                    mimetype="text/html")


if __name__ == "__main__":
    main()
