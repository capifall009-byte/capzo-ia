# Capzo IA — nouvelles fonctionnalités

Hébergement et adresse **inchangés** : `https://capzo-ia.onrender.com`
(service Render existant `srv-dbueb51srm7s73ek2cbg`, déploiement automatique depuis GitHub).

## 1. Interface façon ChatGPT / Claude

- Barre latérale : discussions sauvegardées dans le navigateur, modes rapides, compte.
- Réponses sans bulle lourde, messages utilisateur discrets, composeur arrondi.
- Thèmes existants conservés (sombre, clair, cyberpunk, émeraude).
- Accueil personnalisé avec salutation, jour de la semaine et phrase de motivation du jour.

## 2. Salutations et civilité

- « Bonjour / Bon après-midi / Bonsoir » selon l'heure.
- « Monsieur » ou « Madame » selon le choix de la personne (boutons sur l'accueil,
  enregistrés par visiteur). Google ne transmet **pas** le genre : aucun service n'en déduit un.
- Jour de la semaine, date et citation quotidienne (14 phrases, une par jour).

## 3. Nouveaux modes

`build` (projet de A à Z), `religion` (neutre et documenté), `adulte` (ton mature,
sans contenu explicite ni illégal), `histoire` (récit complet à partir du prompt).
Ils sont dans le sélecteur du haut, dans le menu et sur l'écran d'accueil.

## 4. Connexion optionnelle, sans mot de passe

- La connexion est **optionnelle** : Capzo reste utilisable sans compte.
- La bannière en bas d'écran propose de se connecter (Google/GitHub/Apple) pour lire
  les mails, l'agenda et les réseaux sociaux. Sans connexion, ces fonctions sont
  simplement indisponibles (message clair), le chat et les médias fonctionnent.
- Les routes `Google`, `GitHub`, `Apple` et les callbacks restent publics.
- La page d'accueil, le manifeste, le service worker, les icônes et le fichier de
  vérification Search Console restent publics.
- Aucun mot de passe n'est demandé ou stocké sur le site ; OAuth officiel uniquement.

### GitHub (à activer une fois l'OAuth App créée)

1. https://github.com/settings/developers → **New OAuth App**
2. Homepage URL : `https://capzo-ia.onrender.com`
3. Authorization callback URL : `https://capzo-ia.onrender.com/api/github/callback`
4. Ajouter dans Render → Environment :
   - `CAPZO_GITHUB_CLIENT_ID`
   - `CAPZO_GITHUB_CLIENT_SECRET`

Tant que ces variables sont absentes, le bouton GitHub affiche un message clair et
Google reste utilisable.

## 5. Android

- PWA améliorée (cache `capzo-v4`, icônes, QR code téléchargeable) :
  Chrome → « Installer l'application », ou Safari → « Sur l'écran d'accueil ».
- Projet WebView `native/android` corrigé : adresse Render stable, ouverture des
  OAuth dans le navigateur système, sélecteur de fichiers, partage entrant.
  Compiler gratuitement avec Android Studio → Build APK.

## 6. Connecteurs sociaux et Windsor IA

Le panneau « 🔌 Connecteurs » affiche l'état de chaque service et n'affiche jamais
de secret.

| Service | Variables Render | Commentaire |
|---|---|---|
| Instagram | `CAPZO_IG_APP_ID` + `CAPZO_IG_APP_SECRET` | OAuth Meta, callback `/api/social/instagram/callback`. Le mode existant `CAPZO_IG_TOKEN` reste supporté. |
| TikTok | `CAPZO_TIKTOK_CLIENT_KEY` + `CAPZO_TIKTOK_CLIENT_SECRET` | OAuth officiel, callback `/api/social/tiktok/callback`. Scope réglable avec `CAPZO_TIKTOK_SCOPE`. |
| Windsor IA | `CAPZO_WINDSOR_URL` + `CAPZO_WINDSOR_KEY` | Passerelle générique : bouton « Tester la connexion ». La clé n'est jamais renvoyée au navigateur. |

« Windsor IA » n'ayant pas d'API publique documentée précisément, il est branché
comme adaptateur générique : fournis l'URL de son API et ta clé, et le connecteur
devient opérationnel sans modifier le code ni l'hébergement. Si ton Windsor IA
utilise un format d'échange particulier, transmets sa documentation pour l'adapter.

## 7. Mémoire, voix et agents

- **Mémoire persistante** par visiteur : faits/préférences et souvenirs, injectés dans les prompts. Panneau « 🧠 Mémoire » pour consulter/effacer.
- **Voix masculine hyper-réaliste** par défaut : Henri Neural (Microsoft Edge TTS), sélectionnable.
- **Mode mythologie** (mythes de tous les peuples) + modes **Jarvis** et **Hermes** (liens GitHub OpenJarvis et Hermes Agent).
- **Disponibilité mobile** améliorée (bouton d'installation toujours visible).

## 8. Inscription, Apple et accès avancé

- Bouton **« S'inscrire gratuitement »** sur le portail : l'inscription se fait en un clic
  avec Google, GitHub ou Apple (aucun mot de passe).
- **Connexion Apple** possible si `CAPZO_APPLE_CLIENT_ID` + `CAPZO_APPLE_CLIENT_SECRET` sont
  renseignés (ou la génération automatique via `CAPZO_APPLE_TEAM_ID`, `CAPZO_APPLE_KEY_ID`,
  `CAPZO_APPLE_PRIVATE_KEY`). Callback : `/api/apple/callback` (Apple répond en POST).
- **Accès avancé** (bouton bouclier) : micro, caméra, notifications, position, presse-papiers,
  fichiers — activés uniquement sur demande. Sur le web ils restent limités par le navigateur ;
  l'app Android expose l'interface `CapzoNative` pour demander les permissions natives.
- Les boutons de fournisseur non configurés sont désactivés avec un message clair (plus de
  « codes » bruts lors d'un clic sur Google).

## Sécurité

- Jetons Google, GitHub et sociaux isolés par visiteur via le cookie `capzo_vid`.
- Fichiers de jetons : `google_tokens_*.json`, `github_tokens_*.json`, `social_*_*.json`,
  `utilisateur_*.json` — tous ignorés par Git via `.gitignore`.
- Sur Render (plan gratuit), le système de fichiers est éphémère : après un
  redéploiement, l'utilisateur se reconnecte en un clic. Aucune donnée sensible
  n'est écrite dans le dépôt public.
