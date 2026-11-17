# -*- coding: utf-8 -*-
"""Petit agent : Capzo choisit et utilise des connecteurs (mail, agenda, Instagram, apps).

Deux modes :
  - commandes simples reconnues par mots-cles (tres fiable, meme avec un petit modele) ;
  - appel d'outils par le modele (cloud ou Ollama) pour les demandes libres.
"""
import json
import re
import time
import urllib.parse
import urllib.request

from . import connecteurs, google_auth, instagram, internet, llm

MAX_TOURS = 3

LIENS_APPS = {
    "whatsapp": "https://wa.me/",
    "instagram": "https://www.instagram.com/",
    "youtube": "https://m.youtube.com/",
    "maps": "https://www.google.com/maps",
    "plan": "https://www.google.com/maps",
    "spotify": "https://open.spotify.com/",
    "tiktok": "https://www.tiktok.com/",
    "facebook": "https://www.facebook.com/",
    "gmail": "https://mail.google.com/",
    "agenda": "https://calendar.google.com/",
    "calendrier": "https://calendar.google.com/",
    "appareil photo": None,
}

OUTILS = [
    {"type": "function", "function": {
        "name": "lire_mails",
        "description": "Lire les derniers mails de la boite de reception.",
        "parameters": {"type": "object", "properties": {
            "nombre": {"type": "integer", "description": "Nombre de mails (1 a 15)"},
            "non_lus": {"type": "boolean", "description": "Seulement les non lus"}},
            "required": []}}},
    {"type": "function", "function": {
        "name": "envoyer_mail",
        "description": "Envoyer un mail. N'appelle cet outil qu'avec l'adresse, le sujet et le corps.",
        "parameters": {"type": "object", "properties": {
            "destinataire": {"type": "string", "description": "Adresse email du destinataire"},
            "sujet": {"type": "string"},
            "corps": {"type": "string"}},
            "required": ["destinataire", "sujet", "corps"]}}},
    {"type": "function", "function": {
        "name": "lire_agenda",
        "description": "Lire les prochains rendez-vous de l'agenda.",
        "parameters": {"type": "object", "properties": {
            "jours": {"type": "integer", "description": "Fenetre en jours (1 a 30)"}},
            "required": []}}},
    {"type": "function", "function": {
        "name": "creer_evenement",
        "description": "Ajouter un rendez-vous a l'agenda.",
        "parameters": {"type": "object", "properties": {
            "titre": {"type": "string"},
            "debut": {"type": "string", "description": "Date et heure locales AAAA-MM-JJ HH:MM"},
            "duree_min": {"type": "integer"},
            "lieu": {"type": "string"}},
            "required": ["titre", "debut"]}}},
    {"type": "function", "function": {
        "name": "instagram_profil",
        "description": "Statistiques du compte Instagram (abonnes, publications, bio).",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "instagram_medias",
        "description": "Dernieres publications Instagram avec likes et commentaires.",
        "parameters": {"type": "object", "properties": {
            "nombre": {"type": "integer"}}, "required": []}}},
    {"type": "function", "function": {
        "name": "instagram_publier",
        "description": "Publier un Reel Instagram depuis une URL video publique https.",
        "parameters": {"type": "object", "properties": {
            "url_video": {"type": "string"},
            "legende": {"type": "string"}},
            "required": ["url_video"]}}},
    {"type": "function", "function": {
        "name": "ouvrir_app",
        "description": "Ouvrir une application sur le telephone (whatsapp, instagram, maps, youtube, spotify, tel, sms).",
        "parameters": {"type": "object", "properties": {
            "nom": {"type": "string"},
            "cible": {"type": "string", "description": "Numero, adresse ou recherche (optionnel)"}},
            "required": ["nom"]}}},
    {"type": "function", "function": {
        "name": "heure_date",
        "description": "Donne la date et l'heure actuelles.",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "google_connexion",
        "description": "Connecter le compte Google de l'utilisateur (mail + agenda) en un clic.",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "google_deconnexion",
        "description": "Deconnecter le compte Google.",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "recherche_web",
        "description": "Recherche sur Internet (DuckDuckGo) et renvoie des resultats avec liens.",
        "parameters": {"type": "object", "properties": {
            "requete": {"type": "string", "description": "La requete de recherche"},
            "nombre": {"type": "integer", "description": "Nombre de resultats (1 a 10)"}},
            "required": ["requete"]}}},
    {"type": "function", "function": {
        "name": "lire_page",
        "description": "Lit le contenu texte d'une page web a partir de son URL.",
        "parameters": {"type": "object", "properties": {
            "url": {"type": "string", "description": "URL complete de la page"}},
            "required": ["url"]}}},
]

