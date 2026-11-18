# Capzo IA — ton assistant, sur ton PC ou en ligne

> Nouveautés (interface ChatGPT/Claude, modes, connexion obligatoire, Android, réseaux sociaux) : voir `NOUVEAUTES.md`.
Ton assistant **Capzo IA** : chat en direct, images, animations 2D avec voix off,
**pièces jointes** (photos, vidéos, fichiers) et **plusieurs cerveaux IA**.

Il fonctionne **sans aucune clé API** grâce à [Ollama](https://ollama.com) (modèles libres sur ton PC).
Il peut aussi utiliser une **API en ligne gratuite** (plus rapide) si tu en ajoutes une.

## Lancer

Double-clique sur **`lancer.bat`** (ou : `python app.py`)

Le navigateur s'ouvre sur **http://127.0.0.1:5050**

## Utiliser

- **Chat** : écris un message, Entrée pour envoyer. La réponse s'affiche **en direct**.
- **Images** : « dessine une forêt brumeuse la nuit ».
- **Animations** : « fais une animation d'une maison hantée » → SVG animé + voix off + sous-titres.
- **Micro** : bouton 🎤 pour parler (reconnaissance vocale du navigateur).
- **Pièces jointes** : bouton 📎 ou **glisser-déposer** une photo, une vidéo ou un fichier.
- **Thèmes** : 🌙 Sombre, ⚡ Néon, ☀️ Clair, 🌿 Émeraude (mémorisé).
- **Effacer** : la corbeille remet la conversation à zéro.

### Les trois réglages en haut de l'écran

| Réglage | À quoi ça sert |
|---|---|
| **Cerveau IA** | 🧠 Auto, 🌐 En ligne, ou un modèle précis installé sur le PC (👁 = voit les images) |
| **Temps de réflexion** | ⚡ Rapide (~70 mots) · ⚖️ Équilibré (~150) · 🔎 Approfondi (~320) |
| **Thème** | change les couleurs de l'interface |

> Le niveau de réflexion ne change **pas** de modèle (sinon Ollama devrait le recharger,
> ce qui coûtait ~20 s) : il change seulement la **longueur maximale** de la réponse.

### La ligne de statistiques

Sous chaque réponse, Capzo affiche ses mesures réelles :

```
⏱ 33,4 s · 1er mot 25,3 s · réflexion 20,1 s · 4,1 tok/s · chargement 5,0 s
```

- **⏱ total** : durée complète de la réponse
- **1er mot** : temps avant le premier mot affiché (le plus important pour la sensation de vitesse)
- **réflexion** : temps de lecture du prompt (historique + fichiers + question)
- **tok/s** : vitesse de génération
- **chargement** : temps de chargement du modèle en mémoire (0 s quand il est déjà chaud)

## Voix, téléphone, connecteurs

### Voix neuronale (comme les autres IA)

Capzo parle avec une **vraie voix française** (`edge-tts`, gratuit, sans clé) et lit la
réponse **pendant** qu'elle s'écrit, phrase par phrase.

- Bouton 🔊 dans l'en-tête : activer / couper.
- Menu juste à côté : 6 voix (Denise, Henri, Éloïse, Rémy, Sylvie, Antoine).
- Sans Internet, Capzo retombe automatiquement sur la voix du navigateur.

### Sur le téléphone (PWA)

Capzo s'installe comme une **application** : ouvre le site puis « Ajouter à l'écran d'accueil ».

- Plein écran, icône Capzo, démarrage rapide.
- **Partage** : depuis la galerie ou une autre app → Partager → Capzo
  (ou « Partager vers Capzo »). Le fichier arrive directement dans la discussion.
- **Liens profonds** : Capzo peut ouvrir WhatsApp, Instagram, Maps, YouTube, Spotify,
  le téléphone ou les SMS (`tel:`, `sms:`).

### Réveil « Hey Capzo »

Bouton 🛰 dans l'en-tête : Capzo écoute, et dès qu'il entend **« Hey Capzo »** il
répond **« Comment puis-je vous être utile ? »** puis attend ta demande.

> Limite honnête : un site web ne peut pas écouter quand il est fermé. Ça fonctionne
> quand Capzo est ouvert (application installée, écran allumé). Pour un réveil permanent
> il faudrait une vraie app Android native.

### Connecteurs (mail, agenda, Instagram)

Bouton 🔌 → état des connecteurs. Tout se configure dans **`CapzoIA/.env`** :

| Connecteur | Variables | Exemples de phrases |
|---|---|---|
| **Messagerie** | `CAPZO_MAIL_ADRESSE`, `CAPZO_MAIL_MDP` (mot de passe d'application) | « lis mes derniers mails », « envoie un mail à … » |
| **Agenda** | `CAPZO_AGENDA_ICS` (adresse iCal secrète) | « mes rendez-vous cette semaine », « ajoute un rdv mardi 14 h » |
| **Instagram** | `CAPZO_IG_USER`, `CAPZO_IG_TOKEN` | « stats de mon Instagram », « publie ce Reel » |

### Connecter Google en un clic (sans mot de passe d'application)

1. https://console.cloud.google.com → Nouveau projet → « APIs et services » → « Identifiants ».
2. « Créer des identifiants » → « ID client OAuth 2.0 » → type **Application Web**.
3. Origines JavaScript autorisées : ton site (ex. `http://127.0.0.1:5050` et ton URL Render).
4. URI de redirection autorisés : `<ton site>/api/google/callback`.
5. Active les APIs **Gmail API** et **Google Calendar API**.
6. Copie l'ID client et le secret dans `.env` :
   ```
   CAPZO_GOOGLE_CLIENT_ID=123...apps.googleusercontent.com
   CAPZO_GOOGLE_CLIENT_SECRET=GOCSPX-...
   CAPZO_SITE_URL=https://ton-site.onrender.com
   ```
7. Dans Capzo : 🔌 → « Connecter mon compte Google » → autorise → terminé.
   Capzo lit alors tes mails et ton agenda via l'API Google (plus besoin de
   mot de passe d'application ni d'adresse iCal).

### Application native (Android)

Un squelette Android Studio est fourni dans `native/android/` (WebView + micro +
ouverture des apps). Voir `native/README.md`. Sur iPhone, la PWA fait le même
travail visuellement.

- Un rendez-vous créé sans CalDAV génère un **fichier .ics** : un clic sur le bouton
  l'ajoute à l'agenda du téléphone.
- Instagram : compte **professionnel** + app Meta gratuite. La publication d'un Reel
  exige une vidéo à une **URL publique https** (ton site Render peut la servir).
- Analyser le compte d'une **autre** personne n'est pas possible proprement : Meta ne
  fournit pas d'API et le scraping fait bannir le compte.

### Ce que Capzo sait faire des fichiers joint(e)s

| Type | Ce que Capzo en fait |
|---|---|
| Photo (jpg, png, webp…) | Décrite par un **modèle de vision** local (`moondream`) |
| Vidéo (mp4, mov, mkv…) | Capzo extrait 2 images de la vidéo et les décrit |
| Texte, code, CSV, JSON, Markdown | Le contenu est lu et utilisé pour répondre |
| PDF | Le texte est extrait (nécessite `pypdf`) puis utilisé |

## Comment ça marche (sans clé)

| Fonction | Moteur |
|---|---|
| Chat / rédaction | **Ollama local** (`qwen2.5:1.5b` par défaut) |
| Photos et vidéos | **`moondream`** (vision, local) |
| Images générées | Pollinations (gratuit, sans clé) |
| Animations | SVG animé généré localement (aucun réseau) |
| Voix off | Synthèse vocale du navigateur |

### Installer d'autres cerveaux

Bouton **➕** dans l'en-tête : Capzo affiche un catalogue de cerveaux à installer
en un clic (installation en arrière-plan par `ollama pull`).

Ou en ligne de commande :

```powershell
ollama pull qwen2.5:0.5b    # ultra rapide (≈0,4 Go)
ollama pull qwen2.5:1.5b    # équilibré (≈1 Go) — installé par défaut
ollama pull qwen2.5:3b      # meilleure qualité (≈2 Go)
ollama pull llama3.2:3b     # autre style, bon en français
ollama pull gemma2:2b       # Google, compact
ollama pull moondream       # vision : comprendre photos et vidéos
```

Ils apparaissent tout seuls dans le menu. Pour forcer un modèle par défaut :

```powershell
$env:CAPZO_MODEL = "qwen2.5:3b"
python app.py
```

## Accélérer avec une API gratuite (optionnel)

Sur ce PC (Pentium Silver N5030, sans carte graphique), le calcul local tourne à
**~3–5 tokens/s** : c'est la limite matérielle, pas un bug. Pour des réponses
quasi instantanées, ajoute une clé **gratuite** (Groq, OpenRouter, Google AI Studio…) :

```powershell
$env:CAPZO_API_URL   = "https://api.groq.com/openai/v1"
$env:CAPZO_API_KEY   = "ta_cle_gratuite"
$env:CAPZO_API_MODEL = "llama-3.1-8b-instant"
python app.py
```

En mode **🧠 Auto**, Capzo essaie le cloud **en premier** (beaucoup plus rapide),
puis Ollama, puis Pollinations. En mode **💻 modèle**, il reste **100 % local**
(utile hors connexion : fichiers et photos ne sortent jamais du PC).

## Publier Capzo en vrai site 24/7

Tout est prêt (Render, Docker, Hugging Face Spaces) : voir **[PUBLIER.md](PUBLIER.md)**.
En résumé : GitHub → Render → variables `CAPZO_MOTEUR=cloud`, `CAPZO_API_URL`,
`CAPZO_API_KEY`, `CAPZO_API_MODEL`, et `CAPZO_MOT_DE_PASSE` pour protéger le site.

## Vitesse sur ce PC

Le processeur n'a pas de carte graphique : la génération est lente (≈3–5 token/s).
C'est pour ça que :

- la réponse **s'affiche en flux** (tu lis pendant que ça se génère) ;
- le modèle **1,5B** est privilégié (≈2× plus rapide que le 3B) ;
- le modèle est **gardé en mémoire** (`/api/chauffe`) et les autres sont déchargés ;
- les réponses sont demandées **courtes** et le niveau de réflexion limite les tokens.

Les images et animations, elles, restent rapides.

## Fichiers

```
CapzoIA/
  app.py               serveur + routes (chat, flux SSE, upload, modèles, catalogue)
  lancer.bat           double-clic pour démarrer
  PUBLIER.md           publier le site (Render / Docker / HF Spaces)
  requirements.txt     dépendances Python
  Dockerfile, Procfile, render.yaml   paquet de déploiement
  uploads/             fichiers joints (créé automatiquement)
  capzo/
    llm.py             Ollama + cloud + secours, streaming, stats, cerveaux, vision
    fichiers.py        lecture des textes, PDF, images, vidéos
    images.py          génération d'images gratuite
    anim.py            animations SVG (IA + repli procédural)
  templates/index.html l'interface (Tailwind, thèmes, SSE)
```

## Notes

- Les **images générées** ont besoin d'**internet**. Si le service gratuit est saturé,
  l'appli réessaie puis affiche un message clair.
- En mode local, les **fichiers joints** ne quittent jamais l'ordinateur.
- Les « vidéos » de Capzo sont des **animations SVG en boucle** (pas des MP4),
  avec la voix du navigateur.
- Pour de vrais MP4 verticaux, utilise **STUDIO ZÉRO** (dossier `studio_zero`).
