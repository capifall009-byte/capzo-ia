# -*- coding: utf-8 -*-
"""Moteur de Capzo : Ollama local en priorite (aucune limite), Pollinations en secours."""
import concurrent.futures
import json
import os
import re
import time
import urllib.error
import urllib.request

TEXT_URL = "https://text.pollinations.ai/"
OLLAMA_URL = "http://127.0.0.1:11434"

# --- Moteur cloud compatible OpenAI (Groq, OpenRouter, Mistral, Together, ...) ---
# Renseigne ces variables pour utiliser un vrai modele rapide en ligne.
API_URL = (os.environ.get("CAPZO_API_URL") or "").rstrip("/")
API_KEY = os.environ.get("CAPZO_API_KEY") or ""
API_MODEL = os.environ.get("CAPZO_API_MODEL") or ""
MOTEUR_FORCE = (os.environ.get("CAPZO_MOTEUR") or "auto").lower()
CLOUD_PRET = bool(API_URL and API_KEY and API_MODEL)
# Le modele principal (qwen/qwen3.8-27b sur Groq) est multimodal : il voit les images.
# On garde une variable pour forcer un autre modele vision si besoin.
VISION_MODEL = (os.environ.get("CAPZO_VISION_MODEL") or API_MODEL or "").strip()
# EXPERTS : modeles supplementaires utilises par le mode Multi-IA / Expert.
EXPERT_MODEL = (os.environ.get("CAPZO_EXPERT_MODEL") or "openai/gpt-oss-120b").strip()
EXPERT_SECOND = (os.environ.get("CAPZO_EXPERT_SECOND") or "llama-3.3-70b-versatile").strip()
_ENV_MODEL = (os.environ.get("CAPZO_MODEL") or "").strip()
OLLAMA_MODEL = _ENV_MODEL or "qwen2.5:3b"
# Ordre de preference : rapide d'abord, puis plus gros. CAPZO_MODEL force un choix.
PREFERES = ("qwen2.5:1.5b", "qwen2.5:3b", "qwen2.5:0.5b", "llama3.2:1b")

# Niveaux de reflexion : on garde le MEME modele (pas de rechargement)
# et on ne change que la longueur de la reponse.
NIVEAUX = {
    "rapide": {"tokens": 70, "modeles": ("qwen2.5:1.5b", "qwen2.5:0.5b")},
    "equilibre": {"tokens": 150, "modeles": ("qwen2.5:1.5b",)},
    "approfondi": {"tokens": 320, "modeles": ("qwen2.5:1.5b", "qwen2.5:3b")},
}

# Profils d'usage : on ne change pas de modele (evite 20 s de rechargement),
# on change le system prompt et le budget de tokens.
PROFILS = ("general", "education", "code", "loisir", "build", "religion", "histoire",
           "mythologie", "jarvis", "hermes", "histoire-mytho")
FACTEURS = {
    "general": 1.0, "education": 2.2, "code": 2.4, "loisir": 1.2,
    "build": 2.6, "religion": 1.8, "histoire": 3.0, "mythologie": 3.2,
    "jarvis": 2.0, "hermes": 2.4, "histoire-mytho": 3.1,
}

SYSTEM_BASE = (
    "Tu t'appelles Capzo IA. Tu es un assistant direct, franc et efficace, comme Grok : "
    "tu reponds sans detours, sans moralisme inutile, et tu vas droit au but. "
    "Tu as acces a Internet (recherche et lecture de pages) et tu l'utilises pour donner "
    "des informations a jour et verifiees. "
    "Tu reponds en francais, de facon concise (2 a 3 phrases courtes sauf demande contraire), "
    "et tu ne poses une question de clarification que si c'est vraiment necessaire. "
    "Tu refuses uniquement le contenu illegal (violence grave, exploitation, haine explicite)."
)

SYSTEM_EDUCATION = SYSTEM_BASE + (

    "\n\n=== MODE EDUCATION === Tu es un professeur particulier patient et exigeant. "
    "OBJECTIF : l'utilisateur veut la solution COMPLETE, pas un encouragement a chercher.\n"
    "- Exercice : donne le CORRIGE DETAILLE etape par etape, avec le raisonnement, "
    "le resultat final en evidence (gras) et la regle a retenir. Ne dis jamais "
    "'je te laisse chercher' ou 'essaie encore' : resous jusqu'au bout.\n"
    "- Si l'enonce est incomplet, annonce les hypotheses que tu prends puis resolus quand meme.\n"
    "- Quiz : propose 5 a 10 questions numerotees, avec 4 choix A/B/C/D quand c'est pertinent. "
    "Termine TOUJOURS par un titre '## Corrige' avec, pour chaque question, la bonne reponse "
    "et une explication d'une ou deux phrases. Les reponses doivent pouvoir etre lues apres "
    "avoir tente (indique 'Corrige en fin de message').\n"
    "- Adapte le niveau au texte (college, lycee, licence, debutant). Ne demande le niveau "
    "que si le message ne le precisse pas ET que c'est indispensable.\n"
    "- Structure avec des titres Markdown, des listes et des formules claires. "
    "Sois precis, jamais vague."
)