MOTS_MAIL = ("mail", "mails", "e-mail", "email", "courriel", "boite de reception", "boîte de réception")
MOTS_AGENDA = ("agenda", "rendez-vous", "rdv", "calendrier", "planning", "meeting")
MOTS_INSTA = ("instagram", "insta", "reel", "reels", "publication insta")
MOTS_GOOGLE = ("google", "connexion", "connecte", "compte")
MOTS_APP = ("ouvre", "ouvrir", "lance", "appelle", "sms", "whatsapp", "maps", "youtube", "spotify")
MOTS_INTERNET = ("cherche", "recherche", "rechercher", "internet", "actualite", "actualité", "news", "quoi de neuf", "dernieres infos", "dernières infos", "trouve", "google")


def _contient(texte, mots):
    t = (texte or "").lower()
    return any(m in t for m in mots)


def detecter_intention(texte):
    return (_contient(texte, MOTS_MAIL) or _contient(texte, MOTS_AGENDA)
            or _contient(texte, MOTS_INSTA) or _contient(texte, MOTS_APP)
            or _contient(texte, MOTS_GOOGLE) or _contient(texte, MOTS_INTERNET))


def _resume_mails(mails):
    if not mails:
        return "Aucun mail a afficher."
    lignes = [f"Voici tes {len(mails)} derniers mails :"]
    for i, m in enumerate(mails, 1):
        etat = "" if m.get("lu") else " 🔵"
        lignes.append(f"{i}. **{m['sujet']}**{etat} — {m['de']}\n   {m['extrait'][:220]}")
    return "\n".join(lignes)


def _resume_agenda(evts, jours):
    if not evts:
        return f"Rien de prevu dans les {jours} prochains jours."
    lignes = [f"Tes prochains rendez-vous ({jours} jours) :"]
    for e in evts:
        lieu = (" · " + e["lieu"]) if e.get("lieu") else ""
        lignes.append(f"• **{e['debut']}** → {e['titre']}{lieu}")
    return "\n".join(lignes)


def _lien_app(nom, cible=""):
    nom = (nom or "").strip().lower()
    cible = (cible or "").strip()
    if nom in ("tel", "telephone", "téléphone", "appel", "appelle"):
        if not cible:
            return None, "Donne-moi le numero a appeler."
        return ("tel:" + re.sub(r"[^\d+]", "", cible),
                "J'ouvre le telephone sur " + cible + ".")
    if nom == "sms":
        return ("sms:" + re.sub(r"[^\d+]", "", cible),
                "J'ouvre les SMS" + (" pour " + cible if cible else "") + ".")
    if nom in ("mail", "email"):
        return ("mailto:" + cible, "J'ouvre ta messagerie.")
    base = LIENS_APPS.get(nom)
    if not base:
        return None, ("Je ne sais pas ouvrir « " + nom + " ». Je peux ouvrir : "
                      + ", ".join(sorted(k for k in LIENS_APPS if LIENS_APPS[k] and k != "plan")) + ".")
    if nom in ("maps", "plan") and cible:
        return (base + "/search/?api=1&query=" + urllib.parse.quote(cible),
                "J'ouvre la carte sur " + cible + ".")
    return (base, "J'ouvre " + nom + ".")


