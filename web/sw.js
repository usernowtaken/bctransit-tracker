/* Victoria Bus Radar V2.6 - offline UI shell only; live GPS is ALWAYS network-only. */
const APP_CACHE = 'victoria-bus-radar-shell-v2.6.0';
const SHELL = [
  '/', '/index.html', '/style.css?v=2.6', '/classic.css?v=2.6',
  '/classic-dark.css?v=2.6', '/mobile.css?v=2.6', '/app.js?v=2.6',
  '/pwa.js?v=2.6', '/manifest.webmanifest', '/favicon.svg',
  '/icons/icon-192.png', '/icons/icon-512.png', '/icons/maskable-512.png',
  '/icons/apple-touch-icon.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(APP_CACHE).then((cache) => cache.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(Promise.all([
    caches.keys().then((names) => Promise.all(names
      .filter((name) => name.startsWith('victoria-bus-radar-shell-') && name !== APP_CACHE)
      .map((name) => caches.delete(name)))),
    self.clients.claim()
  ]));
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return; // Tile imagery/CDN is NOT stored by the PWA.
  if (url.pathname.startsWith('/api/') || url.pathname === '/config.js') return;

  if (request.mode === 'navigate') {
    // Prefer current HTML; offline fallback still opens the app UI.
    event.respondWith(fetch(request).catch(async () =>
      (await caches.match('/index.html')) || Response.error()));
    return;
  }

  if (SHELL.includes(url.pathname + url.search) || SHELL.includes(url.pathname)) {
    event.respondWith(caches.match(request).then((hit) => hit || fetch(request)));
  }
});