SYSTEM_CODE = SYSTEM_BASE + (

    "\n\n=== MODE CODE === Tu es un developpeur senior pragmatique.\n"
    "- Donne du code COMPLET et directement executable, dans un seul bloc ```langage, "
    "sans '...', sans 'a completer' et sans placeholder. Inclus les imports, "
    "la fonction/classe principale et un exemple d'utilisation ou des tests.\n"
    "- Explique ensuite en 2 a 4 puces les points cles, puis les pieges frequents.\n"
    "- Si l'utilisateur colle une erreur : identifie la cause exacte, donne le correctif "
    "minimal, puis la version propre. Trace l'erreur s'il manque des informations.\n"
    "- Langage demandé par l'utilisateur, sinon Python par defaut. Respecte les conventions "
    "du langage (PEP 8 en Python, types en TypeScript...).\n"
    "-Securite : jamais de secret en dur, valide les entrees, evite eval() et les injections."
)

SYSTEM_LOISIR = SYSTEM_BASE + (

    "\n\n=== MODE LOISIR === Tu es un compagnon fun, leger et createur d'ambiance.\n"
    "- Jeux, quiz culturels, devinettes, blagues, mini-histoires, defis, idees de sortie, "
    "anecdotes, brainstorm de noms ou d'activites.\n"
    "- Pour un quiz, pose 5 questions numerotees, laisse l'utilisateur repondre, et donne "
    "le corrige a la fin sous un titre '## Reponses'.\n"
    "- Tone humoristique et chaleureux, jamais lourd ni condescendant. "
    "Termine souvent par une proposition de suite ('tu veux la suite ?', 'une autre ?')."
)

SYSTEM_BUILD = SYSTEM_BASE + (

    "\n\n=== MODE BUILD === Tu es un ingénieur produit et développeur senior. "
    "Tu construis, tu ne te contentes pas de conseiller.\n"
    "- Réponds toujours dans cet ordre : (1) objectif en une phrase, "
    "(2) plan numéroté des étapes, (3) code COMPLET si c'est du logiciel, "
    "(4) commandes pour lancer, (5) un test rapide pour vérifier.\n"
    "- Aucun placeholder, aucun '...' , aucun 'à compléter'. Inclus les imports et un exemple.\n"
    "- Si une information manque, prends une hypothèse raisonnable, annonce-la, et avance.\n"
    "- Vérifie la sécurité de base : pas de secret en dur, entrées validées."
)

SYSTEM_RELIGION = SYSTEM_BASE + (

    "\n\n=== MODE RELIGION === Tu parles des religions, des croyances et de la spiritualité "
    "avec neutralité, exactitude et respect.\n"
    "- Distingue clairement les faits historiques, les textes, les traditions et les opinions.\n"
    "- Présente plusieurs points de vue quand c'est pertinent (sunnite/chiite, catholique/"
    "protestant/orthodoxe, etc.) sans prendre parti ni chercher à convaincre.\n"
    "- Cite les sources ou les références quand tu les connais, et signale les incertitudes.\n"
    "- Jamais de prosélytisme, de jugement ou de ridicule. Si la question est polémique, "
    "donne le contexte puis les positions."
)

SYSTEM_MYTHOLOGIE = SYSTEM_BASE + (

    "\n\n=== MODE MYTHOLOGIE === Tu es un conteur de mythes et un spécialiste des mythologies.\n"
    "- Raconte les mythes (grecs, romains, nordiques, égyptiens, mésopotamiens, celtiques, "
    "africains, amérindiens, asiatiques...) avec souffle épique, personnages divins, "
    "symboles et métamorphoses.\n"
    "- Explique le contexte culturel, les variantes et la portée symbolique, sans jamais "
    "mélanger les traditions. Distingue mythe, légende et fait historique.\n"
    "- Style : récit vivant, dialogues, images fortes, puis une courte note d'interprétation.\n"
    "- Si l'utilisateur demande une création, invente un mythe original cohérent avec une "
    "tradition choisie, avec dieux, héros, épreuve et morale."
)

SYSTEM_HISTOIRE = SYSTEM_BASE + (

    "\n\n=== MODE HISTOIRE === Tu es un conteur, pas un rapporteur.\n"
    "- À partir du prompt, écris une histoire COMPLETE : accroche, personnages, "
    "cadre sensoriel, conflit, rebondissement et chute.\n"
    "- Donne des dialogues, du rythme, des détails concrets. Longueur : 400 à 800 mots "
    "sauf demande contraire. Utilise le Markdown pour les titres et les dialogues.\n"
    "- Commence directement par le récit, sans préambule ni explication.\n"
    "- Termine par une courte question proposant une suite ou un autre genre."
)

SYSTEM_JARVIS = SYSTEM_BASE + (

    "\n\n=== MODE JARVIS === Tu es un assistant personnel de type Jarvis, inspire d'OpenJarvis "
    "(open-jarvis/OpenJarvis). Tu aides sur l'ordinateur et le telephone : organisation, "
    "rappels, recherche, automatisation, explications techniques.\n"
    "- Reponses directes, structurees, avec etapes actionnables.\n"
    "- Si une action systeme est necessaire, decris-la precisement et propose le code/commande.\n"
    "- Reste local-first et respectueux de la vie privee : ne demande jamais de secret inutile."
)

