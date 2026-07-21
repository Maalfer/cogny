/* cogny Service Worker (app-shell precaching + stale-while-revalidate) */
const CACHE = 'cogny-v2';
const AV = '__ASSET_VERSION__'; // inyectado por Django service_worker view

// App shell: activos críticos precacheados en install.
// URLs versionadas → inmutables; la app arranca sin red en visitas siguientes.
const APP_SHELL = [
  '/manifest.json',
  `/static/css/app.css?v=${AV}`,
  `/static/notes/marked.min.js?v=${AV}`,
  `/static/notes/md-ctxmenu.js?v=${AV}`,
  `/static/vendor/codemirror/balucm.js?v=${AV}`,
  `/static/vendor/highlight.min.js?v=${AV}`,
  `/static/vendor/highlight-github-dark.min.css?v=${AV}`,
  `/static/vendor/katex/katex.min.js?v=${AV}`,
  `/static/vendor/katex/katex.min.css?v=${AV}`,
];

self.addEventListener('install', e => e.waitUntil(
  caches.open(CACHE)
    // allSettled: si falla un asset no bloquea el resto del precaching
    .then(cache => Promise.allSettled(APP_SHELL.map(url => cache.add(url))))
    .then(() => self.skipWaiting())
));

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        // Borrar todas las cachés legacy excepto la versión actual.
        keys.filter(k => k !== CACHE).map(k => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET') return;
  if (url.origin !== self.location.origin) return;

  // Las APIs del vault (árbol, contenido de notas, búsqueda, assets) siempre
  // van a red: cachearlas serviría notas desactualizadas tras editar.
  if (url.pathname.startsWith('/api/')) return;

  const isHtml = e.request.headers.get('Accept')?.includes('text/html');

  if (isHtml) {
    // Network-first: el HTML (login con CSRF, y el vault) SIEMPRE se pide a la
    // red. Servir una página de login cacheada llevaría un token CSRF caduco y
    // el POST daría 403. La caché sólo se usa como respaldo si no hay red.
    e.respondWith(
      fetch(e.request, { cache: 'no-store' })
        .then(res => { if (res.ok) caches.open(CACHE).then(c => c.put(e.request, res.clone())); return res; })
        .catch(() => caches.match(e.request))
    );
    return;
  }

  // Activos estáticos (CSS, JS, iconos, imágenes): cache-first.
  // URLs versionadas → inmutables; precacheados en install, siempre instantáneos.
  e.respondWith(
    caches.match(e.request).then(cached =>
      cached || fetch(e.request).then(res => {
        if (res.ok) caches.open(CACHE).then(c => c.put(e.request, res.clone()));
        return res;
      })
    )
  );
});
