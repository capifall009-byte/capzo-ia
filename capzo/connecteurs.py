# -*- coding: utf-8 -*-
"""Connecteurs Capzo IA : messagerie (IMAP/SMTP) et agenda (iCal / CalDAV).

Tout passe par les bibliotheques standard de Python : aucune dependance.
Configuration dans CapzoIA/.env :

    CAPZO_MAIL_ADRESSE=mon.adresse@gmail.com
    CAPZO_MAIL_MDP=mot_de_passe_application   (Google : 2FA puis "mot de passe d'application")
    CAPZO_AGENDA_ICS=https://calendar.google.com/calendar/ical/.../basic.ics
"""
import email
import imaplib
import os
import re
import smtplib
import ssl
import time
import urllib.parse
import urllib.request
import uuid
from email.header import decode_header
from email.message import EmailMessage

try:
    from . import google_auth
except Exception:  # pragma: no cover
    google_auth = None

MAIL_ADRESSE = (os.environ.get("CAPZO_MAIL_ADRESSE") or "").strip()
MAIL_MDP = (os.environ.get("CAPZO_MAIL_MDP") or "").strip()
IMAP_HOTE = (os.environ.get("CAPZO_IMAP") or "imap.gmail.com").strip()
SMTP_HOTE = (os.environ.get("CAPZO_SMTP") or "smtp.gmail.com").strip()

AGENDA_ICS = (os.environ.get("CAPZO_AGENDA_ICS") or "").strip()
AGENDA_CALDAV = (os.environ.get("CAPZO_AGENDA_CALDAV") or "").strip()
AGENDA_USER = (os.environ.get("CAPZO_AGENDA_USER") or MAIL_ADRESSE).strip()
AGENDA_MDP = (os.environ.get("CAPZO_AGENDA_MDP") or MAIL_MDP).strip()

def mail_pret():
    if google_auth is not None and (google_auth.etat() or {}).get("pret"):
        return True
    return bool(MAIL_ADRESSE and MAIL_MDP)


def agenda_pret():
    if google_auth is not None and (google_auth.etat() or {}).get("pret"):
        return True
    return bool(AGENDA_ICS or AGENDA_CALDAV)


def etat():
    g = google_auth.etat() if google_auth is not None else {"pret": False}
    return {
        "mail": {"pret": mail_pret(), "adresse": (g.get("email") if g.get("pret") else MAIL_ADRESSE) or None},
        "agenda": {"pret": agenda_pret(),
                   "lecture": bool(AGENDA_ICS or (g.get("pret"))), "ecriture": bool(AGENDA_CALDAV or (g.get("pret")))},
        "google": g,
    }


# ------------------------------------------------------------------ utilitaires
def _entete(msg, nom):
    brut = msg.get(nom, "") or ""
    morceaux = []
    for texte, encodage in decode_header(brut):
        if isinstance(texte, bytes):
            try:
                morceaux.append(texte.decode(encodage or "utf-8", "replace"))
            except Exception:
                morceaux.append(texte.decode("utf-8", "replace"))
        else:
            morceaux.append(texte)
    return " ".join(morceaux).strip()


def _corps(msg, limite=900):
    """Recupere la partie texte la plus lisible d'un mail."""
    if msg.is_multipart():
        for partie in msg.walk():
            if partie.get_content_type() == "text/plain" and "attachment" not in str(
                    partie.get("Content-Disposition") or ""):
                try:
                    return _nettoyer(partie.get_payload(decode=True).decode(
                        partie.get_content_charset() or "utf-8", "replace"))[:limite]
                except Exception:
                    continue
        for partie in msg.walk():
            if partie.get_content_type() == "text/html":
                try:
                    html = partie.get_payload(decode=True).decode(
                        partie.get_content_charset() or "utf-8", "replace")
                    return _nettoyer(re.sub(r"<[^>]+>", " ", html))[:limite]
                except Exception:
                    continue
        return ""
    try:
        return _nettoyer(msg.get_payload(decode=True).decode(
            msg.get_content_charset() or "utf-8", "replace"))[:limite]
    except Exception:
        return ""


def _nettoyer(t):
    return re.sub(r"\s+", " ", (t or "")).strip()