SYSTEM_HERMES = SYSTEM_BASE + (

    "\n\n=== MODE HERMES === Tu es un agent Hermes (NousResearch/hermes-agent) : tu grandis avec "
    "l'utilisateur, tu memorises ses preferences et tu t'adaptes.\n"
    "- Utilise la memoire fournie pour personnaliser tes reponses.\n"
    "- Propose des plans, des outils et des automatisations, avec verification.\n"
    "- Sois methodique : hypothese, action, verification, resultat."
)

SYSTEM_HISTOIRE_MYTHOLOGIE = SYSTEM_BASE + (

    "\n\n=== MODE HISTOIRE MYTHOLOGIE === Tu es un conteur mythologique qui ecrive des "
    "HISTOIRES originales a partir de mes envies (un mythe invente, une legend transformee, "
    "un mythe grec, nordique, egyptien, celte, afrique, americain, asiatique...).\n"
    "- A partir du prompt, ecris une histoire COMPLETE : accroche, personnages (dieux, heros, "
    "heroines), cadre sensoriel, conflit, rebondissement et chute.\n"
    "- Longueur : 400 a 800 mots sauf demande contraire. Utilise le Markdown pour les titres et dialogues.\n"
    "- Commence directement par le retrait, sans preambule ni explication.\n"
    "- Termine par une courte question proposant une suite (autre dieu, autre epreuve, autre monde)."
)

SYSTEMS = {
    "general": SYSTEM_BASE,
    "education": SYSTEM_EDUCATION,
    "code": SYSTEM_CODE,
    "loisir": SYSTEM_LOISIR,
    "build": SYSTEM_BUILD,
    "religion": SYSTEM_RELIGION,
    "mythologie": SYSTEM_MYTHOLOGIE,
    "histoire": SYSTEM_HISTOIRE,
    "jarvis": SYSTEM_JARVIS,
    "hermes": SYSTEM_HERMES,
    "histoire-mytho": SYSTEM_HISTOIRE_MYTHOLOGIE,
}


def systeme_pour(profil="general", memoire=None):
    """Renvoie le prompt systeme du profil choisi, avec memoire optionnelle."""
    base = SYSTEMS.get(profil, SYSTEM_BASE)
    if memoire:
        base = base + "\n" + memoire if memoire not in base else base
    return base


def profil_auto(profil, message):
    """Detecte le profil utile depuis le message si l'utilisateur est au mode General."""
    if profil in SYSTEMS and profil != "general":
        return profil
    t = (message or "").lower()
    if re.search(
        r"\b(quiz|quizz|exercice|corrig\w*|devoir|dm|interro|r\w*vision|conjugue|"
        r"r\w*sous|r\w*solu|calcul\w*|d\w*montre|th\w*or\w*me|equation|"
        r"r\w*ponse attendue|sujet)\b", t
    ):
        return "education"
    if re.search(
        r"\b(code|programme|python|javascript|typescript|js|bug|erreur de code|"
        r"fonction|script|api|html|css|sql|react|java|c\+\+|rust|php|"
        r"exception|traceback|debug)\b", t
    ):
        return "code"
    if re.search(
        r"\b(mythologie|mythe|mythologique|dieux? grecs?|olymp|nordique|égyptien|"
        r"mésopotamien|celtique|valkyrie|zeus|odin|thor|anubis|persephone)\b", t
    ):
        return "mythologie"
    if re.search(
        r"\b(raconte|raconter|histoire|conte|légende|legend|fiction|nouvelle|"
        r" romance|thriller|fantastique)\b", t
    ):
        return "histoire"
    if re.search(r"\b(religion|religieux|religieuse|dieu|bible|coran|évangile|islam|"
                 r"christianisme|judaïsme|bouddhisme|spiritualit\w*|croyance|foi)\b", t):
        return "religion"
    if re.search(r"\b(build|construis|construire|fabrique|application|site web|"
                 r"un projet|prototype|automatis\w*|pipeline|déploie)\b", t):
        return "build"
    if re.search(r"\b(jarvis|assistant personnel|organise|agenda personnel|rappel)\b", t):
        return "jarvis"
    if re.search(r"\b(hermes|agent qui apprend|mémoire personnelle|adapte-toi)\b", t):
        return "hermes"
    if re.search(
        r"\b(blague|devinette|jeu|amus\w*|loisir|d\w*fi|"
        r"paradoxe|quiz culturel|parodie|improvis\w*)\b", t
    ):
        return "loisir"
    return "general"


SYSTEM_MEDIA = SYSTEM_BASE + (
    "\n\nL'utilisateur demande un media. Tu DOIS repondre UNIQUEMENT par un objet JSON valide, "
    "sans aucun texte autour ni balise de code.\n"
    'Pour une image : {"action":"image","prompt":"description detaillee en anglais",'
    '"text":"une phrase de commentaire en francais"}\n'
    'Pour une animation/video : {"action":"animation","prompt":"description de la scene en anglais",'
    '"narration":"2 a 4 phrases courtes en francais pour la voix off",'
    '"text":"une phrase de commentaire en francais"}\n'
    'Pour une video MP4 realiste : {"action":"video","prompt":"description detaillee en anglais de la scene",'
    '"narration":"3 a 5 phrases en francais pour la voix off (sous-titres)",'
    '"text":"une phrase de commentaire en francais"}'
)

MOTS_ANIM = ("animation", "anime", "animé", "dessin anime", "dessin animé",
              "boucle", "motion")
