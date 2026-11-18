# -*- coding: utf-8 -*-
"""Hermes pour Capzo : journal d'apprentissage persistant, inspire de
NousResearch/hermes-agent ("the agent that grows with you").

Le vrai depot Hermes est un agent Python complet, trop lourd pour l'hebergement
gratuit de Render. Ici on garde l'essentiel cote serveur : Capzo se souvient de
ce qu'il a appris avec toi et s'en sert dans le mode 🧬 Hermes.
"""
import re

from . import memoire

MAX_LECONS = 40
MAX_CTX = 8

# On n'enregistre pas les secrets eventuellement colles dans une question.
SECRETS = re.compile(
    r"mot de passe|password|jeton|token|api[_ -]?key|cle d['’]api|secret|code pin|"
    r"num(?:ero|éro) de carte|iban", re.IGNORECASE)

# Signaux qu'un echange vaut la peine d'etre retenu comme "lecon".
APPRENDRE = re.compile(
    r"\b(apprends|apprendre|retiens|souviens[- ]toi|m[ée]morise|note que|"
    r"[àa] l'avenir|d[ée]sormais|dor[ée]navant|pr[ée]f[èe]re|pr[ée]f[ée]rence|"
    r"comment (?:fais|fait|tu fais|fonctionne)|automatise|plan|projet|objectif|"
    r"m[ée]thode|r[èe]gle|astuce)\b", re.IGNORECASE)


def lecons():
    d = memoire._lire()
    return list(d.get("lecons") or [])


def ajouter_lecon(texte):
    texte = re.sub(r"\s+", " ", (texte or "")).strip()
    if len(texte) < 12 or len(texte) > 320:
        return False
    if SECRETS.search(texte):
        return False
    d = memoire._lire()
    d.setdefault("lecons", [])
    if texte in d["lecons"]:
        return False
    d["lecons"].append(texte)
    d["lecons"] = d["lecons"][-MAX_LECONS:]
    memoire._ecrire(d)
    return True


def apprendre(question, reponse):
    """Enregistre un echange marquant. Appelé apres la reponse en mode Hermes."""
    q = (question or "").strip()
    r = (reponse or "").strip()
    if not q or not r or SECRETS.search(q):
        return False
    if not APPRENDRE.search(q):
        return False
    q_clean = re.sub(r"\s+", " ", q)[:150]
    r_clean = re.sub(r"\s+", " ", r)[:170]
    return ajouter_lecon("Q : " + q_clean + " → R : " + r_clean)


def contexte():
    """Injectable dans le prompt systeme pour personnaliser la reponse."""
    items = lecons()[-MAX_CTX:]
    if not items:
        return ""
    lignes = "\n".join("- " + lecon for lecon in items)
    return ("\n\n=== HERMES — JOURNAL D'APPRENTISSAGE ===\n" + lignes +
            "\nUtilise ces lecons pour adapter ta methode et ta personnalite. "
            "Ne les recite pas telles quelles, et ne les inventes pas.")


def etat():
    return {"actif": True, "nombre": len(lecons()), "journal": lecons()[-10:]}
