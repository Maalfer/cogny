/* Modal global de Ajustes (tema, enlaces compartidos y claves de API).
   Vive fuera del vault porque se abre desde cualquier página. */
(function() {
  const $ = id => document.getElementById(id);
  function api(url, body) {
    return fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) }).then(r => r.json());
  }
  function esc(s) { return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }

  const iconOpenTab = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M19 19H5V5h7V3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7h-2v7zM14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3h-7z"/></svg>';
  const iconCopyLink = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>';
  const iconCheck = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>';
  const iconLock = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 17a2 2 0 0 0 2-2 2 2 0 0 0-2-2 2 2 0 0 0-2 2 2 2 0 0 0 2 2zm6-9a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V10a2 2 0 0 1 2-2h1V6a5 5 0 0 1 10 0v2h1zM12 3a3 3 0 0 0-3 3v2h6V6a3 3 0 0 0-3-3z"/></svg>';
  const iconGlobe = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm6.93 6h-2.95a15.7 15.7 0 0 0-1.38-3.56A8.03 8.03 0 0 1 18.93 8zM12 4.04c.83 1.2 1.48 2.53 1.91 3.96h-3.82c.43-1.43 1.08-2.76 1.91-3.96zM4.26 14a7.97 7.97 0 0 1 0-4h3.38a16.6 16.6 0 0 0 0 4H4.26zm.81 2h2.95c.32 1.25.78 2.45 1.38 3.56A7.99 7.99 0 0 1 5.07 16zm2.95-8H5.07a7.99 7.99 0 0 1 4.33-3.56A15.7 15.7 0 0 0 8.02 8zM12 19.96a15.7 15.7 0 0 1-1.91-3.96h3.82c-.43 1.43-1.08 2.76-1.91 3.96zM14.34 14H9.66a14.5 14.5 0 0 1 0-4h4.68a14.5 14.5 0 0 1 0 4zm.29 5.56c.6-1.11 1.06-2.31 1.38-3.56h2.95a7.99 7.99 0 0 1-4.33 3.56zM16.36 14a16.6 16.6 0 0 0 0-4h3.38a7.97 7.97 0 0 1 0 4h-3.38z"/></svg>';
  const iconTrash = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M6 19a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>';

  /* ---- Tema ---- */
  const themePicker = $('settings-theme-picker');
  if (themePicker) {
    themePicker.addEventListener('click', async e => {
      const btn = e.target.closest('.pf-theme-btn');
      if (!btn || btn.classList.contains('active')) return;
      const theme = btn.dataset.theme;
      themePicker.querySelectorAll('.pf-theme-btn').forEach(b => b.classList.toggle('active', b === btn));
      document.documentElement.dataset.theme = theme;
      document.cookie = 'bh_theme=' + theme + '; max-age=' + (2 * 365 * 86400) + '; path=/; samesite=lax';
      try { await api('/api/profile/set-theme', { theme }); } catch (_) {}
    });
  }

  /* ---- Enlaces compartidos ---- */
  function renderSharedLinksList(shares) {
    const list = $('shared-links-list'); if (!list) return;
    if (!shares.length) { list.innerHTML = ''; $('shared-links-empty').style.display = 'flex'; return; }
    $('shared-links-empty').style.display = 'none';
    list.innerHTML = shares.map(s => `
      <div class="shared-link-item" data-path="${esc(s.path)}" data-url="${esc(s.url)}">
        <div class="sli-info">
          <div class="sli-name">${esc(s.name)}</div>
          <div class="sli-meta">${s.has_password ? iconLock : iconGlobe}<span>${s.has_password ? 'Con contraseña' : 'Público'} · ${esc(s.path)}</span></div>
        </div>
        <div class="sli-actions">
          <button class="sli-open" title="Abrir esta nota">${iconOpenTab}</button>
          <button class="sli-copy" title="Copiar enlace">${iconCopyLink}</button>
          <button class="sli-revoke" title="Dejar de compartir">${iconTrash}</button>
        </div>
      </div>`).join('');
  }

  async function loadSharedLinks() {
    const loading = $('shared-links-loading'), empty = $('shared-links-empty'), list = $('shared-links-list');
    if (!list) return;
    loading.style.display = ''; list.innerHTML = ''; empty.style.display = 'none';
    try {
      const res = await fetch('/api/notes/share/list').then(r => r.json());
      renderSharedLinksList(res.shares || []);
    } catch (e) { empty.style.display = 'flex'; }
    loading.style.display = 'none';
  }

  const sharedList = $('shared-links-list');
  if (sharedList) {
    sharedList.addEventListener('click', async e => {
      const item = e.target.closest('.shared-link-item'); if (!item) return;
      const path = item.dataset.path, url = item.dataset.url;
      if (e.target.closest('.sli-open')) {
        closeSettingsModal();
        if (typeof window.openInNewTab === 'function') window.openInNewTab(path);
        else location.href = '/?open=' + encodeURIComponent(path);
      } else if (e.target.closest('.sli-copy')) {
        const btn = e.target.closest('.sli-copy');
        try { await navigator.clipboard.writeText(url); }
        catch (_) {
          const ta = document.createElement('textarea'); ta.value = url; ta.style.cssText = 'position:fixed;opacity:0';
          document.body.appendChild(ta); ta.select(); try { document.execCommand('copy'); } catch (__) {} ta.remove();
        }
        const orig = btn.innerHTML; btn.innerHTML = iconCheck; btn.classList.add('copied');
        setTimeout(() => { btn.innerHTML = orig; btn.classList.remove('copied'); }, 1400);
      } else if (e.target.closest('.sli-revoke')) {
        if (!confirm('¿Dejar de compartir esta nota? El enlace actual dejará de funcionar.')) return;
        const res = await api('/api/notes/share/revoke', { path });
        if (res.error) { alert(res.error); return; }
        item.remove();
        if (!sharedList.children.length) $('shared-links-empty').style.display = 'flex';
      }
    });
  }

  /* ---- Claves de API ---- */
  const iconKey = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12.65 10A5.99 5.99 0 0 0 7 6a6 6 0 1 0 5.65 8H17v4h4v-4h2v-4H12.65zM7 15a3 3 0 1 1 0-6 3 3 0 0 1 0 6z"/></svg>';

  function fmtDate(iso) {
    if (!iso) return 'sin usar';
    const d = new Date(iso);
    return d.toLocaleDateString('es-ES', { day: '2-digit', month: 'short', year: 'numeric' });
  }

  function renderApiKeys(keys) {
    const list = $('apikeys-list'); if (!list) return;
    if (!keys.length) { list.innerHTML = ''; $('apikeys-empty').style.display = 'flex'; return; }
    $('apikeys-empty').style.display = 'none';
    list.innerHTML = keys.map(k => `
      <div class="shared-link-item" data-id="${k.id}">
        <div class="sli-info">
          <div class="sli-name">${esc(k.name)}${k.read_only ? ' <span class="apikey-tag">solo lectura</span>' : ''}</div>
          <div class="sli-meta">${iconKey}<span>${esc(k.masked)} · usada ${fmtDate(k.last_used_at)}</span></div>
        </div>
        <div class="sli-actions">
          <button class="sli-revoke apikey-revoke" title="Revocar esta clave">${iconTrash}</button>
        </div>
      </div>`).join('');
  }

  async function loadApiKeys() {
    const loading = $('apikeys-loading'), empty = $('apikeys-empty'), list = $('apikeys-list');
    if (!list) return;
    loading.style.display = ''; list.innerHTML = ''; empty.style.display = 'none';
    try {
      const res = await fetch('/api/apikeys/list').then(r => r.json());
      renderApiKeys(res.keys || []);
    } catch (e) { empty.style.display = 'flex'; }
    loading.style.display = 'none';
  }

  const createBtn = $('apikey-create');
  if (createBtn) {
    createBtn.addEventListener('click', async () => {
      createBtn.disabled = true;
      const prev = createBtn.textContent;
      createBtn.textContent = 'Generando…';
      try {
        const res = await api('/api/apikeys/create', {
          name: $('apikey-name').value.trim(),
          read_only: $('apikey-readonly').checked,
        });
        if (res.error) { alert(res.error); return; }
        $('apikey-name').value = ''; $('apikey-readonly').checked = false;
        $('apikey-new-secret').textContent = res.key.secret;
        $('apikey-new').style.display = '';
        await loadApiKeys();
      } catch (e) { alert('No se pudo generar la clave'); }
      finally { createBtn.disabled = false; createBtn.textContent = prev; }
    });
  }

  const newCopy = $('apikey-new-copy');
  if (newCopy) {
    newCopy.innerHTML = iconCopyLink;
    newCopy.addEventListener('click', async () => {
      const val = $('apikey-new-secret').textContent;
      try { await navigator.clipboard.writeText(val); }
      catch (_) {
        const ta = document.createElement('textarea'); ta.value = val; ta.style.cssText = 'position:fixed;opacity:0';
        document.body.appendChild(ta); ta.select(); try { document.execCommand('copy'); } catch (__) {} ta.remove();
      }
      newCopy.innerHTML = iconCheck; newCopy.classList.add('copied');
      setTimeout(() => { newCopy.innerHTML = iconCopyLink; newCopy.classList.remove('copied'); }, 1400);
    });
  }

  const keysList = $('apikeys-list');
  if (keysList) {
    keysList.addEventListener('click', async e => {
      const item = e.target.closest('.shared-link-item'); if (!item) return;
      if (!e.target.closest('.apikey-revoke')) return;
      if (!confirm('¿Revocar esta clave? Todo lo que la use dejará de funcionar al instante.')) return;
      const res = await api('/api/apikeys/revoke', { id: Number(item.dataset.id) });
      if (res.error) { alert(res.error); return; }
      item.remove();
      if (!keysList.children.length) $('apikeys-empty').style.display = 'flex';
    });
  }

  /* ---- Abrir / cerrar modal ---- */
  function openSettingsModal() {
    $('settings-modal').classList.add('show');
    loadSharedLinks();
    loadApiKeys();
    // La clave recién creada no sobrevive a cerrar el modal: si el usuario no
    // la copió, ya no hay forma de recuperarla y dejarla ahí sólo confunde.
    const fresh = $('apikey-new');
    if (fresh) { fresh.style.display = 'none'; $('apikey-new-secret').textContent = ''; }
    const drawer = $('hb-drawer'), overlay = $('hb-overlay'), toggle = $('hb-toggle');
    if (drawer && drawer.classList.contains('open')) {
      drawer.classList.remove('open');
      if (overlay) overlay.classList.remove('show');
      if (toggle) toggle.setAttribute('aria-expanded', 'false');
      document.body.style.overflow = '';
    }
  }
  function closeSettingsModal() { $('settings-modal').classList.remove('show'); }
  window.openSettingsModal = openSettingsModal;

  document.addEventListener('click', e => {
    if (e.target.closest('.js-open-settings')) { e.preventDefault(); openSettingsModal(); }
  });
  const closeBtn = $('settings-modal-close'); if (closeBtn) closeBtn.addEventListener('click', closeSettingsModal);
  const backdrop = $('settings-modal');
  if (backdrop) backdrop.addEventListener('click', e => { if (e.target === backdrop) closeSettingsModal(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && backdrop && backdrop.classList.contains('show')) closeSettingsModal(); });
})();