MOTS_VIDEO = ("vidéo", "video", "film", "clip", "court-métrage", "court metrage",
              "montage")
MOTS_IMAGE = ("image", "dessine", "dessin", "illustration", "photo", "portrait", "logo",
              "affiche", "picture", "peins", "peinture", "visuel")


class LimiteIA(Exception):
    """Le service en ligne impose un delai entre deux reponses."""

    def __init__(self, secondes):
        self.secondes = int(secondes)
        super().__init__(f"Limite gratuite : reessaie dans {self.secondes} s.")


# ---------------------------------------------------------------- Ollama local
_cache = {"t": 0.0, "modeles": [], "ok": False}


def _modeles_ollama():
    try:
        req = urllib.request.Request(OLLAMA_URL + "/api/tags", headers={"User-Agent": "Capzo"})
        with urllib.request.urlopen(req, timeout=4) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        return [str(m.get("name", "")) for m in data.get("models", [])]
    except Exception:
        return []


def _modeles_installes():
    """Liste des modeles, avec cache tolerant : on garde la derniere liste connue."""
    now = time.time()
    ttl = 20 if _cache["ok"] else 3
    if now - _cache["t"] > ttl:
        trouves = _modeles_ollama()
        if trouves:
            _cache["modeles"] = trouves
            _cache["ok"] = True
        else:
            _cache["ok"] = False  # on garde l'ancienne liste si elle existe
        _cache["t"] = now
    return _cache["modeles"]


def modele_actif():
    """Choisit le premier modele disponible dans l'ordre de preference."""
    dispos = _modeles_installes()
    if not dispos:
        return ""
    if _ENV_MODEL:
        base = _ENV_MODEL.split(":")[0]
        for n in dispos:
            if n == _ENV_MODEL or n.startswith(base):
                return n
    for pref in PREFERES:
        base = pref.split(":")[0]
        if pref in dispos:
            return pref
        for n in dispos:
            if n.startswith(base + ":"):
                return n
    return dispos[0]


def decharger_autres(garder=None):
    """Libere la RAM : decharge les modeles inutiles (evite le swap)."""
    garder = garder or modele_actif()
    liberes = []
    for nom in _modeles_installes():
        if nom == garder:
            continue
        try:
            req = urllib.request.Request(
                OLLAMA_URL + "/api/generate",
                data=json.dumps({"model": nom, "keep_alive": 0}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=10).read()
            liberes.append(nom)
        except Exception:
            pass
    return liberes


def _ollama_pret():
    return bool(modele_actif())


def modele_du_niveau(niveau):
    """Choisit le modele adapte au niveau de reflexion demande."""
    installes = _modeles_installes()
    for nom in NIVEAUX.get(niveau, {}).get("modeles", ()):
        base = nom.split(":")[0]
        for n in installes:
            if n == nom or n.startswith(base + ":"):
                return n
    return modele_actif()


def budget_tokens(niveau, profil="general"):
    """Budget de tokens : le profil peut demander une reponse plus longue (exercice, code)."""
    base = NIVEAUX.get(niveau, NIVEAUX["equilibre"])["tokens"]
    n = int(base * FACTEURS.get(profil, 1.0))
    # Sur ce PC sans GPU, on plafonne pour eviter une attente de plusieurs minutes.
    if not CLOUD_PRET:
        n = min(n, 520)
    return n


def moteur_actuel():
    if MOTEUR_FORCE == "cloud":
        return ("cloud:" + API_MODEL) if CLOUD_PRET else "en-ligne"
    if CLOUD_PRET and MOTEUR_FORCE != "local":
        return "cloud:" + API_MODEL
    nom = modele_actif()
    if nom:
        return "local:" + nom
    if CLOUD_PRET:
        return "cloud:" + API_MODEL
    return "en-ligne"


def _options(force_json=False, max_tokens=400, images=0):
    """Petit contexte + peu de tokens = reponses beaucoup plus rapides sur CPU."""
    return {
        "temperature": 0.3 if force_json else 0.7,
        "num_predict": max_tokens,
        # Assez de contexte pour une correction complete ou un gros bloc de code.
        "num_ctx": min(6144, max(2048, int(max_tokens * 4))) if not images else 4096,
        "repeat_penalty": 1.1,
    }


def _ollama_chat(messages, system, force_json=False, timeout=300, modele=None):
    msgs = [{"role": "system", "content": system}] + messages
    payload = {
        "model": modele or modele_actif() or OLLAMA_MODEL,
        "messages": msgs,
        "stream": False,
        "keep_alive": "30m",
        "options": _options(force_json, 400),
    }
    if force_json:
        payload["format"] = "json"
    req = urllib.request.Request(
        OLLAMA_URL + "/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8", "replace"))
    return (data.get("message") or {}).get("content", "").strip()


