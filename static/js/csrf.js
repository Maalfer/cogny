/* CSRF global: añade la cabecera X-CSRFToken a toda llamada fetch() del mismo
   origen que no sea segura. Evita repetirla en cada template y arregla los 403
   de los fetch de JSON/FormData.

   Se carga SIN defer y antes que ningún otro script: si el envoltorio se
   instalara después, las primeras peticiones de la página (el árbol del vault,
   por ejemplo) saldrían sin token. */
(function () {
  const csrf = (window.COGNY && window.COGNY.csrf) || '';
  if (!csrf || !window.fetch) return;
  const origFetch = window.fetch.bind(window);
  window.fetch = function (input, init) {
    init = init || {};
    const url = typeof input === 'string' ? input : (input && input.url) || '';
    const method = (init.method || (typeof input === 'object' && input.method) || 'GET').toUpperCase();
    const sameOrigin = url.startsWith('/') || url.startsWith(location.origin);
    if (sameOrigin && method !== 'GET' && method !== 'HEAD' && method !== 'OPTIONS') {
      const headers = new Headers(init.headers || {});
      if (!headers.has('X-CSRFToken')) headers.set('X-CSRFToken', csrf);
      init.headers = headers;
      if (!init.credentials) init.credentials = 'same-origin';
    }
    return origFetch(input, init);
  };
})();
