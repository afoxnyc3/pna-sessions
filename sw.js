/* Mission Control — Service Worker
   Strategy: Network-first for manifest.json (always fresh),
             Cache-first for static shell assets.
*/

const CACHE = 'mc-v1';

const SHELL = [
  '/',
  '/app.webmanifest',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
];

/* ── Install: pre-cache the shell ── */
self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(SHELL))
  );
  self.skipWaiting();
});

/* ── Activate: purge old caches ── */
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

/* ── Fetch strategy ── */
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);

  // manifest.json (artifact registry) — network first, fall back to cache
  if (url.pathname === '/manifest.json') {
    e.respondWith(
      fetch(e.request)
        .then(res => {
          const clone = res.clone();
          caches.open(CACHE).then(c => c.put(e.request, clone));
          return res;
        })
        .catch(() => caches.match(e.request))
    );
    return;
  }

  // Shell assets — cache first
  if (SHELL.includes(url.pathname) || url.pathname.startsWith('/icons/')) {
    e.respondWith(
      caches.match(e.request).then(cached => {
        if (cached) return cached;
        return fetch(e.request).then(res => {
          const clone = res.clone();
          caches.open(CACHE).then(c => c.put(e.request, clone));
          return res;
        });
      })
    );
    return;
  }

  // Everything else — network only (design docs, session pages, etc. stay fresh)
  // No caching for HTML pages — they update frequently and Vercel serves them fast
});