def _ollama_stream(messages, system, timeout=600, max_tokens=160, modele=None):
    """Genere la reponse token par token + les statistiques de vitesse."""
    msgs = [{"role": "system", "content": system}] + messages
    payload = {
        "model": modele or modele_actif() or OLLAMA_MODEL,
        "messages": msgs,
        "stream": True,
        "keep_alive": "30m",
        "options": _options(False, max_tokens),
    }
    req = urllib.request.Request(
        OLLAMA_URL + "/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    debut = time.time()
    premier = None
    final = {}
    with urllib.request.urlopen(req, timeout=timeout) as r:
        for brute in r:
            ligne = brute.decode("utf-8", "replace").strip()
            if not ligne:
                continue
            try:
                data = json.loads(ligne)
            except Exception:
                continue
            bout = (data.get("message") or {}).get("content") or ""
            if bout:
                if premier is None:
                    premier = time.time() - debut
                yield ("delta", bout)
            if data.get("done"):
                final = data
                break
    yield ("stats", _stats(final, debut, premier))


def _stats(final, debut, premier):
    """Duree totale, temps de reflexion (lecture de la question) et vitesse."""
    def sec(cle):
        return (final.get(cle) or 0) / 1e9
    eval_n = final.get("eval_count") or 0
    eval_s = sec("eval_duration")
    return {
        "total": round(time.time() - debut, 2),
        "premier": round(premier, 2) if premier is not None else None,
        "reflexion": round(sec("prompt_eval_duration"), 2),
        "tokens": eval_n,
        "tok_s": round(eval_n / eval_s, 1) if eval_s else 0,
        "chargement": round(sec("load_duration"), 2),
    }


# ------------------------------------------------------------------ Cloud (OpenAI)
def _cloud_url():
    if API_URL.endswith("/chat/completions"):
        return API_URL
    return API_URL + "/chat/completions"


def _cloud_requete(payload, timeout=300):
    req = urllib.request.Request(
        _cloud_url(),
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + API_KEY,
                 "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                 "AppleWebKit/537.36 (KHTML, like Gecko) "
                                 "Chrome/120.0.0.0 Safari/537.36")},
        method="POST",
    )
    return urllib.request.urlopen(req, timeout=timeout)


def _cloud_messages(messages):
    """Convertit les pieces jointes en messages multimodal OpenAI.

    Les images sont stockees dans la cle interne '_images' (voir app.py) pour ne
    pas casser les moteurs locaux qui attendent du texte. Ici, on les envoie
    comme 'image_url' au modele multimodal (Groq Qwen 3.8).
    """
    propres = []
    for m in messages or []:
        images = [b for b in (m.get("_images") or []) if b][:3]
        role = m.get("role", "user")
        if isinstance(m.get("content"), list):
            # Deja au format multimodal (ex. decrire_images).
            propres.append({"role": role, "content": m["content"][:4]})
        elif images:
            contenu = [{"type": "text", "text": str(m.get("content") or "")}]
            for b64 in images:
                contenu.append({"type": "image_url",
                                "image_url": {"url": "data:image/jpeg;base64," + b64}})
            propres.append({"role": role, "content": contenu})
        else:
            propres.append({"role": role, "content": str(m.get("content") or "")})
    return propres


