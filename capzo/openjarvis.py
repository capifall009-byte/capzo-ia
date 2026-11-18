# -*- coding: utf-8 -*-
"""OpenJarvis dans Capzo : compétences et méthode de travail "local-first".

Inspire de https://github.com/open-jarvis/OpenJarvis (Stanford Hazy Research,
"Personal AI, On Personal Devices", Apache 2.0). Le projet complet est une pile
Python/Rust/Tauri avec Ollama : trop lourd pour l'offre gratuite de Render.
Capzo en garde l'essentiel cote serveur : un catalogue de competences et des
methodes courtes injectees dans le mode 🤖 Jarvis.
"""
import re

PROJET = {
    "nom": "OpenJarvis",
    "auteur": "Stanford Hazy Research / Scaling Intelligence Lab",
    "url": "https://github.com/open-jarvis/OpenJarvis",
    "site": "https://openjarvis.stanford.edu/",
    "licence": "Apache 2.0",
    "devise": "Personal AI, On Personal Devices",
}

# Competences inspirees des agents integres et des presets OpenJarvis.
# Chaque "methode" est une consigne courte ajoutee au prompt quand la demande
# correspond (pas de code externe, pas de dependance supplementaire).
SKILLS = [
    {
        "id": "digest",
        "nom": "Briefing du matin",
        "mots": ("briefing", "reveil", "matin", "resume du jour", "nouvelles", "actualites"),
        "methode": "Donne un briefing court : temps, agenda, priorités, nouveautés. "
                   "Une ligne par point, l'essentiel d'abord, puis une seule action proposée.",
    },
    {
        "id": "recherche",
        "nom": "Recherche approfondie",
        "mots": ("recherche", "rechercher", "sources", "comparer", "enquete", "verifier"),
        "methode": "Procède en sauts : question précise, sources fiables datées, synthèse. "
                   "Cite les sources et signale ce qui reste incertain.",
    },
    {
        "id": "code",
        "nom": "Assistant code",
        "mots": ("code", "programme", "bug", "erreur", "script", "python", "javascript"),
        "methode": "Donne le code complet et prêt à tourner, avec la commande pour le lancer "
                   "et un test minimal. Explique seulement le piège principal.",
    },
    {
        "id": "monitor",
        "nom": "Surveillance / suivi",
        "mots": ("surveille", "suivi", "controle", "rappel", "regulierement", "chaque jour"),
        "methode": "Propose une routine simple : ce qu'on vérifie, à quelle fréquence, "
                   "quel signal déclenche une action, et comment arrêter proprement.",
    },
    {
        "id": "orchestrateur",
        "nom": "Orchestrateur d'outils",
        "mots": ("organise", "plan", "automatise", "outils", "etapes", "projet"),
        "methode": "Découpe en étapes numérotées, choisis l'outil Capzo utile à chaque étape, "
                   "et demande confirmation avant toute action externe.",
    },
    {
        "id": "simple",
        "nom": "Conversation simple",
        "mots": (),
        "methode": "Réponds directement et brièvement, sans outil si ce n'est pas nécessaire.",
    },
]


def trouver(demande):
    """Compétences correspondant à la demande (2 au maximum)."""
    t = (demande or "").lower()
    trouves = []
    for s in SKILLS:
        if any(m in t for m in s["mots"]):
            trouves.append(s)
    if not trouves:
        trouves = [SKILLS[-1]]
    return trouves[:2]


def contexte(demande=""):
    """Bloc court injecté dans le prompt du mode Jarvis."""
    lignes = []
    for s in trouver(demande):
        lignes.append("- " + s["nom"] + " : " + s["methode"])
    return ("\n\n=== OPENJARVIS — COMPÉTENCE ACTIVE ===\n" + "\n".join(lignes) +
            "\nLocal-first : traite en local ce qui peut l'être, sois court, et ne demande "
            "aucun secret inutile.")


def etat():
    return {
        "actif": True,
        "projet": PROJET,
        "nombre": len(SKILLS),
        "competences": [{"id": s["id"], "nom": s["nom"]} for s in SKILLS],
    }
