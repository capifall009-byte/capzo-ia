# Publier Capzo IA en vrai site (24/7)

En local, Capzo utilise **Ollama** (ton PC). Sur un serveur, Ollama ne peut pas tourner :
Capzo utilise donc un **modèle en ligne** (API compatible OpenAI). Le site fonctionne
alors même quand ton PC est éteint.

## 1. Choisir un moteur en ligne (gratuit)

Capzo accepte n'importe quelle API compatible OpenAI. Les plus simples :

| Fournisseur | Adresse (CAPZO_API_URL) | Exemple de modèle | Clé |
|---|---|---|---|
| **Groq** (très rapide, gratuit) | `https://api.groq.com/openai/v1` | `qwen/qwen3.8-27b` | console.groq.com |
| **OpenRouter** (modèles `:free`) | `https://openrouter.ai/api/v1` | `meta-llama/llama-3.1-8b-instruct:free` | openrouter.ai |
| **Google AI Studio** | `https://generativelanguage.googleapis.com/v1beta/openai` | `gemini-2.0-flash` | aistudio.google.com |
| **Mistral** | `https://api.mistral.ai/v1` | `mistral-small-latest` | console.mistral.ai |

> Sans clé, Capzo retombe sur Pollinations (gratuit, mais **1 réponse / 45 s**).

## 2. Mettre le code sur GitHub

1. Crée un compte sur **github.com** (gratuit).
2. **New repository** → nom `capzo-ia` → **Create**.
3. Sur la page du dépôt : **Add file → Upload files**.
4. Glisse **tout le contenu** du dossier `CapzoIA` **sauf** `uploads/` et **sauf `.env`** (il contient tes secrets), puis **Commit changes**.

> Astuce : garde `Dockerfile`, `requirements.txt`, `Procfile`, `render.yaml` à la racine.

## 3. Déployer sur Render (gratuit)

1. Crée un compte sur **render.com** et connecte GitHub.
2. **New → Web Service** → choisis ton dépôt `capzo-ia`.
3. Render lit `render.yaml`. Sinon, saisis :
   - **Build Command** : `pip install -r requirements.txt`
   - **Start Command** : `gunicorn app:app --bind 0.0.0.0:$PORT --timeout 300 --workers 1 --threads 8`
4. Onglet **Environment**, ajoute :

```
CAPZO_MOTEUR     = cloud
CAPZO_API_URL    = https://api.groq.com/openai/v1
CAPZO_API_MODEL  = qwen/qwen3.8-27b
CAPZO_API_KEY    = gsk_…   (ta clé Groq)
```

Aucun mot de passe n’est ajouté : le site reste ouvert, comme tu l’as demandé.

5. **Create Web Service** → Render construit et te donne une adresse du type
   `https://capzo-ia.onrender.com`.

C'est en ligne 🎉 (le plan gratuit met le site en veille après 15 min d'inactivité :
le premier chargement peut alors prendre ~30–50 s).

## 4. Alternative : Hugging Face Spaces (Docker)

1. **huggingface.co** → **New Space** → SDK **Docker** → Blank.
2. Envoie les fichiers du projet (avec le `Dockerfile`).
3. Dans **Settings → Variables and secrets**, ajoute les mêmes variables (`CAPZO_API_KEY` en *secret*).
4. Le site est publié sur `https://<utilisateur>-<space>.hf.space`.

## 5. Changer l'adresse en local

```powershell
$env:CAPZO_PORT = "8080"        # autre port
$env:CAPZO_HOST = "0.0.0.0"     # accessible depuis le telephone (meme Wi-Fi)
python app.py
```

Capzo affiche alors deux adresses au démarrage : celle de l'ordinateur et celle du réseau.

## 6. Ce qui change entre local et en ligne

| Fonction | En local (Ollama) | En ligne (API) |
|---|---|---|
| Chat | illimité, gratuit, plus lent | rapide, quota du fournisseur |
| Photos / vidéos | `moondream` sur ton PC | pas de vision (texte seulement) |
| Fichiers texte / PDF | oui | oui |
| Images générées | Pollinations | Pollinations |
| Animations + voix | oui (dans le navigateur) | oui (dans le navigateur) |
| Limite 45 s | non | seulement sans clé API |

## Sécurité

Le site est volontairement ouvert (pas de mot de passe). N'importe qui ayant
le lien peut donc consommer ton quota Groq. Si tu changes d'avis, ajoute
`CAPZO_MOT_DE_PASSE = ton_mot_de_passe` dans les variables Render : le navigateur
demandera alors l'utilisateur `capzo` + ce mot de passe.

## Connecteurs en ligne

Ajoute les mêmes variables que dans `.env` (onglet **Environment** de Render) :

| Variable | Rôle |
|---|---|
| `CAPZO_MAIL_ADRESSE`, `CAPZO_MAIL_MDP` | lire et envoyer des mails |
| `CAPZO_AGENDA_ICS` | lire l'agenda (adresse iCal secrète) |
| `CAPZO_AGENDA_CALDAV` | écrire directement dans l'agenda (optionnel) |
| `CAPZO_IG_USER`, `CAPZO_IG_TOKEN` | Instagram (stats + publication de Reels) |

> **Ne téléverse jamais `.env` sur GitHub** : il contient tes secrets.
> Le fichier `.gitignore` fourni l'exclut déjà.

## Ce qui marche en ligne

- Chat, voix neuronale, images, animations, PWA / partage : ✅
- Mails, agenda, Instagram : ✅ (connecteurs côté serveur)
- Photos et vidéos analysées par `moondream` : ❌ (pas de vision locale sur un serveur gratuit)
- Fichiers texte / PDF : ✅