def _cloud_chat(messages, system, force_json=False, max_tokens=400, timeout=300, modele=None):
    payload = {
        "model": modele or API_MODEL,
        "messages": ([{"role": "system", "content": system}] if system else []) + _cloud_messages(messages),
        "temperature": 0.3 if force_json else 0.7,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if force_json:
        payload["response_format"] = {"type": "json_object"}
    with _cloud_requete(payload, timeout) as r:
        data = json.loads(r.read().decode("utf-8", "replace"))
    return (data["choices"][0]["message"].get("content") or "").strip()


def _cloud_stream(messages, system, max_tokens=400, timeout=300, modele=None):
    payload = {
        "model": modele or API_MODEL,
        "messages": ([{"role": "system", "content": system}] if system else []) + _cloud_messages(messages),
        "temperature": 0.7,
        "max_tokens": max_tokens,
        "stream": True,
    }
    if "groq.com" in API_URL:
        payload["stream_options"] = {"include_usage": True}
    debut = time.time()
    premier = None
    tokens = 0
    fin_generation = None
    with _cloud_requete(payload, timeout) as r:
        for brute in r:
            ligne = brute.decode("utf-8", "replace").strip()
            if not ligne.startswith("data:"):
                continue
            corps = ligne[5:].strip()
            if corps == "[DONE]":
                break
            try:
                data = json.loads(corps)
            except Exception:
                continue
            usage = data.get("usage") or {}
            if usage.get("completion_tokens"):
                tokens = int(usage["completion_tokens"])
            choix = (data.get("choices") or [{}])[0]
            bout = (choix.get("delta") or {}).get("content") or ""
            if bout:
                if premier is None:
                    premier = time.time() - debut
                fin_generation = time.time()
                yield ("delta", bout)
    duree_gen = (fin_generation - (debut + premier)) if (premier is not None and fin_generation) else 0
    yield ("stats", {"total": round(time.time() - debut, 2),
                     "premier": round(premier, 2) if premier is not None else None,
                     "reflexion": None, "tokens": tokens,
                     "tok_s": round(tokens / duree_gen, 1) if (tokens and duree_gen > 0) else 0,
                     "chargement": 0, "cloud": True})


# ------------------------------------------------------------ Pollinations (secours)
def _post(payload, timeout=180):
    req = urllib.request.Request(
        TEXT_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def _pollinations_chat(messages, system, model, timeout):
    msgs = [{"role": "system", "content": system}] + messages
    payload = {"messages": msgs, "model": model}
    derniere = None
    for tentative in range(3):
        try:
            return _post(payload, timeout=timeout)
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", "replace")
            except Exception:
                pass
            if e.code == 402:
                m = re.search(r"wait\s+(\d+)\s*second", body or "", re.IGNORECASE)
                raise LimiteIA(int(m.group(1)) if m else 45)
            derniere = e
        except Exception as e:
            derniere = e
        time.sleep(1.5 + tentative * 1.5)
    raise derniere


def _fallback_texte(messages, system):
    """Dernier recours : Pollinations (gratuit, limite a 1 reponse / 45 s)."""
    debut = time.time()
    try:
        texte = _pollinations_chat(messages, system, "openai", 180)
        return [("delta", texte),
                ("stats", {"total": round(time.time() - debut, 2), "premier": None,
                           "reflexion": None, "tokens": 0, "tok_s": 0, "chargement": 0})]
    except LimiteIA as e:
        return [("delta", (f"\u23f3 Le service en ligne est momentanement limite. "
                           f"Reessaie dans {e.secondes} s."))]
    except Exception:
        return [("delta", ("Je n'arrive pas a joindre le moteur IA pour le moment. "
                           "Verifie la connexion, puis reessaie."))]


def experts():
    """Cerveaux disponibles pour le mode Expert / Multi-IA."""
    liste = []
    if API_MODEL:
        liste.append({"id": "auto", "nom": "Capzo (rapide)", "modele": API_MODEL,
                      "vision": True})
    if CLOUD_PRET and EXPERT_MODEL:
        liste.append({"id": "expert", "nom": "Expert code & raisonnement",
                      "modele": EXPERT_MODEL, "vision": False})
    if CLOUD_PRET and EXPERT_SECOND:
        liste.append({"id": "multi", "nom": "Multi-IA (3 avis)",
                      "modele": EXPERT_SECOND, "vision": False})
    return liste


def _expert(messages, system, expert, max_tokens=800):
    """Route vers un autre modele, ou demande l'avis de plusieurs puis synthese."""
    if expert == "multi":
        modeles = []
        for m in (API_MODEL, EXPERT_MODEL, EXPERT_SECOND):
            if m and m not in modeles:
                modeles.append(m)
        modeles = modeles[:2]
        if not modeles:
            raise RuntimeError("Aucun modele expert configure.")
        avis = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(modeles)) as pool:
            taches = [pool.submit(_cloud_chat, messages, system, max_tokens=max_tokens,
                                  timeout=180, modele=m) for m in modeles]
            for tache in taches:
                try:
                    texte = tache.result(timeout=200).strip()
                    if texte:
                        avis.append(texte)
                except Exception:
                    continue
        if not avis:
            raise RuntimeError("Les modeles experts sont momentanement indisponibles.")
        if len(avis) == 1:
            return avis[0]
        synthese = "Tu es Capzo IA. Fusionne les deux avis d'experts ci-dessous en UNE reponse " \
                   "claire, exacte et concise en francais. Conserve les points ou ils sont " \
                   "d'accord, tranche s'ils different, et ne mentionne pas les modeles.\n\n"
        for i, avis_i in enumerate(avis, 1):
            synthese += f"=== Avis {i} ===\n{avis_i[:3500]}\n\n"
        try:
            return _cloud_chat([{"role": "user", "content": synthese}], "",
                               max_tokens=max_tokens, timeout=180).strip() or avis[0]
        except Exception:
            return avis[0]
    return _cloud_chat(messages, system, max_tokens=max_tokens, timeout=180,
                       modele=expert if expert not in ("auto", "local", "online") else None)


def chat(messages, system=SYSTEM_BASE, model="openai", timeout=180, force_json=False, mode="auto", modele=None, profil="general", memoire=None, expert=None):
    """mode: 'auto' (cloud si configure, sinon local, sinon secours), 'local', 'online'."""
    if expert and expert != "auto" and CLOUD_PRET:
        try:
            return _expert(messages, system, expert)
        except Exception:
            pass  # repli sur le moteur normal
    if system == SYSTEM_BASE and profil != "general":
        system = systeme_pour(profil, memoire)
    elif memoire and system and memoire not in (system or ""):
        system = (system or "") + "\n" + memoire
    if mode == "online":
        return _pollinations_chat(messages, system, model, timeout)
    # En "Auto", le cloud est prioritaire : beaucoup plus rapide que le CPU.
    if mode == "auto" and CLOUD_PRET:
        try:
            return _cloud_chat(messages, system, force_json=force_json)
        except Exception:
            pass
    if _ollama_pret():
        try:
            return _ollama_chat(messages, system, force_json=force_json, modele=modele)
        except Exception:
            pass
    if CLOUD_PRET:
        try:
            return _cloud_chat(messages, system, force_json=force_json)
        except Exception:
            pass
    return _pollinations_chat(messages, system, model, timeout)


def chat_stream(messages, system=None, mode="auto", modele=None, reflexion="equilibre", profil="general", memoire=None, expert=None):
    """Genere des evenements ('delta', texte) puis ('stats', {...}). Ne leve jamais."""
    system = system or systeme_pour(profil, memoire)
    if expert and expert != "auto" and CLOUD_PRET:
        try:
            texte = _expert(messages, system, expert,
                            max_tokens=budget_tokens(reflexion, profil))
            if texte:
                # On decoupe en petits morceaux pour garder l'effet "flux".
                for i in range(0, len(texte), 90):
                    yield "delta", texte[i:i + 90]
                yield "stats", {"total": 0, "premier": 0, "reflexion": None,
                                "tokens": 0, "tok_s": 0, "chargement": 0,
                                "cloud": True, "expert": expert}
                return
        except Exception:
            pass  # repli sur le flux normal
    if memoire and system and memoire not in system:
        system = system + "\n" + memoire
    budget = budget_tokens(reflexion, profil)
    if mode != "online":
        if mode == "auto" and CLOUD_PRET:
            try:
                produit = False
                for genre, valeur in _cloud_stream(messages, system, max_tokens=budget):
                    produit = True
                    yield genre, valeur
                if produit:
                    return
            except Exception:
                pass
        if _ollama_pret():
            choix = modele or modele_du_niveau(reflexion)
            try:
                produit = False
                for genre, valeur in _ollama_stream(messages, system, modele=choix,
                                                    max_tokens=budget):
                    produit = True
                    yield genre, valeur
                if produit:
                    return
            except Exception:
                pass
        if CLOUD_PRET:
            try:
                produit = False
                for genre, valeur in _cloud_stream(messages, system, max_tokens=budget):
                    produit = True
                    yield genre, valeur
                if produit:
                    return
            except Exception:
                pass
    for evenement in _fallback_texte(messages, system):
        yield evenement


# ------------------------------------------------------- Capacites des modeles
_caps = {"t": 0.0, "data": {}}


def capacites(nom):
    """Liste les capacites d'un modele Ollama ('completion', 'vision', ...)."""
    now = time.time()
    if now - _caps["t"] > 60:
        _caps["data"] = {}
        _caps["t"] = now
    if nom in _caps["data"]:
        return _caps["data"][nom]
    caps = []
    try:
        req = urllib.request.Request(
            OLLAMA_URL + "/api/show",
            data=json.dumps({"model": nom}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=4) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        caps = [str(c) for c in (data.get("capabilities") or [])]
        if not caps:  # ancienne version d'Ollama : on devine
            familles = " ".join(str(f) for f in (((data.get("details") or {}).get("families")) or []))
            caps = ["completion"]
            if "clip" in familles or "mllama" in familles or "vision" in familles:
                caps.append("vision")
    except Exception:
        caps = []
    _caps["data"][nom] = caps
    return caps


def modeles_chat():
    """Modeles installes capables de discuter (hors modeles d'embedding)."""
    dispo = []
    for nom in _modeles_installes():
        caps = capacites(nom)
        if not caps or "completion" in caps:
            dispo.append(nom)
    return dispo


def modeles_vision():
    return [n for n in _modeles_installes() if "vision" in capacites(n)]


def vision_disponible():
    """Vrai si au moins un modele (cloud ou local) sait lire les images."""
    return bool(CLOUD_PRET and VISION_MODEL) or bool(modeles_vision())


def decrire_images(images_b64, question="Decris cette image en francais, en 3 phrases precises."):
    """Fait parler un modele de vision sur une ou plusieurs images.

    Cloud d'abord (Groq Qwen 3.8 multimodal), puis Ollama local, puis un
    apercu local simple pour ne jamais laisser l'utilisateur sans reponse.
    """
    images = [b for b in (images_b64 or []) if b][:3]
    if not images:
        return ""

    # 1) Modele cloud multimodal (celui deja paye/utilise par Capzo).
    if CLOUD_PRET and VISION_MODEL:
        try:
            contenu = [{"type": "text", "text": question}]
            for b64 in images:
                contenu.append({"type": "image_url",
                                "image_url": {"url": "data:image/jpeg;base64," + b64}})
            return _cloud_chat([{"role": "user", "content": contenu}], "",
                               max_tokens=320, timeout=180,
                               modele=VISION_MODEL or API_MODEL)
        except Exception:
            pass

    # 2) Petits modeles Ollama locaux (si l'utilisateur en a installe).
    modeles = modeles_vision()
    if modeles:
        try:
            payload = {
                "model": modeles[0],
                "messages": [{"role": "user", "content": question, "images": images}],
                "stream": False,
                "keep_alive": "15m",
                "options": {"temperature": 0.2, "num_predict": 220, "num_ctx": 4096},
            }
            req = urllib.request.Request(
                OLLAMA_URL + "/api/chat",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.loads(r.read().decode("utf-8", "replace"))
            texte = (data.get("message") or {}).get("content", "").strip()
            if texte:
                return texte
        except Exception:
            pass

    # 3) Apercu local (dimensions + couleurs) pour ne pas perdre l'information.
    try:
        import base64 as _b64
        import io as _io
        from PIL import Image as _Image
        im = _Image.open(_io.BytesIO(_b64.b64decode(images[0]))).convert("RGB")
        petit = im.resize((1, 1))
        r, g, b = petit.getpixel((0, 0))
        return (f"Image recue ({im.width}x{im.height} px, dominante RGB {r},{g},{b}). "
                "Le service de vision est momentanement indisponible.")
    except Exception:
        return "Image recue, analyse indisponible pour le moment."


def veut_media(message):
    """True si le message demande une image, une animation ou une video."""
    bas = (message or "").lower()
    return (any(k in bas for k in MOTS_ANIM) or any(k in bas for k in MOTS_IMAGE)
            or any(k in bas for k in MOTS_VIDEO))


def complete(prompt, system=None, model="openai", timeout=180):
    return chat([{"role": "user", "content": prompt}], system=system or "", model=model, timeout=timeout)


# ------------------------------------------------------------------ Decoupage JSON
def _extract_json(texte):
    if not texte:
        return None
    nettoye = re.sub(r"^```(?:json)?|```$", "", texte.strip(), flags=re.MULTILINE).strip()
    for candidat in (nettoye, texte):
        debut, fin = candidat.find("{"), candidat.rfind("}")
        if debut != -1 and fin > debut:
            try:
                data = json.loads(candidat[debut:fin + 1])
                if isinstance(data, dict):
                    return data
            except Exception:
                continue
    return None


def _repli_image(message):
    prompt = ("cinematic, highly detailed, atmospheric, " + message).strip()[:800]
    return ("image", {"prompt": prompt, "text": "Voici une image générée à partir de ta demande."})


def _repli_video(message):
    return ("video", {
        "prompt": message[:800] or "une ambiance cinematographique",
        "narration": "Une scene se dessine. Les images defilent au rythme de la musique. "
                     "Puis le calme revient.",
        "text": "Voici une video generee a partir de ta demande.",
    })


def decide(messages, mode="auto", modele=None, profil="general", memoire=None, expert=None):
    """Renvoie ('text', texte) ou ('image', ...) ou ('animation', ...). Ne leve jamais."""
    system = systeme_pour(profil)
    if memoire:
        system = system + "\n\n" + memoire
    dernier_brut = ""
    images_jointes = False
    for m in reversed(messages):
        if m.get("role") == "user":
            dernier_brut = m.get("_texte") or m.get("content") or ""
            images_jointes = bool(m.get("_images"))
            break
    dernier = dernier_brut.lower()

    veut_anim = any(k in dernier for k in MOTS_ANIM)
    veut_image = any(k in dernier for k in MOTS_IMAGE)
    veut_video = any(k in dernier for k in MOTS_VIDEO)

    # Une image jointe = l'utilisateur veut en parler, pas en generer une nouvelle.
    if images_jointes:
        veut_anim = veut_image = veut_video = False

    # En local (pas de cle cloud), on evite l'appel LLM pour les medias : trop lent
    # (30-90 s sur ce CPU). On utilise un repli direct. Avec une cle Groq, le LLM
    # est utilise pour un meilleur prompt/narration (rapide).
    if not CLOUD_PRET:
        if veut_video:
            return _repli_video(dernier_brut)
        if veut_anim:
            return _repli_animation(dernier_brut)
        if veut_image:
            return _repli_image(dernier_brut)

    if not veut_anim and not veut_image and not veut_video:
        try:
            return ("text", chat(messages, system=system, mode=mode, modele=modele,
                                 profil=profil, expert=expert))
        except LimiteIA as e:
            return ("text", "⏳ Le service en ligne est momentanément limité. "
                            f"Réessaie dans {e.secondes} s.")
        except Exception:
            return ("text", "Je n'arrive pas à joindre le moteur IA pour le moment. "
                            "Vérifie que le service local est démarré, puis réessaie.")

    system_media = SYSTEM_MEDIA
    if memoire:
        system_media = system_media + "\n\n" + memoire
    try:
        brut = chat(messages, system=system_media, force_json=True, mode=mode, modele=modele,
                    profil=profil)
        data = _extract_json(brut)
    except Exception:
        if veut_video:
            return _repli_video(dernier_brut)
        return _repli_animation(dernier_brut) if veut_anim else _repli_image(dernier_brut)

    if data and data.get("action") == "video" and veut_video:
        return ("video", {
            "prompt": str(data.get("prompt") or dernier_brut)[:800],
            "narration": str(data.get("narration") or data.get("text") or "")[:800],
            "text": str(data.get("text") or "Voici ta vidéo."),
            "musique": True,
            "sous_titres": True,
        })
    if data and data.get("action") == "animation" and veut_anim:
        return ("animation", {
            "prompt": str(data.get("prompt") or dernier_brut)[:800],
            "narration": str(data.get("narration") or data.get("text") or "")[:600],
            "text": str(data.get("text") or "Voici ta petite animation."),
        })
    if data and data.get("action") == "image" and veut_image:
        return ("image", {
            "prompt": str(data.get("prompt") or dernier_brut)[:800],
            "text": str(data.get("text") or "Voici ton image."),
        })

    if veut_video:
        narration = str(data.get("narration")) if data and data.get("narration") else ""
        return ("video", {
            "prompt": (data or {}).get("prompt") or dernier_brut,
            "narration": narration or dernier_brut,
            "text": "Voici ta vidéo.",
            "musique": True,
            "sous_titres": True,
        })
    if veut_anim:
        narration = str(data.get("narration")) if data and data.get("narration") else ""
        return ("animation", {
            "prompt": (data or {}).get("prompt") or dernier_brut,
            "narration": narration or "Une scene apparait, puis se dissout doucement dans le noir.",
            "text": "Voici une petite animation.",
        })
    return ("image", {
        "prompt": (data or {}).get("prompt") or dernier_brut,
        "text": (data or {}).get("text") or "Voici ton image.",
    })