def executer(nom, args):
    """Execute un outil. Retourne (resultat_json, evenement_ui|None)."""
    args = args if isinstance(args, dict) else {}
    try:
        if nom == "lire_mails":
            mails, err = connecteurs.lire_mails(args.get("nombre", 5), bool(args.get("non_lus")))
            return (json.dumps({"erreur": err} if err else {"mails": mails}, ensure_ascii=False),
                    None)
        if nom == "envoyer_mail":
            ok, message = connecteurs.envoyer_mail(
                args.get("destinataire"), args.get("sujet"), args.get("corps"))
            return json.dumps({"ok": ok, "message": message}, ensure_ascii=False), None
        if nom == "lire_agenda":
            jours = int(args.get("jours") or 7)
            evts, err = connecteurs.agenda_evenements(jours)
            return (json.dumps({"erreur": err} if err else {"evenements": evts}, ensure_ascii=False),
                    None)
        if nom == "creer_evenement":
            infos, err = connecteurs.creer_evenement(
                args.get("titre"), args.get("debut"), args.get("duree_min") or 60,
                args.get("lieu") or "", args.get("description") or "")
            if err:
                return json.dumps({"erreur": err}, ensure_ascii=False), None
            ev = {"type": "lien", "url": infos.get("lien"), "titre": "Ajouter à mon agenda",
                  "texte": infos.get("titre")} if infos.get("lien") else None
            return json.dumps(infos, ensure_ascii=False), ev
        if nom == "instagram_profil":
            data, err = instagram.profil()
            return json.dumps({"erreur": err} if err else {"profil": data}, ensure_ascii=False), None
        if nom == "instagram_medias":
            data, err = instagram.medias(args.get("nombre", 5))
            return json.dumps({"erreur": err} if err else {"medias": data}, ensure_ascii=False), None
        if nom == "instagram_publier":
            data, err = instagram.publier_video(args.get("url_video"), args.get("legende") or "")
            if err:
                return json.dumps({"erreur": err}, ensure_ascii=False), None
            return (json.dumps(data, ensure_ascii=False),
                    {"type": "lien", "url": data.get("lien"), "titre": "Voir le Reel",
                     "texte": "Publication Instagram"})
        if nom == "ouvrir_app":
            lien, texte = _lien_app(args.get("nom"), args.get("cible") or "")
            if not lien:
                return json.dumps({"erreur": texte}, ensure_ascii=False), None
            return (json.dumps({"ok": True, "lien": lien}, ensure_ascii=False),
                    {"type": "ouvrir", "url": lien, "texte": texte})
        if nom == "heure_date":
            return json.dumps({"maintenant": time.strftime("%Y-%m-%d %H:%M", time.localtime()),
                               "jour": time.strftime("%A", time.localtime())},
                              ensure_ascii=False), None
        if nom == "google_connexion":
            return (json.dumps({"ok": True, "lien": "/api/google/connexion"}, ensure_ascii=False),
                    {"type": "lien", "url": "/api/google/connexion", "titre": "Connecter Google",
                     "texte": "Ouvre Google pour autoriser Capzo"})
        if nom == "google_deconnexion":
            google_auth.deconnecter()
            return json.dumps({"ok": True, "message": "Compte Google deconnecte."}, ensure_ascii=False), None
        if nom == "recherche_web":
            res, err = internet.rechercher(args.get("requete", ""), int(args.get("nombre") or 6))
            if err:
                return json.dumps({"erreur": err}, ensure_ascii=False), None
            return json.dumps({"resultats": res}, ensure_ascii=False), None
        if nom == "lire_page":
            texte, err = internet.lire_page(args.get("url", ""))
            if err:
                return json.dumps({"erreur": err}, ensure_ascii=False), None
            return json.dumps({"texte": texte}, ensure_ascii=False), None
        return json.dumps({"erreur": "Outil inconnu."}, ensure_ascii=False), None
    except Exception as e:
        return json.dumps({"erreur": str(e)[:200]}, ensure_ascii=False), None