# ---------------------------------------------------------------------- mails
def lire_mails(nombre=5, non_lus=False):
    """Retourne (liste_de_mails, erreur)."""
    if not mail_pret():
        return [], ("La messagerie n'est pas configuree. Ajoute CAPZO_MAIL_ADRESSE et "
                    "CAPZO_MAIL_MDP dans CapzoIA/.env, ou connecte ton compte Google.")
    if google_auth is not None and (google_auth.etat() or {}).get("pret"):
        return google_auth.gmail_lire(nombre, non_lus)
    nombre = max(1, min(int(nombre or 5), 15))
    try:
        boite = imaplib.IMAP4_SSL(IMAP_HOTE, timeout=25)
        boite.login(MAIL_ADRESSE, MAIL_MDP)
        boite.select("INBOX", readonly=True)
        critere = "(UNSEEN)" if non_lus else "ALL"
        typ, data = boite.search(None, critere)
        ids = (data[0] or b"").split()
        mails = []
        for ident in reversed(ids[-nombre:]):
            typ, contenu = boite.fetch(ident, "(RFC822)")
            if not contenu or not isinstance(contenu[0], tuple):
                continue
            msg = email.message_from_bytes(contenu[0][1])
            mails.append({
                "de": _entete(msg, "From"),
                "sujet": _entete(msg, "Subject") or "(sans sujet)",
                "date": _entete(msg, "Date"),
                "extrait": _corps(msg, 400),
                "lu": "\\Seen" in (boite.fetch(ident, "(FLAGS)")[1][0] or b"").decode("utf-8", "replace"),
            })
        try:
            boite.logout()
        except Exception:
            pass
        return mails, None
    except Exception as e:
        return [], "Connexion mail impossible : " + str(e)[:160]


def envoyer_mail(destinataire, sujet, corps, copie=None):
    """Envoie un mail. Retourne (ok, message)."""
    if not mail_pret():
        return False, ("La messagerie n'est pas configuree. Ajoute CAPZO_MAIL_ADRESSE et "
                       "CAPZO_MAIL_MDP dans CapzoIA/.env, ou connecte ton compte Google.")
    if google_auth is not None and (google_auth.etat() or {}).get("pret"):
        return google_auth.gmail_envoyer(destinataire, sujet, corps)
    destinataire = (destinataire or "").strip()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", destinataire):
        return False, "Adresse du destinataire invalide."
    msg = EmailMessage()
    msg["From"] = MAIL_ADRESSE
    msg["To"] = destinataire
    if copie:
        msg["Cc"] = copie
    msg["Subject"] = (sujet or "(sans objet)")[:180]
    msg.set_content(corps or "")
    try:
        contexte = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOTE, 465, timeout=30, context=contexte) as serveur:
            serveur.login(MAIL_ADRESSE, MAIL_MDP)
            serveur.send_message(msg)
        return True, "Mail envoye a " + destinataire + "."
    except Exception as e:
        return False, "Envoi impossible : " + str(e)[:160]


# --------------------------------------------------------------------- agenda
def _deplier_ics(texte):
    return re.sub(r"\r?\n[ \t]", "", texte or "")


def _lire_date(valeur):
    """20140213T090000Z ou 20140213 (date seule) -> timestamp local approx."""
    valeur = (valeur or "").strip()
    try:
        if len(valeur) >= 15 and valeur[8] == "T":
            base = time.strptime(valeur[:15], "%Y%m%dT%H%M%S")
            return time.mktime(base)
        if len(valeur) >= 8:
            base = time.strptime(valeur[:8], "%Y%m%d")
            return time.mktime(base)
    except Exception:
        return None
    return None


