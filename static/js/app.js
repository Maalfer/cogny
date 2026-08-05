/* Comportamiento común a todas las páginas: menú lateral y service worker.
   Va con `defer`, así que corre con el DOM ya parseado. */

/* ── Menú hamburguesa (móvil) ── */
(function () {
  const toggle = document.getElementById('hb-toggle');
  if (!toggle) return;
  const drawer = document.getElementById('hb-drawer');
  const overlay = document.getElementById('hb-overlay');
  const closeBtn = document.getElementById('hb-close');

  function open() {
    drawer.classList.add('open');
    overlay.classList.add('show');
    toggle.setAttribute('aria-expanded', 'true');
    document.body.style.overflow = 'hidden';
  }
  function close() {
    drawer.classList.remove('open');
    overlay.classList.remove('show');
    toggle.setAttribute('aria-expanded', 'false');
    document.body.style.overflow = '';
  }

  toggle.addEventListener('click', open);
  closeBtn.addEventListener('click', close);
  overlay.addEventListener('click', close);
  document.addEventListener('keydown', e => { if (e.key === 'Escape') close(); });
})();

/* ── Service worker ── */
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js').catch(() => {});
  /* Cuando un SW nuevo toma control (p.ej. tras purgar una caché vieja con un
     login CSRF caduco), recargar UNA vez para que la página venga ya fresca. */
  let reloaded = false;
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (reloaded) return;
    reloaded = true;
    // El export headless de la API (`?headless_pdf=1`, ver `pdf_headless.py`)
    // es una navegación de un solo uso desde un Chromium sin usuario detrás,
    // con un perfil siempre nuevo: el SW "toma control por primera vez" en
    // CADA export, y recargar aquí abortaría el render a medias — el export
    // nunca llegaría a dejar su resultado listo.
    if (new URLSearchParams(location.search).get('headless_pdf')) return;
    location.reload();
  });
}
