/* Service worker: makes the app installable + work offline (open + view last data).
   Strategy:
   - navigations  -> network-first, fall back to the cached app shell (opens offline)
   - static assets-> stale-while-revalidate (instant load, updates in background)
   - API GETs     -> network-first, fall back to the last cached response (view offline)
   POST/PUT/DELETE are never cached — writes always require the network.
*/
const CACHE = "bus-app-v5";
const CORE = ["/", "/index.html", "/manifest.webmanifest", "/icon-192.png", "/icon-512.png", "/apple-touch-icon.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(CORE)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// Show a notification when a push arrives (works even when the app is closed)
self.addEventListener("push", (e) => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch { d = {}; }
  e.waitUntil(
    self.registration.showNotification(d.title || "Bestimetravel", {
      body: d.body || "",
      icon: "/icon-192.png",
      badge: "/icon-192.png",
      data: { url: d.url || "/" },
    })
  );
});

// Open the app at the notification's target tab (navigate an already-open window there)
self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  const url = (e.notification.data && e.notification.data.url) || "/";
  e.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((wins) => {
      for (const w of wins) {
        if ("focus" in w) {
          if ("navigate" in w) { try { w.navigate(url).catch(() => {}); } catch {} }
          return w.focus();
        }
      }
      return self.clients.openWindow(url);
    })
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return; // never cache writes
  const url = new URL(req.url);

  // App shell — open offline
  if (req.mode === "navigate") {
    e.respondWith(
      fetch(req)
        .then((res) => { const copy = res.clone(); caches.open(CACHE).then((c) => c.put("/", copy)).catch(() => {}); return res; })
        .catch(() => caches.match("/").then((r) => r || caches.match("/index.html")))
    );
    return;
  }

  // Backend API — show last data when offline
  if (url.pathname.startsWith("/api/")) {
    e.respondWith(
      fetch(req)
        .then((res) => {
          // only keep real JSON answers (never an HTML "server waking up" page)
          const json = res && (res.headers.get("content-type") || "").includes("json");
          if (res && res.status === 200 && json) {
            const copy = res.clone();   // clone NOW: once the page reads the body it is too late
            caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
          }
          return res;
        })
        .catch(() => caches.match(req).then((r) => r || Response.error()))
    );
    return;
  }

  // Same-origin static assets — stale-while-revalidate
  if (url.origin === self.location.origin) {
    e.respondWith(
      caches.match(req).then((cached) => {
        const net = fetch(req)
          .then((res) => {
            if (res && res.status === 200) {
              const copy = res.clone();
              caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
            }
            return res;
          })
          .catch(() => cached);
        return cached || net;
      })
    );
  }
});
