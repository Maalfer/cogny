/* Mejoras PWA: theme-color según el tema y altura útil con el teclado móvil. */
(function () {
  'use strict';
  var root = document.documentElement;

  /* 1. theme-color sigue al tema activo (barra de estado de Android/iOS). */
  function syncThemeColor() {
    var bg = getComputedStyle(root).getPropertyValue('--bg').trim();
    if (!bg) return;
    var metas = document.querySelectorAll('meta[name="theme-color"]');
    if (!metas.length) {
      var m = document.createElement('meta');
      m.name = 'theme-color';
      document.head.appendChild(m);
      metas = [m];
    }
    metas.forEach(function (m) { m.setAttribute('content', bg); });
  }
  syncThemeColor();
  new MutationObserver(syncThemeColor)
    .observe(root, { attributes: true, attributeFilter: ['data-theme'] });

  /* 2. Altura visible real: con el teclado abierto, 100dvh no siempre encoge
        (iOS PWA). Se publica --app-h y la clase kb-open en <html>. */
  var vv = window.visualViewport;
  if (!vv) return;
  var raf = 0;
  function update() {
    raf = 0;
    var h = Math.round(vv.height);
    var kb = window.innerHeight - h > 120;
    root.style.setProperty('--app-h', h + 'px');
    root.classList.toggle('kb-open', kb);
    if (kb && vv.offsetTop > 0) window.scrollTo(0, 0);
  }
  function schedule() { if (!raf) raf = requestAnimationFrame(update); }
  vv.addEventListener('resize', schedule);
  vv.addEventListener('scroll', schedule);
  update();
})();
