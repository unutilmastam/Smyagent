// SMY Agent service worker: caches the static app shell only.
// Never caches HTML pages or API responses (they contain business data).
const CACHE = "smy-shell-v3";
const SHELL = [
  "/static/app.css",
  "/static/app.js",
  "/static/vendor/htmx-2.0.4.min.js",
  "/static/icons/icon-192.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== self.location.origin) return;
  if (!SHELL.includes(url.pathname)) return; // everything else: network only
  // Network first, so a deploy ("SMY yangilash") reaches the phone at once; the cached
  // copy is only the offline fallback.
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(CACHE).then((c) => c.put(event.request, copy));
        }
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});
