/* Capzo IA — service worker minimal (installation + coque hors ligne) */
const CACHE = "capzo-v12";
const COQUE = [
  "/",
  "/manifest.webmanifest",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
  "/static/icons/qr-capzo.png"
];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE)
      .then((c) => Promise.all(COQUE.map((u) => c.add(u).catch(() => null))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((cles) => Promise.all(cles.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);

  // Jamais de cache pour l'API : réponses toujours fraîches.
  if (url.origin === self.location.origin && url.pathname.startsWith("/api/")) return;

  // Page : réseau d'abord, coque visible en secours (jamais de page blanche).
  if (req.mode === "navigate") {
    e.respondWith(
      fetch(req).then((rep) => {
        if (rep && rep.ok) {
          const copie = rep.clone();
          caches.open(CACHE).then((c) => c.put("/", copie));
        }
        return rep;
      }).catch(() =>
        caches.match("/").then((hit) =>
          hit && hit.ok ? hit : new Response(
            "<!doctype html><html lang=fr><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>Capzo IA — hors ligne</title><body style='font-family:system-ui;background:#0f172a;color:#f8fafc;padding:24px;line-height:1.6'><h1>Capzo IA</h1><p>Pas de connexion. Reconnecte-toi au Wi-Fi ou aux données mobiles, puis réessaie.</p><p style='opacity:.7'>Le serveur doit rester allumé à la maison.</p></body></html>",
            { status: 503, headers: { "Content-Type": "text/html; charset=utf-8" } }
          )
        )
      )
    );
    return;
  }

  // Fichiers statiques : cache d'abord.
  if (url.origin === self.location.origin && url.pathname.startsWith("/static/")) {
    e.respondWith(
      caches.match(req).then((hit) =>
        hit ||
        fetch(req).then((r) => {
          const copie = r.clone();
          caches.open(CACHE).then((c) => c.put(req, copie));
          return r;
        })
      )
    );
  }
});
