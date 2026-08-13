(function () {
  const CAN_WRITE = !!window.PIZARRA_CAN_WRITE;
  const grid = document.getElementById('pz-grid');
  const empty = document.getElementById('pz-empty');
  const newBtn = document.getElementById('pz-new');

  function fmtDate(unixSeconds) {
    return new Date(unixSeconds * 1000).toLocaleString('es-ES', {
      day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit',
    });
  }

  async function api(url, body) {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {}),
    });
    return res.json();
  }

  function cardActionBtn(title, svg, onClick) {
    const b = document.createElement('button');
    b.type = 'button';
    b.title = title;
    b.setAttribute('aria-label', title);
    b.innerHTML = svg;
    b.addEventListener('click', (e) => { e.stopPropagation(); onClick(); });
    return b;
  }

  const ICON_RENAME = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg>';
  const ICON_DUP = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M16 1H4a2 2 0 0 0-2 2v14h2V3h12V1zm3 4H8a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2zm0 16H8V7h11v14z"/></svg>';
  const ICON_DELETE = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M6 19a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>';
  const ICON_BOARD = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M20 2H4a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h4l-1 3v1h10v-1l-1-3h4a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2zm0 14H4V4h16v12z"/><path d="M7.5 13.5 10 10l2 2.5 3-4L18 13.5H7.5z"/></svg>';

  function renderCard(board) {
    const card = document.createElement('div');
    card.className = 'pz-card';
    card.tabIndex = 0;
    card.setAttribute('role', 'button');

    const thumb = document.createElement('div');
    thumb.className = 'pz-card-thumb';
    if (board.thumb_url) {
      const img = document.createElement('img');
      img.src = board.thumb_url;
      img.alt = '';
      img.loading = 'lazy';
      thumb.appendChild(img);
    } else {
      thumb.innerHTML = ICON_BOARD;
    }

    const body = document.createElement('div');
    body.className = 'pz-card-body';
    const name = document.createElement('div');
    name.className = 'pz-card-name';
    name.textContent = board.name;
    const date = document.createElement('div');
    date.className = 'pz-card-date';
    date.textContent = fmtDate(board.updated_at);
    body.append(name, date);

    card.append(thumb, body);

    const open = () => { window.location.href = '/pizarra/' + board.id + '/'; };
    card.addEventListener('click', open);
    card.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); } });

    if (CAN_WRITE) {
      const actions = document.createElement('div');
      actions.className = 'pz-card-actions';
      actions.append(
        cardActionBtn('Renombrar', ICON_RENAME, async () => {
          const next = prompt('Nuevo nombre de la pizarra', board.name);
          if (!next || !next.trim() || next.trim() === board.name) return;
          const res = await api('/api/pizarra/rename', { id: board.id, name: next.trim() });
          if (res.success) { board.name = res.name; name.textContent = res.name; }
        }),
        cardActionBtn('Duplicar', ICON_DUP, async () => {
          const res = await api('/api/pizarra/duplicate', { id: board.id });
          if (res.success) load();
        }),
        cardActionBtn('Eliminar', ICON_DELETE, async () => {
          if (!confirm('¿Eliminar «' + board.name + '»? No se puede deshacer.')) return;
          const res = await api('/api/pizarra/delete', { id: board.id });
          if (res.success) card.remove();
        }),
      );
      card.appendChild(actions);
    }

    return card;
  }

  async function load() {
    const res = await fetch('/api/pizarra/list');
    const data = await res.json();
    const boards = data.boards || [];
    grid.querySelectorAll('.pz-card').forEach((n) => n.remove());
    boards.forEach((b) => grid.appendChild(renderCard(b)));
    empty.classList.toggle('hidden', boards.length > 0);
  }

  if (newBtn) {
    newBtn.addEventListener('click', async () => {
      newBtn.disabled = true;
      try {
        const res = await api('/api/pizarra/create', {});
        if (res.success) window.location.href = '/pizarra/' + res.id + '/';
      } finally {
        newBtn.disabled = false;
      }
    });
  }

  load();
})();
