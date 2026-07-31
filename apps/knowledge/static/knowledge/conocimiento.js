/* Lector público de la bóveda (/conocimiento) — sólo lectura.
 *
 * Comparte el pipeline de Markdown "Obsidian-flavored" con notes.js y
 * shared.js (KaTeX, callouts, resaltado, tags, ==resaltado==, notas al pie),
 * pero se queda sólo con lo de leer: no hay editor, ni guardado, ni menús
 * contextuales, ni una sola llamada que escriba. Lo que aquí no existe no se
 * puede pedir.
 *
 * A diferencia de shared.js —que enseña UNA nota suelta y por eso corta los
 * wikilinks—, aquí la bóveda entera es pública, así que los enlaces internos
 * y las transclusiones ![[Otra nota]] SÍ se resuelven: es lo que hace que esto
 * se pueda leer como unos apuntes y no como una lista de ficheros.
 */
(function () {
  'use strict';

  const API = '/conocimiento/api';
  const $ = id => document.getElementById(id);
  const esc = s => (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;')
                            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');

  const IMG_EXT = ['jpg', 'jpeg', 'png', 'webp', 'gif', 'bmp', 'avif', 'ico', 'svg'];
  const MAX_EMBED_DEPTH = 3;

  const BY_PATH = new Map();   // ruta completa en minúsculas → item
  const BY_BASE = new Map();   // nombre de fichero (con y sin extensión) → item
  let TREE = [];
  let currentPath = '';

  const assetUrl = path => API + '/asset?path=' + encodeURIComponent(path);

  /* ════════════ Índice de ficheros ════════════ */

  function indexTree(items) {
    items.forEach(it => {
      if (it.type === 'folder') { indexTree(it.children || []); return; }
      BY_PATH.set(it.path.toLowerCase(), it);
      const base = it.path.split('/').pop().toLowerCase();
      if (!BY_BASE.has(base)) BY_BASE.set(base, it);
      const noExt = base.replace(/\.[^.]+$/, '');
      if (!BY_BASE.has(noExt)) BY_BASE.set(noExt, it);
    });
  }

  function findFileByName(name) {
    if (!name) return null;
    const clean = name.replace(/\\/g, '/').trim();
    const hit = BY_PATH.get(clean.toLowerCase());
    if (hit) return hit;
    const base = clean.split('/').pop().toLowerCase();
    return BY_BASE.get(base) || BY_BASE.get(base.replace(/\.[^.]+$/, '')) || null;
  }

  /* ════════════ Markdown ════════════ */

  const mathBlock = {
    name: 'mathBlock', level: 'block', start(s) { return s.indexOf('$$'); },
    tokenizer(src) { const m = /^\$\$([\s\S]+?)\$\$/.exec(src); if (m) return { type: 'mathBlock', raw: m[0], text: m[1] }; },
    renderer(t) { try { return katex.renderToString(t.text.trim(), { displayMode: true, throwOnError: false }); } catch (e) { return '<pre>' + esc(t.text) + '</pre>'; } },
  };
  const mathInline = {
    name: 'mathInline', level: 'inline', start(s) { return s.indexOf('$'); },
    tokenizer(src) { const m = /^\$(?!\s)((?:\\\$|[^$\n])+?)(?<!\s)\$(?!\d)/.exec(src); if (m) return { type: 'mathInline', raw: m[0], text: m[1] }; },
    renderer(t) { try { return katex.renderToString(t.text, { throwOnError: false }); } catch (e) { return esc(t.raw); } },
  };
  const embed = {
    name: 'embed', level: 'inline', start(s) { return s.indexOf('![['); },
    tokenizer(src) { const m = /^!\[\[([^\]\n]+?)\]\]/.exec(src); if (m) return { type: 'embed', raw: m[0], target: m[1] }; },
    // Se deja el marcador y lo resuelve postProcess(): las transclusiones de
    // notas necesitan un fetch, y el renderer de marked es síncrono.
    renderer(t) { return `<span class="internal-embed" data-target="${esc(t.target)}"></span>`; },
  };
  const wikilink = {
    name: 'wikilink', level: 'inline', start(s) { return s.indexOf('[['); },
    tokenizer(src) { const m = /^\[\[([^\]\n]+?)\]\]/.exec(src); if (m) return { type: 'wikilink', raw: m[0], target: m[1] }; },
    renderer(t) {
      const parts = t.target.split('|');
      const disp = (parts[1] || parts[0].split('#')[0]).trim();
      return `<span class="wikilink" data-target="${esc(t.target)}">${esc(disp)}</span>`;
    },
  };
  const highlightMark = {
    name: 'hl', level: 'inline', start(s) { return s.indexOf('=='); },
    tokenizer(src) { const m = /^==(?=\S)([\s\S]+?)==/.exec(src); if (m) return { type: 'hl', raw: m[0], tokens: this.lexer.inlineTokens(m[1]) }; },
    renderer(t) { return '<mark>' + this.parser.parseInline(t.tokens) + '</mark>'; },
  };
  const tag = {
    name: 'tag', level: 'inline', start(s) { const i = s.search(/#[A-Za-z]/); return i < 0 ? undefined : i; },
    tokenizer(src) { const m = /^#([A-Za-z0-9_/-]*[A-Za-z_/-][A-Za-z0-9_/-]*)/.exec(src); if (m) return { type: 'tag', raw: m[0], tag: m[1] }; },
    renderer(t) { return `<span class="tag-pill">#${esc(t.tag)}</span>`; },
  };
  const comment = {
    name: 'comment', level: 'inline', start(s) { return s.indexOf('%%'); },
    tokenizer(src) { const m = /^%%[\s\S]*?%%/.exec(src); if (m) return { type: 'comment', raw: m[0] }; },
    renderer() { return ''; },
  };
  marked.use({ gfm: true, breaks: true, extensions: [mathBlock, mathInline, embed, wikilink, highlightMark, tag, comment] });

  function parseFrontmatter(src) {
    const m = /^---\n([\s\S]*?)\n---\n?/.exec(src);
    if (!m) return { body: src, props: null };
    const props = [];
    m[1].split('\n').forEach(line => {
      const mm = /^([A-Za-z0-9_ -]+):\s*(.*)$/.exec(line);
      if (mm) props.push([mm[1].trim(), mm[2].trim()]);
    });
    return { body: src.slice(m[0].length), props: props.length ? props : null };
  }
  function extractFootnotes(src) {
    const defs = {};
    src = src.replace(/^\[\^([^\]]+)\]:\s?(.*)$/gm, (m, id, txt) => { defs[id] = txt; return ''; });
    if (!Object.keys(defs).length) return src;
    const order = [];
    src = src.replace(/\[\^([^\]]+)\]/g, (m, id) => {
      if (!(id in defs)) return m;
      if (!order.includes(id)) order.push(id);
      return `<sup class="fn-ref" id="fnref-${esc(id)}"><a href="#fn-${esc(id)}">[${order.indexOf(id) + 1}]</a></sup>`;
    });
    if (!order.length) return src;
    let foot = '\n\n<hr>\n<ol class="footnotes">';
    order.forEach(id => { foot += `<li id="fn-${esc(id)}">${esc(defs[id])} <a href="#fnref-${esc(id)}">↩</a></li>`; });
    return src + foot + '</ol>';
  }
  function extractSection(md, heading) {
    if (!heading) return md;
    const target = heading.replace(/^#*/, '').trim().toLowerCase();
    if (!target) return md;
    const lines = md.split('\n');
    let start = -1, level = 0;
    for (let i = 0; i < lines.length; i++) {
      const m = /^(#{1,6})\s+(.*)$/.exec(lines[i]);
      if (m && m[2].trim().toLowerCase() === target) { start = i; level = m[1].length; break; }
    }
    if (start < 0) return md;
    let end = lines.length;
    for (let i = start + 1; i < lines.length; i++) {
      const m = /^(#{1,6})\s+/.exec(lines[i]);
      if (m && m[1].length <= level) { end = i; break; }
    }
    return lines.slice(start, end).join('\n');
  }
  // Ver notes.js: mismo saneado, misma razón — esta vista además es pública
  // y sin autenticar (/conocimiento/), así que el payload correría contra
  // cualquier visitante que entre por dominio permitido o enlace maestro.
  const SANITIZE_CONFIG = {USE_PROFILES: {html: true, mathMl: true, svg: true}};

  function renderMarkdown(src) {
    const { body, props } = parseFrontmatter(src);
    let html = '';
    if (props) {
      html += '<div class="note-props"><table>';
      props.forEach(([k, v]) => { html += `<tr><th>${esc(k)}</th><td>${esc(v)}</td></tr>`; });
      html += '</table></div>';
    }
    return DOMPurify.sanitize(html + marked.parse(extractFootnotes(body)), SANITIZE_CONFIG);
  }

  /* ════════════ Post-proceso ════════════ */

  const CALLOUT_ICON = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2a10 10 0 100 20 10 10 0 000-20zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/></svg>';
  const COPY_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>';
  const CHECK_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>';

  function addCopyBtn(pre) {
    if (!pre || pre.querySelector('.code-copy')) return;
    const code = pre.querySelector('code'); if (!code) return;
    const btn = document.createElement('button');
    btn.className = 'code-copy'; btn.type = 'button';
    btn.title = 'Copiar'; btn.setAttribute('aria-label', 'Copiar código');
    btn.innerHTML = COPY_ICON;
    btn.addEventListener('mousedown', e => e.preventDefault());
    btn.addEventListener('click', async e => {
      e.preventDefault(); e.stopPropagation();
      try { await navigator.clipboard.writeText(code.textContent); }
      catch (_) {
        const ta = document.createElement('textarea'); ta.value = code.textContent;
        ta.style.cssText = 'position:fixed;opacity:0'; document.body.appendChild(ta);
        ta.select(); try { document.execCommand('copy'); } catch (__) {} ta.remove();
      }
      btn.classList.add('copied'); btn.innerHTML = CHECK_ICON; btn.title = '¡Copiado!';
      setTimeout(() => { btn.classList.remove('copied'); btn.innerHTML = COPY_ICON; btn.title = 'Copiar'; }, 1400);
    });
    pre.appendChild(btn);
  }

  let mermaidLoaded = false;
  async function renderMermaid(container) {
    const nodes = container.querySelectorAll('.mermaid');
    if (!nodes.length) return;
    if (!mermaidLoaded) {
      await new Promise((res, rej) => {
        const s = document.createElement('script');
        s.src = '/static/vendor/mermaid.min.js?v=' + window.COGNY.assetVersion;
        s.onload = res; s.onerror = rej; document.head.appendChild(s);
      }).catch(() => {});
      if (window.mermaid) { mermaid.initialize({ startOnLoad: false, theme: 'dark' }); mermaidLoaded = true; }
    }
    try { window.mermaid && await mermaid.run({ nodes: [...nodes] }); } catch (e) {}
  }

  function resolveEmbed(el, depth) {
    const raw = el.dataset.target || '';
    const [namePart, extra] = raw.split('|');
    const name = namePart.split('#')[0].trim();
    const section = namePart.indexOf('#') >= 0 ? namePart.slice(namePart.indexOf('#') + 1) : '';
    const f = findFileByName(name);
    if (!f) { el.innerHTML = '<span class="embed-missing">⚠ No encontrado: ' + esc(name) + '</span>'; return; }
    const ext = (f.ext || f.path.split('.').pop() || '').toLowerCase();
    if (IMG_EXT.includes(ext)) {
      const m = (extra || '').trim().match(/^(\d+)(?:x(\d+))?$/);
      let dim = '';
      if (m) { dim += ` width="${m[1]}"`; if (m[2]) dim += ` height="${m[2]}"`; }
      el.innerHTML = `<img src="${assetUrl(f.path)}" alt="${esc(f.name || name)}"${dim} loading="lazy">`;
      el.style.border = 'none';
      return;
    }
    if (ext === 'pdf') {
      el.innerHTML = `<iframe src="${assetUrl(f.path)}" style="width:100%;height:480px;border:0" title="${esc(f.name || name)}"></iframe>`;
      return;
    }
    if (ext === 'md') {
      if (depth >= MAX_EMBED_DEPTH) {
        el.innerHTML = `<span class="embed-missing">↪ ${esc(f.name)} (demasiadas notas anidadas)</span>`;
        return;
      }
      const titleTxt = section ? `${f.name} › ${section.replace(/^\^/, '')}` : f.name;
      el.innerHTML = `<div class="embed-title">▣ ${esc(titleTxt)}</div><div class="embed-body">Cargando…</div>`;
      el.querySelector('.embed-title').addEventListener('click', () => openNote(f.path));
      fetch(API + '/note?path=' + encodeURIComponent(f.path))
        .then(r => r.json())
        .then(res => {
          const bodyEl = el.querySelector('.embed-body');
          if (!bodyEl) return;
          const md = section && !section.startsWith('^')
            ? extractSection(res.content || '', section) : (res.content || '');
          bodyEl.innerHTML = renderMarkdown(md);
          postProcess(bodyEl, depth + 1);
        })
        .catch(() => { const b = el.querySelector('.embed-body'); if (b) b.textContent = 'No se pudo cargar'; });
      return;
    }
    el.innerHTML = `<a class="embed-title" href="${assetUrl(f.path)}" target="_blank" rel="noopener">⬇ ${esc(f.name)}</a>`;
  }

  function postProcess(container, depth) {
    depth = depth || 0;
    let hasMermaid = false;

    container.querySelectorAll('pre code').forEach(code => {
      const lang = (code.className.match(/language-([\w-]+)/) || [])[1];
      if (lang === 'mermaid') {
        const pre = code.closest('pre'); const div = document.createElement('div');
        div.className = 'mermaid'; div.textContent = code.textContent;
        pre.replaceWith(div); hasMermaid = true; return;
      }
      try { window.hljs && hljs.highlightElement(code); } catch (e) {}
      addCopyBtn(code.closest('pre'));
    });

    container.querySelectorAll('blockquote').forEach(bq => {
      const first = bq.querySelector('p'); if (!first) return;
      if (!/^\s*\[![A-Za-z]+\]/.test(first.textContent)) return;
      const type = (/^\s*\[!([A-Za-z]+)\]/.exec(first.textContent) || [])[1].toLowerCase();
      const html = first.innerHTML;
      const brm = html.match(/<br\s*\/?>/i);
      const titleHtml = brm ? html.slice(0, html.indexOf(brm[0])) : html;
      const bodyHtml = brm ? html.slice(html.indexOf(brm[0]) + brm[0].length) : '';
      const title = titleHtml.replace(/^\s*\[![A-Za-z]+\][+-]?\s*/, '').trim()
        || (type.charAt(0).toUpperCase() + type.slice(1));
      if (bodyHtml.trim()) first.innerHTML = bodyHtml; else first.remove();
      const wrap = document.createElement('div'); wrap.className = 'callout'; wrap.dataset.cl = type;
      const body = document.createElement('div'); body.className = 'callout-content';
      while (bq.firstChild) body.appendChild(bq.firstChild);
      wrap.innerHTML = `<div class="callout-title">${CALLOUT_ICON}<span>${title}</span></div>`;
      wrap.appendChild(body); bq.replaceWith(wrap);
    });

    // Imágenes markdown normales: ![alt](Adjuntos/foo.webp)
    container.querySelectorAll('img').forEach(img => {
      const src = img.getAttribute('src') || '';
      if (/^(https?:|data:|\/)/.test(src)) return;
      let f = null;
      try { f = findFileByName(decodeURIComponent(src)); } catch (_) { f = findFileByName(src); }
      if (f) { img.src = assetUrl(f.path); img.loading = 'lazy'; }
    });

    container.querySelectorAll('.wikilink').forEach(w => {
      const name = (w.dataset.target || '').split('#')[0].split('|')[0].trim();
      if (!findFileByName(name)) w.classList.add('missing');
    });

    container.querySelectorAll('.internal-embed').forEach(el => resolveEmbed(el, depth));

    if (hasMermaid) renderMermaid(container);
  }

  /* ════════════ Árbol ════════════ */

  const iconFolder = open => open
    ? '<svg class="ico" viewBox="0 0 24 24" fill="currentColor"><path d="M19 20H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h6l2 2h7a2 2 0 0 1 2 2H4v10l2.14-7H23l-2.28 7.62A2 2 0 0 1 19 20z"/></svg>'
    : '<svg class="ico" viewBox="0 0 24 24" fill="currentColor"><path d="M10 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z"/></svg>';
  const iconNote = '<svg class="ico" viewBox="0 0 24 24" fill="currentColor"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6zm-1 7V3.5L18.5 9H13z"/></svg>';
  const iconChev = '<svg class="kn-chev" viewBox="0 0 24 24" fill="currentColor"><path d="M8.59 16.59 13.17 12 8.59 7.41 10 6l6 6-6 6z"/></svg>';

  const expanded = new Set(JSON.parse(localStorage.getItem('kn-expanded') || '[]'));
  const persist = () => localStorage.setItem('kn-expanded', JSON.stringify([...expanded]));

  function renderTree(items, depth) {
    // Los adjuntos no son lectura: son el material de las notas. Enseñarlos
    // como una carpeta más llena el índice de ruido.
    const visible = items.filter(it => it.type !== 'file');
    return visible.map(it => {
      if (it.type === 'folder') {
        const isOpen = expanded.has(it.path);
        const kids = renderTree(it.children || [], depth + 1);
        if (!kids) return '';   // carpeta sin notas dentro: no se enseña
        return `<div class="kn-folder" data-path="${esc(it.path)}">
            <button type="button" class="kn-row kn-row-folder${isOpen ? ' is-open' : ''}"
                    style="--d:${depth}" aria-expanded="${isOpen}">
              ${iconChev}${iconFolder(isOpen)}<span>${esc(it.name)}</span>
            </button>
            <div class="kn-children"${isOpen ? '' : ' hidden'}>${kids}</div>
          </div>`;
      }
      return `<button type="button" class="kn-row kn-row-note" style="--d:${depth}"
                data-note="${esc(it.path)}">${iconNote}<span>${esc(it.name)}</span></button>`;
    }).join('');
  }

  function paintTree() {
    const html = renderTree(TREE, 0);
    $('kn-tree').innerHTML = html || '<p class="kn-empty">Esta bóveda todavía no tiene notas.</p>';
    markActive();
  }

  function markActive() {
    document.querySelectorAll('.kn-row-note').forEach(el => {
      el.classList.toggle('is-active', el.dataset.note === currentPath);
    });
  }

  /* Abre todas las carpetas que llevan hasta `path` para que la nota activa
     se vea en el índice al llegar por un enlace directo. */
  function expandTo(path) {
    const parts = path.split('/');
    parts.pop();
    let acc = '';
    parts.forEach(p => { acc = acc ? acc + '/' + p : p; expanded.add(acc); });
    persist();
  }

  $('kn-tree').addEventListener('click', e => {
    const folder = e.target.closest('.kn-row-folder');
    if (folder) {
      const wrap = folder.closest('.kn-folder');
      const path = wrap.dataset.path;
      const nowOpen = !expanded.has(path);
      if (nowOpen) expanded.add(path); else expanded.delete(path);
      persist();
      folder.classList.toggle('is-open', nowOpen);
      folder.setAttribute('aria-expanded', String(nowOpen));
      folder.querySelector('.ico').outerHTML = iconFolder(nowOpen);
      wrap.querySelector('.kn-children').hidden = !nowOpen;
      return;
    }
    const note = e.target.closest('.kn-row-note');
    if (note) openNote(note.dataset.note);
  });

  /* ════════════ Abrir notas ════════════ */

  function setCrumb(path) {
    const parts = path.split('/');
    const name = parts.pop().replace(/\.md$/i, '');
    $('kn-crumb').innerHTML = parts.length
      ? `<span class="kn-crumb-dir">${esc(parts.join(' / '))}</span> / <strong>${esc(name)}</strong>`
      : `<strong>${esc(name)}</strong>`;
  }

  async function openNote(path, opts) {
    opts = opts || {};
    const content = $('kn-content');
    $('kn-welcome').hidden = true;
    content.hidden = false;
    content.innerHTML = '<p class="kn-loading">Cargando…</p>';
    closeSidebar();

    let res;
    try {
      res = await fetch(API + '/note?path=' + encodeURIComponent(path)).then(r => r.json());
    } catch (_) {
      content.innerHTML = '<p class="kn-loading">No se ha podido cargar la nota.</p>';
      return;
    }
    if (res.error) {
      content.innerHTML = `<p class="kn-loading">${esc(res.error)}</p>`;
      return;
    }

    currentPath = res.path;
    setCrumb(res.path);
    document.title = res.name + ' — Conocimiento — Cogny';
    content.innerHTML = renderMarkdown(res.content || '');
    postProcess(content, 0);
    content.scrollTop = 0;
    $('kn-main').scrollTop = 0;

    expandTo(res.path);
    paintTree();

    if (!opts.fromHistory) {
      history.pushState({ path: res.path }, '', '/conocimiento/?n=' + encodeURIComponent(res.path));
    }
  }

  function showWelcome(fromHistory) {
    currentPath = '';
    $('kn-content').hidden = true;
    $('kn-welcome').hidden = false;
    $('kn-crumb').textContent = 'Conocimiento';
    document.title = 'Conocimiento — Cogny';
    markActive();
    if (!fromHistory) history.pushState({}, '', '/conocimiento/');
  }

  // Wikilinks: navegan dentro de la bóveda como cualquier otro enlace.
  // Imágenes: zoom a pantalla completa (mismo lightbox que el editor).
  $('kn-content').addEventListener('click', e => {
    const im = e.target.closest('img');
    if (im) { e.preventDefault(); openLightbox(im.src); return; }
    const link = e.target.closest('.wikilink');
    if (!link || link.classList.contains('missing')) return;
    const name = (link.dataset.target || '').split('|')[0].split('#')[0].trim();
    const f = findFileByName(name);
    if (f && (f.type === 'note' || /\.md$/i.test(f.path))) openNote(f.path);
  });

  /* ════════════ Lightbox de imágenes ════════════ */

  function openLightbox(src) {
    const lb = $('img-lightbox');
    lb.querySelector('img').src = src;
    lb.classList.add('show'); lb.setAttribute('aria-hidden', 'false');
  }
  function closeLightbox() {
    const lb = $('img-lightbox');
    lb.classList.remove('show'); lb.setAttribute('aria-hidden', 'true');
    lb.querySelector('img').removeAttribute('src');
  }
  $('img-lightbox').addEventListener('click', closeLightbox);
  $('img-lightbox').querySelector('.lightbox-close').addEventListener('click', e => {
    e.stopPropagation(); closeLightbox();
  });

  window.addEventListener('popstate', e => {
    const path = (e.state && e.state.path) ||
      new URLSearchParams(location.search).get('n') || '';
    if (path) openNote(path, { fromHistory: true }); else showWelcome(true);
  });

  /* ════════════ Buscador ════════════ */

  let searchTimer;
  const qInput = $('kn-q');

  function showTree() {
    $('kn-results').hidden = true;
    $('kn-tree').hidden = false;
    $('kn-q-clear').hidden = !qInput.value;
  }

  async function runSearch(q) {
    const box = $('kn-results');
    $('kn-tree').hidden = true;
    box.hidden = false;
    box.innerHTML = '<p class="kn-empty">Buscando…</p>';
    let res;
    try {
      res = await fetch(API + '/search?q=' + encodeURIComponent(q)).then(r => r.json());
    } catch (_) {
      box.innerHTML = '<p class="kn-empty">No se ha podido buscar.</p>';
      return;
    }
    const list = res.results || [];
    if (!list.length) {
      box.innerHTML = `<p class="kn-empty">Nada para “${esc(q)}”.</p>`;
      return;
    }
    box.innerHTML = list.map(r => `
      <button type="button" class="kn-hit" data-note="${esc(r.path)}">
        <span class="kn-hit-name">${esc(r.name)}</span>
        <span class="kn-hit-path">${esc(r.path)}</span>
        <span class="kn-hit-snippet">${esc(r.snippet)}</span>
      </button>`).join('');
  }

  qInput.addEventListener('input', () => {
    const q = qInput.value.trim();
    $('kn-q-clear').hidden = !qInput.value;
    clearTimeout(searchTimer);
    if (q.length < 2) { showTree(); return; }
    searchTimer = setTimeout(() => runSearch(q), 250);
  });
  qInput.addEventListener('keydown', e => { if (e.key === 'Escape') { qInput.value = ''; showTree(); } });
  $('kn-q-clear').addEventListener('click', () => { qInput.value = ''; showTree(); qInput.focus(); });
  $('kn-results').addEventListener('click', e => {
    const hit = e.target.closest('.kn-hit');
    if (hit) openNote(hit.dataset.note);
  });

  /* ════════════ Índice lateral en móvil ════════════ */

  const side = $('kn-side'), overlay = $('kn-overlay'), toggle = $('kn-side-toggle');
  function openSidebar() {
    side.classList.add('is-open'); overlay.hidden = false;
    toggle.setAttribute('aria-expanded', 'true');
  }
  function closeSidebar() {
    side.classList.remove('is-open'); overlay.hidden = true;
    toggle.setAttribute('aria-expanded', 'false');
  }
  toggle.addEventListener('click', () => {
    side.classList.contains('is-open') ? closeSidebar() : openSidebar();
  });
  overlay.addEventListener('click', closeSidebar);
  document.addEventListener('keydown', e => {
    if (e.key !== 'Escape') return;
    if ($('img-lightbox').classList.contains('show')) { closeLightbox(); return; }
    closeSidebar();
  });

  /* ════════════ Arranque ════════════ */

  (async function start() {
    try {
      const res = await fetch(API + '/tree').then(r => r.json());
      TREE = res.tree || [];
    } catch (_) {
      $('kn-tree').innerHTML = '<p class="kn-empty">No se ha podido cargar el índice.</p>';
      return;
    }
    indexTree(TREE);

    const wanted = JSON.parse($('kn-open-path').textContent || '""');
    if (wanted) expandTo(wanted);
    paintTree();
    if (wanted) openNote(wanted, { fromHistory: true });
  })();
})();