def agenda_evenements(jours=7, limite=12):
    """Lit les prochains evenements depuis une adresse iCal (Google, Outlook...)."""
    if not agenda_pret():
        return [], ("L'agenda n'est pas configure. Ajoute CAPZO_AGENDA_ICS dans CapzoIA/.env "
                    "(adresse iCal secrete de ton agenda), ou connecte ton compte Google.")
    if google_auth is not None and (google_auth.etat() or {}).get("pret"):
        return google_auth.calendar_lire(jours, limite)
    try:
        req = urllib.request.Request(AGENDA_ICS, headers={"User-Agent": "CapzoIA"})
        with urllib.request.urlopen(req, timeout=25) as r:
            texte = _deplier_ics(r.read().decode("utf-8", "replace"))
    except Exception as e:
        return [], "Lecture de l'agenda impossible : " + str(e)[:160]

    evenements = []
    blocs = re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", texte, re.S)
    for bloc in blocs:
        def champ(nom):
            m = re.search(r"^" + nom + r"[^:]*:(.*)$", bloc, re.M)
            return (m.group(1).strip() if m else "")

        debut = _lire_date(champ("DTSTART"))
        if not debut:
            continue
        fin = _lire_date(champ("DTEND")) or debut + 3600
        evenements.append({
            "titre": (champ("SUMMARY") or "(sans titre)").replace("\\,", ",").replace("\\n", " "),
            "debut": time.strftime("%Y-%m-%d %H:%M", time.localtime(debut)),
            "fin": time.strftime("%H:%M", time.localtime(fin)),
            "lieu": (champ("LOCATION") or "").replace("\\,", ","),
            "_t": debut,
        })
    maintenant = time.time() - 3600
    fin_fenetre = time.time() + max(1, int(jours or 7)) * 86400
    evenements = [e for e in evenements if maintenant <= e["_t"] <= fin_fenetre]
    evenements.sort(key=lambda e: e["_t"])
    for e in evenements:
        e.pop("_t", None)
    return evenements[:limite], None


def _ics(titre, debut, duree_min, lieu="", description=""):
    try:
        t = time.strptime(debut.replace("T", " ")[:16], "%Y-%m-%d %H:%M")
    except Exception:
        return None
    depart = int(time.mktime(t))
    fin = depart + max(15, int(duree_min or 60)) * 60
    fmt = "%Y%m%dT%H%M%S"
    return ("BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Capzo IA//FR\r\n"
            "BEGIN:VEVENT\r\n"
            f"UID:{uuid.uuid4().hex}@capzo.local\r\n"
            f"DTSTAMP:{time.strftime(fmt, time.gmtime())}Z\r\n"
            f"DTSTART:{time.strftime(fmt, time.localtime(depart))}\r\n"
            f"DTEND:{time.strftime(fmt, time.localtime(fin))}\r\n"
            f"SUMMARY:{(titre or 'Rendez-vous')[:180]}\r\n"
            + (f"LOCATION:{(lieu or '')[:180]}\r\n" if lieu else "")
            + (f"DESCRIPTION:{(description or '')[:500]}\r\n" if description else "")
            + "END:VEVENT\r\nEND:VCALENDAR\r\n")


def creer_evenement(titre, debut, duree_min=60, lieu="", description=""):
    """Cree un evenement : CalDAV si configure, sinon fichier .ics a ouvrir.

    Retourne (infos, erreur). infos['lien'] permet d'ajouter l'evenement au calendrier
    du telephone en un clic.
    """
    if google_auth is not None and (google_auth.etat() or {}).get("pret"):
        return google_auth.calendar_creer(titre, debut, duree_min, lieu, description)
    if not contenu:
        return None, "Date invalide. Utilise le format AAAA-MM-JJ HH:MM (ex. 2026-11-20 14:30)."

    if AGENDA_CALDAV:
        try:
            uid = re.search(r"UID:(\S+)", contenu).group(1)
            url = AGENDA_CALDAV.rstrip("/") + "/" + uid + ".ics"
            req = urllib.request.Request(
                url, data=contenu.encode("utf-8"), method="PUT",
                headers={"Content-Type": "text/calendar; charset=utf-8",
                         "If-None-Match": "*"})
            if AGENDA_USER and AGENDA_MDP:
                import base64
                jeton = base64.b64encode(f"{AGENDA_USER}:{AGENDA_MDP}".encode()).decode()
                req.add_header("Authorization", "Basic " + jeton)
            with urllib.request.urlopen(req, timeout=25) as r:
                if r.status in (200, 201, 204):
                    return {"ok": True, "mode": "caldav", "titre": titre, "debut": debut,
                            "duree": duree_min, "lieu": lieu}, None
        except Exception:
            pass  # on retombe sur le fichier .ics

    dossier = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "uploads", "agenda")
    os.makedirs(dossier, exist_ok=True)
    ident = uuid.uuid4().hex[:12]
    chemin = os.path.join(dossier, ident + ".ics")
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(contenu)
    return {"ok": True, "mode": "fichier", "titre": titre, "debut": debut,
            "duree": duree_min, "lieu": lieu, "fichier": ident,
            "lien": "/api/agenda/ics/" + ident + ".ics"}, None