def _appel_outils(messages, system, mode, modele):
    """Demande au modele quels outils appeler. Retourne la liste (peut etre vide)."""
    if mode == "online":
        return []
    # Cloud compatible OpenAI
    if mode in ("auto", "cloud") and llm.CLOUD_PRET:
        payload = {"model": llm.API_MODEL,
                   "messages": ([{"role": "system", "content": system}] if system else []) + messages,
                   "tools": OUTILS, "tool_choice": "auto",
                   "temperature": 0.2, "max_tokens": 400}
        try:
            with llm._cloud_requete(payload, timeout=90) as r:
                data = json.loads(r.read().decode("utf-8", "replace"))
            msg = ((data.get("choices") or [{}])[0].get("message") or {})
            return msg.get("tool_calls") or []
        except Exception:
            return []
    # Ollama
    if llm._ollama_pret():
        try:
            corps = {"model": modele or llm.modele_actif() or llm.OLLAMA_MODEL,
                     "messages": ([{"role": "system", "content": system}] if system else []) + messages,
                     "tools": OUTILS, "stream": False,
                     "options": {"temperature": 0.2, "num_predict": 300}}
            req = urllib.request.Request(
                llm.OLLAMA_URL + "/api/chat",
                data=json.dumps(corps).encode("utf-8"),
                headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.loads(r.read().decode("utf-8", "replace"))
            return (data.get("message") or {}).get("tool_calls") or []
        except Exception:
            return []
    return []


def _executer_direct(texte):
    """Commandes evidentes, sans dependre du modele (tres fiable)."""
    t = (texte or "").lower()
    if _contient(t, ("cherche", "recherche", "rechercher", "trouve", "trouver")) and not _contient(t, ("mes mails", "mes rendez", "mon instagram")):
        requete = texte
        for mot in ("cherche", "recherche", "rechercher", "trouve", "trouver", "sur internet", "sur le web", "pour moi", "capzo"):
            requete = __import__("re").sub(r"(?i)\b" + __import__("re").escape(mot) + r"\b", "", requete)
        requete = requete.strip(" .,:;!?")
        if not requete:
            requete = texte
        res, err = internet.rechercher(requete, 6)
        if err:
            return [("outil", {"nom": "recherche_web", "ok": False})], err
        if not res:
            return [("outil", {"nom": "recherche_web", "ok": True})], "Aucun resultat pour « " + requete + " »."
        lignes = ["Resultats pour « " + requete + " » :"]
        for i, r in enumerate(res, 1):
            lignes.append(str(i) + ". **" + r["titre"] + "**\n   " + r["extrait"] + "\n   " + r["url"])
        return ([("outil", {"nom": "recherche_web", "ok": True})], "\n".join(lignes))
    if _contient(t, ("deconnecte", "déconnecte", "deconnexion", "déconnexion")) and "google" in t:
        google_auth.deconnecter()
        return ([("outil", {"nom": "google_deconnexion", "ok": True})],
                "Compte Google déconnecté.")
    if _contient(t, ("connecte", "connexion", "connecter")) and _contient(t, ("google", "compte", "gmail", "mail", "agenda")):
        return ([("outil", {"nom": "google_connexion", "ok": True}),
                 ("lien", {"url": "/api/google/connexion", "titre": "Connecter Google",
                           "texte": "Ouvre Google pour autoriser Capzo"})],
                "Clique sur le bouton pour connecter ton compte Google en un clic.")
    if _contient(t, MOTS_MAIL) and _contient(t, ("lis", "lire", "montre", "résume", "resume", "derniers", "voir")):
        mails, err = connecteurs.lire_mails(5, "non lu" in t or "non-lu" in t)
        return ([("outil", {"nom": "lire_mails", "ok": not err})],
                err or _resume_mails(mails))
    if _contient(t, MOTS_AGENDA) and _contient(t, ("lis", "lire", "montre", "mes", "prochain", "résume", "resume", "voir")):
        jours = 7
        m = re.search(r"(\d+)\s*(jour|jours|semaine)", t)
        if m:
            jours = int(m.group(1)) * (7 if "semaine" in m.group(2) else 1)
        evts, err = connecteurs.agenda_evenements(jours)
        return ([("outil", {"nom": "lire_agenda", "ok": not err})],
                err or _resume_agenda(evts, jours))
    if "instagram" in t and _contient(t, ("profil", "statistique", "abonnes", "abonnés", "stats")):
        try:
            data, err = instagram.profil()
        except Exception as e:
            err, data = str(e), None
        if err:
            return [("outil", {"nom": "instagram_profil", "ok": False})], err
        texte_reponse = (f"**@{data.get('username')}** — {data.get('followers_count', 0)} abonnés, "
                         f"{data.get('media_count', 0)} publications, "
                         f"{data.get('follows_count', 0)} abonnements."
                         + ("\n" + data.get("biography", "").strip() if data.get("biography") else ""))
        return [("outil", {"nom": "instagram_profil", "ok": True})], texte_reponse
    m = re.search(r"(?:ouvre|ouvrir|lance)\s+(?:l'|la\s+|le\s+)?([a-zéèêàç]+)", t)
    if m:
        nom = m.group(1)
        if nom in LIENS_APPS or nom in ("tel", "sms", "appel", "appelle", "mail"):
            lien, message = _lien_app(nom, "")
            if lien:
                return ([("outil", {"nom": "ouvrir_app", "ok": True}),
                         ("ouvrir", {"url": lien, "texte": message})], message)
            return [("outil", {"nom": "ouvrir_app", "ok": False})], message
    return None, None


def repondre(messages, system, mode="auto", modele=None, reflexion="equilibre", profil="general"):
    """Genere des evenements ('outil', 'ouvrir', 'lien', 'delta', 'stats').

    Ne leve jamais : en cas d'echec on retombe sur une reponse normale.
    """
    debut = time.time()
    dernier = ""
    for m in reversed(messages or []):
        if m.get("role") == "user":
            dernier = m.get("content") or ""
            break

    try:
        direct, texte_direct = _executer_direct(dernier)
    except Exception:
        direct, texte_direct = None, None
    if direct is not None:
        for ev in direct:
            yield ev
        for morceau in re.split(r"(?<=[.!?])\s+", texte_direct):
            if morceau:
                yield ("delta", morceau + " ")
        yield ("stats", {"total": round(time.time() - debut, 2), "premier": 0, "reflexion": None,
                         "tokens": 0, "tok_s": 0, "chargement": 0, "outils": True})
        return

    historique = list(messages)
    for _ in range(MAX_TOURS):
        appels = _appel_outils(historique, system, mode, modele)
        if not appels:
            break
        for appel in appels:
            fonction = (appel.get("function") or {})
            nom = fonction.get("name") or ""
            try:
                args = json.loads(fonction.get("arguments") or "{}")
            except Exception:
                args = {}
            resultat, evenement = executer(nom, args)
            yield ("outil", {"nom": nom, "ok": '"erreur"' not in resultat})
            if evenement:
                yield (evenement.pop("type"), evenement)
            historique.append({"role": "assistant", "content": "",
                               "tool_calls": [{"id": appel.get("id") or nom,
                                               "type": "function",
                                               "function": {"name": nom,
                                                            "arguments": fonction.get("arguments") or "{}"}}]})
            historique.append({"role": "tool", "tool_call_id": appel.get("id") or nom,
                               "content": resultat[:4000]})

    # Reponse finale en flux (avec les resultats d'outils dans le contexte)
    for evenement in llm.chat_stream(historique, system, mode=mode, modele=modele,
                                     reflexion=reflexion, profil=profil):
        yield evenement
