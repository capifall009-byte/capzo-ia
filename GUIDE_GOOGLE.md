# Connecter son compte Google à Capzo IA — guide pas à pas

## ⚠️ Lire d'abord : ce que Capzo ne fera jamais

Capzo **ne demande pas** ton email + mot de passe Google. C'est interdit par Google et dangereux (c'est exactement ce que font les arnaques). Seul Google voit ton mot de passe.

Capzo utilise la **connexion Google en 1 clic (OAuth officiel)** :
- Tu cliques sur « Se connecter avec Google » dans Capzo.
- Google s'ouvre, tu te connectes **chez Google**.
- Google demande : « Capzo veut lire vos mails et votre agenda — Autoriser ? »
- Tu acceptes. Google donne à Capzo un **jeton** (pas ton mot de passe).
- Capzo peut alors lire/envoyer des mails et gérer l'agenda.

---

## Étape 0 — Avoir une adresse de site fixe (important)

Google demande une **adresse de redirection fixe**. Le lien `*.trycloudflare.com` change à chaque redémarrage : la connexion Google ne fonctionnera donc **pas de façon stable** dessus.

👉 Il faut d'abord déployer Capzo sur **Render** (gratuit). Guide complet dans `PUBLIER.md`. Ton adresse sera alors du type :

```
https://capzo-ia.onrender.com
```

C'est cette adresse qu'on donnera à Google aux étapes suivantes.

---

## Étape 1 — Créer le projet Google Cloud

1. Va sur **https://console.cloud.google.com/**
2. Connecte-toi avec ton compte Google.
3. En haut, clique sur **« Sélectionner un projet »** → **« Nouveau projet »**.
4. Nom : `Capzo IA` → **Créer**.
5. Sélectionne ce projet (en haut de la page).

## Étape 2 — Activer les API Gmail et Agenda

1. Menu ☰ → **API et services** → **Bibliothèque**.
2. Cherche **« Gmail API »** → clique dessus → **Activer**.
3. Retour dans la Bibliothèque.
4. Cherche **« Google Calendar API »** → **Activer**.

## Étape 3 — Configurer l'écran de consentement

1. Menu ☰ → **API et services** → **Écran de consentement OAuth**.
2. Type d'utilisateur : choisis **« Externe »** → **Créer**.
3. Remplis :
   - Nom de l'application : `Capzo IA`
   - E-mail d'assistance utilisateur : **ton email Google**
   - Domaine autorisé : laisse vide
   - E-mail du développeur : **ton email Google**
4. Clique sur **Enregistrer et continuer** jusqu'à la fin (Étapes 2, 3, 4, 5).
5. À l'étape **« Utilisateurs test »**, clique sur **+ AJOUTER DES UTILISATEURS** et ajoute **ton propre email Google** → **Enregistrer**.
   (Sans ça, Google refusera la connexion tant que l'app est en mode test.)

## Étape 4 — Créer les identifiants

1. Menu ☰ → **API et services** → **Identifiants**.
2. En haut, clique sur **+ CRÉER DES IDENTIFIANTS** → **« ID client OAuth »**.
3. Type d'application : **« Application Web »**.
4. Nom : `Capzo IA Web`.
5. **URI de redirection autorisés** → clique sur **+ AJOUTER UN URI** et colle :

```
https://capzo-ia.onrender.com/api/google/callback
```

(remplace `capzo-ia.onrender.com` par ta vraie adresse Render si elle est différente)

6. Clique sur **Créer**.
7. Une fenêtre s'affiche avec :
   - **ID client** → copie-le
   - **Secret client** → copie-le

⚠️ Ne partage ces deux valeurs avec personne et ne les publie pas sur GitHub.

## Étape 5 — Mettre les valeurs dans Capzo

### Si tu héberges sur Render (recommandé)
1. Va sur ton service Render → onglet **Environment**.
2. Ajoute ces 3 variables :

| Nom | Valeur |
|---|---|
| `CAPZO_GOOGLE_CLIENT_ID` | l'ID client copié |
| `CAPZO_GOOGLE_CLIENT_SECRET` | le secret client copié |
| `CAPZO_SITE_URL` | `https://capzo-ia.onrender.com` |

3. Clique sur **Save Changes** → Render redémarre automatiquement.

### Si tu restes en local pour tester
Ouvre `CapzoIA/.env` avec le Bloc-notes et ajoute ces lignes à la fin :

```
CAPZO_GOOGLE_CLIENT_ID=ton_id_client
CAPZO_GOOGLE_CLIENT_SECRET=ton_secret_client
CAPZO_SITE_URL=https://ton-adresse-ici
```

Puis redémarre Capzo.

## Étape 6 — Se connecter dans Capzo

1. Ouvre Capzo → onglet **Connecteurs** (icône 🔌).
2. Clique sur **« Se connecter avec Google »**.
3. Google s'ouvre → connecte-toi → **Autoriser**.
4. Tu reviens sur Capzo avec un message : « Connecté : ton.email@gmail.com ».

✅ C'est fait. Capzo peut maintenant lire tes mails et ton agenda.

---

## Dépannage

| Problème | Solution |
|---|---|
| « Google n'est pas configuré » | Les variables de l'Étape 5 ne sont pas remplies ou Capzo n'a pas redémarré. |
| « redirect_uri_mismatch » | L'URI dans Google Cloud ne correspond pas exactement à l'adresse du site (vérifie `/api/google/callback` et le `https://`). |
| « access_denied » / « app non vérifiée » | Ajoute ton email dans **Utilisateurs test** (Étape 3.5). |
| Connexion perdue au redémarrage du tunnel | Normal avec `trycloudflare.com` : passe par Render pour une adresse fixe. |

## Sécurité

- Les jetons sont stockés dans `google_tokens.json` (déjà ignoré par Git).
- Pour déconnecter : bouton **« Déconnecter Google »** dans les connecteurs.
- Pour révoquer l'accès depuis Google : https://myaccount.google.com/permissions → Capzo IA → **Supprimer l'accès**.
