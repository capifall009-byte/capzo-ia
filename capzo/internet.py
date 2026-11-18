# -*- coding: utf-8 -*-
"""Acces Internet pour Capzo IA : recherche DuckDuckGo + lecture de pages.

Aucune cle API : DuckDuckGo HTML est gratuit et sans limite stricte.
"""
import html as _html
import re
import urllib.parse
import urllib.request

TIMEOUT = 25
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def _nettoyer_html(texte):
    texte = re.sub(r"<script[^>]*>.*?</script>", " ", texte, flags=re.S | re.I)
    texte = re.sub(r"<style[^>]*>.*?</style>", " ", texte, flags=re.S | re.I)
    texte = re.sub(r"<[^>]+>", " ", texte)
    texte = _html.unescape(texte)
    texte = re.sub(r"\s+", " ", texte).strip()
    return texte


def rechercher(requete, nombre=6):
    """Recherche DuckDuckGo. Retourne (liste, erreur)."""
    requete = (requete or "").strip()
    if not requete:
        return [], "Requete vide."
    nombre = max(1, min(int(nombre or 6), 12))
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(requete)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            page = r.read().decode("utf-8", "replace")
    except Exception as e:
        return [], "Recherche impossible : " + str(e)[:160]

    resultats = []
    # blocs de resultats
    blocs = re.findall(
        r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?'
        r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
        page, re.S | re.I)
    for lien, titre, extrait in blocs:
        titre = _nettoyer_html(titre)
        extrait = _nettoyer_html(extrait)
        # DuckDuckGo renvoie parfois un redirect /l/?uddg=...
        m = re.search(r"uddg=([^&]+)", lien)
        if m:
            lien = urllib.parse.unquote(m.group(1))
        if not titre:
            continue
        resultats.append({"titre": titre, "url": lien, "extrait": extrait[:260]})
        if len(resultats) >= nombre:
            break

    if not resultats:
        # fallback : liens bruts
        for m in re.finditer(r'<a[^>]*href="(https?://[^"]+)"[^>]*>([^<]{5,120})</a>', page):
            resultats.append({"titre": _nettoyer_html(m.group(2)), "url": m.group(1), "extrait": ""})
            if len(resultats) >= nombre:
                break
    return resultats, None


MOTS_EXPLICITES = (
    "sur internet", "sur le web", "cherche sur", "recherche sur", "va voir sur",
    "regarde sur internet", "d'apres internet", "d'après internet", "google",
)

MOTS_TEMPORELS = (
    "aujourd'hui", "aujourd hui", "actuellement", "en ce moment", "maintenant",
    "cette annee", "cette année", "cette semaine", "ce mois", "hier", "demain",
    "derniere", "dernière", "dernier", "derniers", "recente", "récente", "recent",
    "récent", "nouveau", "nouvelle", "nouveaute", "nouveauté", "2025", "2026",
    "2027", "prochain", "prochaine", "a venir", "à venir",
)

MOTS_INFO = (
    "meteo", "météo", "prix", "cout", "coût", "combien coute", "combien coûte",
    "tarif", "taux de change", "bourse", "cours de l'action", "score", "resultat du match",
    "résultat du match", "classement", "election", "élection", "president", "président",
    "qui est le", "qui est la", "sortie de", "quand sort", "date de sortie",
    "actualite", "actualité", "les news", "info du jour", "trafic", "greve", "grève",
    "bourse", "bitcoin", "crypto", "dollar", "euro", "temperature", "seisme", "séisme",
)


def faut_chercher(texte):
    """Devine si la question demande des informations fraiches du web."""
    t = (texte or "").lower()
    if not t or len(t) > 500:
        return False
    if any(m in t for m in MOTS_EXPLICITES):
        return True
    if any(m in t for m in MOTS_INFO):
        return True
    temporel = any(m in t for m in MOTS_TEMPORELS)
    interrogatif = any(m in t for m in ("quel", "quelle", "quels", "quelles", "qui",
                                        "quand", "combien", "ou ", "où "))
    return temporel and interrogatif


def apercu(requete, nombre=5, max_chars=1800):
    """Recherche web + resume compact et date, pret a etre injecte dans le prompt."""
    import time as _time
    resultats, erreur = rechercher(requete, nombre)
    if erreur or not resultats:
        return ""
    lignes = ["=== INFORMATIONS WEB EN DIRECT ===",
              "Date du jour : " + _time.strftime("%d/%m/%Y"),
              "Question : " + requete[:200],
              "Sources trouvees (appuie-toi dessus et cite les liens) :"]
    for i, r in enumerate(resultats, 1):
        lignes.append(f"[{i}] {r.get('titre', '')[:120]} — {r.get('extrait', '')[:230]} "
                      f"({r.get('url', '')[:150]})")
    texte = "\n".join(lignes)
    return texte[:max_chars] + ("\n(Cite tes sources avec leur lien.)" if len(texte) > 200 else "")


def lire_page(url, max_chars=5000):
    """Telecharge une page et renvoie son texte lisible."""
    url = (url or "").strip()
    if not url.startswith(("http://", "https://")):
        return None, "URL invalide."
    try:
        try:
            import certifi, ssl as _ssl
            ctx = _ssl.create_default_context(cafile=certifi.where())
        except Exception:
            import ssl as _ssl
            ctx = _ssl._create_unverified_context()
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as r:
            data = r.read()
            ctype = r.headers.get("Content-Type", "")
            enc = "utf-8"
            m = re.search(r"charset=([\w-]+)", ctype, re.I)
            if m:
                enc = m.group(1)
            texte = data.decode(enc, "replace")
    except Exception as e:
        return None, "Lecture impossible : " + str(e)[:160]
    texte = _nettoyer_html(texte)
    if not texte:
        return None, "Page vide ou illisible."
    return texte[:max_chars], None
