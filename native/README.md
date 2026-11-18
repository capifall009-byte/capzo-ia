# Capzo IA — application native Android (projet Android Studio)

Ce dossier contient un **projet Android minimal** qui enveloppe le site Capzo
dans une WebView, avec accès au micro (pour « Hey Capzo ») et ouverture des
apps externes (WhatsApp, Maps, téléphone, SMS, mail).

## Prérequis (gratuits)

1. Installe **Android Studio** : https://developer.android.com/studio
   (téléchargement ~1 Go, installation ~10 min).
2. Ouvre Android Studio → « Open » → sélectionne ce dossier `native/android`.

## Compiler l'APK

- Android Studio télécharge automatiquement Gradle et le SDK.
- Menu **Build → Build Bundle(s) / APK(s) → Build APK(s)**.
- L'APK se trouve dans `app/build/outputs/apk/debug/app-debug.apk`.
- Transfère-le sur ton téléphone (e-mail, câble, Drive) et installe-le
  (autorise les sources inconnues si demandé).

## Configurer l'adresse du site

L'adresse est déjà fixée sur **`https://capzo-ia.onrender.com`** dans
`MainActivity.kt` et dans le filtre d'intent du `AndroidManifest.xml`.
Aucune modification n'est nécessaire : l'hébergement Render reste inchangé.
Si tu changes un jour d'adresse, modifie ces deux fichiers puis recompile.

## Ce que l'app fait

- Plein écran, sans barre d'adresse : ressemble à une vraie app.
- Micro accessible : « Hey Capzo » fonctionne.
- Les liens `tel:`, `sms:`, `mailto:`, `whatsapp:`, `https://maps…` ouvrent
  l'app correspondante au lieu de rester dans la WebView.
- Réception du **partage** depuis la galerie / une autre app (filtre SEND).
- Bouton retour Android = retour dans l'historique Capzo.
- Connexions **Google / GitHub / Meta / TikTok ouvertes dans le navigateur système**
  (obligatoire : ces services refusent les connexions dans une WebView), puis retour
  automatique dans l'app grâce au lien `capzo-ia.onrender.com`.
- Sélecteur de fichiers depuis la WebView (photos, vidéos, PDF…).
- Pour une installation sans Android Studio : utilise directement la **PWA** depuis
  Chrome → « Installer l'application » (recommandé, mises à jour automatiques).

## Limites honnêtes

- Ce n'est pas un assistant système : il ne peut pas se substituer à Siri/Google
  Assistant comme assistant par défaut de l'OS, ni lire l'écran d'une autre app.
- Pour un réveil permanent « Hey Capzo » écran éteint, il faudrait un service
  Android natif (microphone en arrière-plan) + autorisation spéciale ;
  ce squelette ne l'inclut pas.
- iOS : Apple ne permet pas l'installation d'APK. Sur iPhone, utilise le
  site en PWA (« Ajouter à l'écran d'accueil »), qui donne le même résultat
  visuel.
