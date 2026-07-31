/* Página de Ajustes (/settings/): tema, enlaces compartidos y claves de API.

   Antes esto era un modal global inyectado en TODAS las páginas (base.html +
   settings-modal.js). Ahora es una página propia, así que este script se carga
   sólo aquí y no hay nada que abrir ni cerrar: al entrar se pinta todo.

   Los avisos van al toast de la página (#pf-toast, mismo estilo que el perfil)
   en lugar de a alert(). Las confirmaciones destructivas sí siguen con
   confirm(), igual que en el perfil: son acciones que no tienen deshacer. */
(function () {
  const $ = id => document.getElementById(id);

  function api(url, body) {
    return fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {}),
    }).then(r => r.json());
  }
  function esc(s) {
    return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  /* ── Toast ── */
  let toastTimer;
  function toast(text, ok = true) {
    const t = $('pf-toast');
    if (!t) return;
    t.textContent = text;
    t.className = 'pfx-toast show ' + (ok ? 'ok' : 'err');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => t.classList.remove('show'), 3000);
  }

  /* Copia al portapapeles con respaldo para navegadores sin API segura
     (o sin HTTPS), y confirma en el propio botón. */
  async function copyToClipboard(text) {
    try {
      await navigator.clipboard.writeText(text);
    } catch (_) {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.cssText = 'position:fixed;opacity:0';
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand('copy'); } catch (__) {}
      ta.remove();
    }
  }
  function flashCopied(btn, restoreHTML) {
    const prev = restoreHTML !== undefined ? restoreHTML : btn.innerHTML;
    btn.innerHTML = iconCheck;
    btn.classList.add('copied');
    setTimeout(() => { btn.innerHTML = prev; btn.classList.remove('copied'); }, 1400);
  }

  const iconOpenTab = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M19 19H5V5h7V3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7h-2v7zM14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3h-7z"/></svg>';
  const iconCopyLink = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>';
  const iconCheck = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>';
  const iconLock = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 17a2 2 0 0 0 2-2 2 2 0 0 0-2-2 2 2 0 0 0-2 2 2 2 0 0 0 2 2zm6-9a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V10a2 2 0 0 1 2-2h1V6a5 5 0 0 1 10 0v2h1zM12 3a3 3 0 0 0-3 3v2h6V6a3 3 0 0 0-3-3z"/></svg>';
  const iconGlobe = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm6.93 6h-2.95a15.7 15.7 0 0 0-1.38-3.56A8.03 8.03 0 0 1 18.93 8zM12 4.04c.83 1.2 1.48 2.53 1.91 3.96h-3.82c.43-1.43 1.08-2.76 1.91-3.96zM4.26 14a7.97 7.97 0 0 1 0-4h3.38a16.6 16.6 0 0 0 0 4H4.26zm.81 2h2.95c.32 1.25.78 2.45 1.38 3.56A7.99 7.99 0 0 1 5.07 16zm2.95-8H5.07a7.99 7.99 0 0 1 4.33-3.56A15.7 15.7 0 0 0 8.02 8zM12 19.96a15.7 15.7 0 0 1-1.91-3.96h3.82c-.43 1.43-1.08 2.76-1.91 3.96zM14.34 14H9.66a14.5 14.5 0 0 1 0-4h4.68a14.5 14.5 0 0 1 0 4zm.29 5.56c.6-1.11 1.06-2.31 1.38-3.56h2.95a7.99 7.99 0 0 1-4.33 3.56zM16.36 14a16.6 16.6 0 0 0 0-4h3.38a7.97 7.97 0 0 1 0 4h-3.38z"/></svg>';
  const iconTrash = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M6 19a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>';
  const iconKey = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12.65 10A5.99 5.99 0 0 0 7 6a6 6 0 1 0 5.65 8H17v4h4v-4h2v-4H12.65zM7 15a3 3 0 1 1 0-6 3 3 0 0 1 0 6z"/></svg>';

  function lastUsed(iso) {
    if (!iso) return 'sin usar todavía';
    return 'usada el ' + new Date(iso).toLocaleDateString('es-ES',
      { day: '2-digit', month: 'short', year: 'numeric' });
  }

  /* ════════════════════════════ Tema ════════════════════════════ */
  const themePicker = $('settings-theme-picker');
  if (themePicker) {
    themePicker.addEventListener('click', async e => {
      const btn = e.target.closest('.pf-theme-btn');
      if (!btn || btn.classList.contains('active')) return;
      const theme = btn.dataset.theme;
      themePicker.querySelectorAll('.pf-theme-btn').forEach(b => {
        b.classList.toggle('active', b === btn);
        b.setAttribute('aria-checked', b === btn ? 'true' : 'false');
      });
      document.documentElement.dataset.theme = theme;
      // La cookie hace que la próxima carga pinte ya con el tema correcto,
      // sin esperar a la sesión (ver el script inline de base.html).
      document.cookie = 'bh_theme=' + theme + '; max-age=' + (2 * 365 * 86400) + '; path=/; samesite=lax';
      try {
        const res = await api('/api/profile/set-theme', { theme });
        toast(res && res.error ? res.error : 'Tema aplicado', !(res && res.error));
      } catch (_) {
        toast('Tema aplicado aquí, pero no se ha podido guardar', false);
      }
    });
  }

  /* ══════════════════════ Enlaces compartidos ══════════════════════ */
  const sharedList = $('shared-links-list');

  function renderSharedLinks(shares) {
    if (!shares.length) {
      sharedList.innerHTML = '';
      $('shared-links-empty').style.display = 'flex';
      return;
    }
    $('shared-links-empty').style.display = 'none';
    sharedList.innerHTML = shares.map(s => `
      <div class="stx-item" data-path="${esc(s.path)}" data-url="${esc(s.url)}">
        <div class="stx-item-info">
          <div class="stx-item-name"><span>${esc(s.name)}</span></div>
          <div class="stx-item-meta">${s.has_password ? iconLock : iconGlobe}<span>${s.has_password ? 'Con contraseña' : 'Público'} · ${esc(s.path)}</span></div>
        </div>
        <div class="stx-item-actions">
          <button class="stx-btn stx-open" title="Abrir esta nota" aria-label="Abrir la nota ${esc(s.name)}">${iconOpenTab}</button>
          <button class="stx-btn stx-copy" title="Copiar enlace" aria-label="Copiar el enlace de ${esc(s.name)}">${iconCopyLink}</button>
          <button class="stx-btn stx-revoke" title="Dejar de compartir" aria-label="Dejar de compartir ${esc(s.name)}">${iconTrash}</button>
        </div>
      </div>`).join('');
  }

  async function loadSharedLinks() {
    if (!sharedList) return;
    const loading = $('shared-links-loading');
    loading.style.display = '';
    sharedList.innerHTML = '';
    $('shared-links-empty').style.display = 'none';
    try {
      const res = await fetch('/api/notes/share/list').then(r => r.json());
      renderSharedLinks(res.shares || []);
    } catch (_) {
      $('shared-links-empty').style.display = 'flex';
      toast('No se han podido cargar los enlaces compartidos', false);
    }
    loading.style.display = 'none';
  }

  if (sharedList) {
    sharedList.addEventListener('click', async e => {
      const item = e.target.closest('.stx-item');
      if (!item) return;
      const path = item.dataset.path, url = item.dataset.url;

      if (e.target.closest('.stx-open')) {
        // La bóveda abre la nota que le llegue en ?open=… (ver notes.js).
        location.href = '/?open=' + encodeURIComponent(path);

      } else if (e.target.closest('.stx-copy')) {
        const btn = e.target.closest('.stx-copy');
        await copyToClipboard(url);
        flashCopied(btn, iconCopyLink);
        toast('Enlace copiado');

      } else if (e.target.closest('.stx-revoke')) {
        if (!confirm('¿Dejar de compartir esta nota? El enlace actual dejará de funcionar.')) return;
        const res = await api('/api/notes/share/revoke', { path });
        if (res.error) { toast(res.error, false); return; }
        item.remove();
        if (!sharedList.children.length) $('shared-links-empty').style.display = 'flex';
        toast('Nota despublicada');
      }
    });
  }

  /* ═══════════════════════ Claves de API ═══════════════════════ */
  const keysList = $('apikeys-list');

  function renderApiKeys(keys) {
    if (!keys.length) {
      keysList.innerHTML = '';
      $('apikeys-empty').style.display = 'flex';
      return;
    }
    $('apikeys-empty').style.display = 'none';
    keysList.innerHTML = keys.map(k => `
      <div class="stx-item" data-id="${k.id}">
        <div class="stx-item-info">
          <div class="stx-item-name"><span>${esc(k.name)}</span>${k.read_only ? '<span class="stx-tag">sólo lectura</span>' : ''}</div>
          <div class="stx-item-meta">${iconKey}<span>${esc(k.masked)} · ${lastUsed(k.last_used_at)}</span></div>
        </div>
        <div class="stx-item-actions">
          <button class="stx-btn stx-revoke apikey-revoke" title="Revocar esta clave" aria-label="Revocar la clave ${esc(k.name)}">${iconTrash}</button>
        </div>
      </div>`).join('');
  }

  async function loadApiKeys() {
    if (!keysList) return;
    const loading = $('apikeys-loading');
    loading.style.display = '';
    keysList.innerHTML = '';
    $('apikeys-empty').style.display = 'none';
    try {
      const res = await fetch('/api/apikeys/list').then(r => r.json());
      renderApiKeys(res.keys || []);
    } catch (_) {
      $('apikeys-empty').style.display = 'flex';
      toast('No se han podido cargar las claves', false);
    }
    loading.style.display = 'none';
  }

  /* Permisos de la clave nueva: mismo selector de dos opciones que usa el
     perfil para los accesos invitados. */
  let newKeyReadOnly = false;
  const perm = $('apikey-perm');
  if (perm) {
    perm.addEventListener('click', e => {
      const btn = e.target.closest('.acc-perm-btn');
      if (!btn) return;
      newKeyReadOnly = btn.dataset.readonly === '1';
      perm.querySelectorAll('.acc-perm-btn').forEach(b => {
        b.classList.toggle('active', b === btn);
        b.setAttribute('aria-checked', b === btn ? 'true' : 'false');
      });
    });
  }

  const createBtn = $('apikey-create');
  if (createBtn) {
    createBtn.addEventListener('click', async () => {
      const label = createBtn.querySelector('span');
      const prev = label.textContent;
      createBtn.disabled = true;
      label.textContent = 'Generando…';
      try {
        const res = await api('/api/apikeys/create', {
          name: $('apikey-name').value.trim(),
          read_only: newKeyReadOnly,
        });
        if (res.error) { toast(res.error, false); return; }
        $('apikey-name').value = '';
        $('apikey-new-secret').textContent = res.key.secret;
        $('apikey-new').style.display = '';
        await loadApiKeys();
        toast('Clave generada — cópiala ahora');
      } catch (_) {
        toast('No se pudo generar la clave', false);
      } finally {
        createBtn.disabled = false;
        label.textContent = prev;
      }
    });
    $('apikey-name').addEventListener('keydown', e => { if (e.key === 'Enter') createBtn.click(); });
  }

  const newCopy = $('apikey-new-copy');
  if (newCopy) {
    newCopy.innerHTML = iconCopyLink;
    newCopy.addEventListener('click', async () => {
      await copyToClipboard($('apikey-new-secret').textContent);
      flashCopied(newCopy, iconCopyLink);
      toast('Clave copiada');
    });
  }

  if (keysList) {
    keysList.addEventListener('click', async e => {
      const item = e.target.closest('.stx-item');
      if (!item || !e.target.closest('.apikey-revoke')) return;
      if (!confirm('¿Revocar esta clave? Todo lo que la use dejará de funcionar al instante.')) return;
      const res = await api('/api/apikeys/revoke', { id: Number(item.dataset.id) });
      if (res.error) { toast(res.error, false); return; }
      item.remove();
      if (!keysList.children.length) $('apikeys-empty').style.display = 'flex';
      toast('Clave revocada');
    });
  }

  /* ═══════════════ Bóveda pública (/conocimiento) ═══════════════ */

  const knCard = $('kn-card');

  function knSetEnabledUI(on) {
    $('kn-enabled').checked = on;
    $('kn-enabled-label').textContent = on ? 'Activada' : 'Desactivada';
    knCard.classList.toggle('is-on', on);
    // El cuerpo sólo estorba cuando está apagada: no hay nada que configurar
    // hasta que se enciende.
    $('kn-body').hidden = !on;
  }

  function knFillConfig(cfg) {
    knSetEnabledUI(!!cfg.enabled);
    $('kn-domains').value = cfg.allowed_domains || '';
    $('kn-days').value = cfg.grant_days;
    $('kn-url').textContent = cfg.url || '';
  }

  async function knSave(patch, okMsg) {
    const res = await api('/api/knowledge/config/save', patch);
    if (res.error) { toast(res.error, false); return null; }
    knFillConfig(res);
    if (okMsg) toast(okMsg);
    return res;
  }

  function knRenderLinks(links) {
    const list = $('kn-links');
    if (!links.length) {
      list.innerHTML = '';
      $('kn-links-empty').style.display = 'flex';
      return;
    }
    $('kn-links-empty').style.display = 'none';
    list.innerHTML = links.map(l => `
      <div class="stx-item" data-id="${l.id}" data-url="${esc(l.url)}">
        <div class="stx-item-info">
          <div class="stx-item-name"><span>${esc(l.name || 'Enlace maestro')}</span></div>
          <div class="stx-item-meta">${iconKey}<span>${l.visits} ${l.visits === 1 ? 'visita' : 'visitas'} · ${lastUsed(l.last_used_at)}</span></div>
        </div>
        <div class="stx-item-actions">
          <button class="stx-btn kn-link-copy" title="Copiar enlace" aria-label="Copiar el enlace de ${esc(l.name || 'este enlace maestro')}">${iconCopyLink}</button>
          <button class="stx-btn stx-revoke kn-link-revoke" title="Revocar" aria-label="Revocar el enlace de ${esc(l.name || 'este enlace maestro')}">${iconTrash}</button>
        </div>
      </div>`).join('');
  }

  async function knLoadLinks() {
    const loading = $('kn-links-loading');
    loading.style.display = '';
    $('kn-links').innerHTML = '';
    $('kn-links-empty').style.display = 'none';
    try {
      const res = await fetch('/api/knowledge/links').then(r => r.json());
      knRenderLinks(res.links || []);
    } catch (_) {
      $('kn-links-empty').style.display = 'flex';
      toast('No se han podido cargar los enlaces maestros', false);
    }
    loading.style.display = 'none';
  }

  if (knCard) {
    $('kn-enabled').addEventListener('change', async e => {
      const on = e.target.checked;
      knSetEnabledUI(on);   // respuesta inmediata; si falla, knFillConfig lo revierte
      await knSave({ enabled: on },
                   on ? 'Bóveda pública activada' : 'Bóveda pública desactivada');
      if (on) knLoadLinks();
    });

    $('kn-save').addEventListener('click', async () => {
      const btn = $('kn-save'), label = btn.querySelector('span');
      const prev = label.textContent;
      btn.disabled = true; label.textContent = 'Guardando…';
      await knSave({
        allowed_domains: $('kn-domains').value,
        grant_days: Number($('kn-days').value),
      }, 'Ajustes guardados');
      btn.disabled = false; label.textContent = prev;
    });

    $('kn-url-copy').innerHTML = iconCopyLink;
    $('kn-url-copy').addEventListener('click', async () => {
      await copyToClipboard($('kn-url').textContent);
      flashCopied($('kn-url-copy'), iconCopyLink);
      toast('Enlace copiado');
    });

    $('kn-link-create').addEventListener('click', async () => {
      const btn = $('kn-link-create'), label = btn.querySelector('span');
      const prev = label.textContent;
      btn.disabled = true; label.textContent = 'Creando…';
      try {
        const res = await api('/api/knowledge/links/create', { name: $('kn-link-name').value.trim() });
        if (res.error) { toast(res.error, false); return; }
        $('kn-link-name').value = '';
        await knLoadLinks();
        await copyToClipboard(res.link.url);
        toast('Enlace maestro creado y copiado');
      } catch (_) {
        toast('No se pudo crear el enlace', false);
      } finally {
        btn.disabled = false; label.textContent = prev;
      }
    });
    $('kn-link-name').addEventListener('keydown', e => { if (e.key === 'Enter') $('kn-link-create').click(); });

    $('kn-links').addEventListener('click', async e => {
      const item = e.target.closest('.stx-item');
      if (!item) return;
      if (e.target.closest('.kn-link-copy')) {
        const btn = e.target.closest('.kn-link-copy');
        await copyToClipboard(item.dataset.url);
        flashCopied(btn, iconCopyLink);
        toast('Enlace copiado');
      } else if (e.target.closest('.kn-link-revoke')) {
        if (!confirm('¿Revocar este enlace maestro? Dejará de funcionar al instante, ' +
                     'también para quien ya hubiera entrado con él.')) return;
        const res = await api('/api/knowledge/links/revoke', { id: Number(item.dataset.id) });
        if (res.error) { toast(res.error, false); return; }
        item.remove();
        if (!$('kn-links').children.length) $('kn-links-empty').style.display = 'flex';
        toast('Enlace maestro revocado');
      }
    });
  }

  async function knLoad() {
    if (!knCard) return;
    try {
      const cfg = await fetch('/api/knowledge/config').then(r => r.json());
      knFillConfig(cfg);
      if (cfg.enabled) knLoadLinks();
    } catch (_) {
      toast('No se ha podido cargar la bóveda pública', false);
    }
  }

  /* ── Arranque ── */
  loadSharedLinks();
  loadApiKeys();
  knLoad();
})();
