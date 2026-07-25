/* Vista pública de una nota compartida (/s/<token>/).
 *
 * Versión reducida del pipeline de render de notes.js: mismo Markdown
 * "Obsidian-flavored" (KaTeX, callouts, resaltado, tags, ==highlight==), pero
 * SIN acceso al resto de la bóveda. Las imágenes/PDF embebidos ya vienen
 * resueltos por el servidor en `ASSETS` (sólo lo referenciado por esta nota);
 * los embeds/wikilinks a OTRAS notas se muestran como no disponibles en vez
 * de intentar resolverlos (esta vista no tiene ni debe tener acceso al árbol
 * completo del usuario).
 */
(function () {
  'use strict';

  const CONTENT = JSON.parse(document.getElementById('shared-content-data').textContent);
  const ASSETS = JSON.parse(document.getElementById('shared-assets-data').textContent);

  function esc(s) { return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
  function resolveAsset(ref) {
    const cleaned = (ref || '').split('|')[0].split('#')[0].trim();
    return ASSETS[cleaned] || ASSETS[ref] || null;
  }

  /* ── Markdown "Obsidian-flavored" (mismas extensiones que notes.js) ─────── */
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
    renderer(t) {
      const url = resolveAsset(t.target);
      if (!url) return '<span class="embed-missing">⚠ No disponible en la vista pública</span>';
      const name = t.target.split('|')[0].split('#')[0].trim();
      const ext = (name.split('.').pop() || '').toLowerCase();
      if (ext === 'pdf') return `<iframe src="${url}" style="width:100%;height:480px;border:0"></iframe>`;
      // data-resolved: ya trae una URL firmada válida — el fixup genérico de
      // <img> en postProcess() (pensado para ![alt](ref) sin resolver) no
      // debe tocarla, o la sobreescribiría con el aviso de "no disponible".
      return `<img src="${url}" alt="${esc(name)}" data-resolved="1">`;
    },
  };
  const wikilink = {
    name: 'wikilink', level: 'inline', start(s) { return s.indexOf('[['); },
    tokenizer(src) { const m = /^\[\[([^\]\n]+?)\]\]/.exec(src); if (m) return { type: 'wikilink', raw: m[0], target: m[1] }; },
    renderer(t) {
      const parts = t.target.split('|');
      const disp = (parts[1] || parts[0].split('#')[0]).trim();
      return `<span class="wikilink missing" title="No disponible en la vista pública">${esc(disp)}</span>`;
    },
  };
  const highlightMark = {
    name: 'hl', level: 'inline', start(s) { return s.indexOf('=='); },
    tokenizer(src) { const m = /^==(?=\S)([\s\S]+?)==/.exec(src); if (m) { const tok = this.lexer.inlineTokens(m[1]); return { type: 'hl', raw: m[0], tokens: tok }; } },
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
    const ids = Object.keys(defs);
    if (!ids.length) return src;
    let order = [];
    src = src.replace(/\[\^([^\]]+)\]/g, (m, id) => {
      if (!(id in defs)) return m;
      if (!order.includes(id)) order.push(id);
      const i = order.indexOf(id) + 1;
      return `<sup class="fn-ref" id="fnref-${esc(id)}"><a href="#fn-${esc(id)}">[${i}]</a></sup>`;
    });
    if (!order.length) return src;
    let foot = '\n\n<hr>\n<ol class="footnotes">';
    order.forEach(id => { foot += `<li id="fn-${esc(id)}">${esc(defs[id])} <a href="#fnref-${esc(id)}">↩</a></li>`; });
    foot += '</ol>';
    return src + foot;
  }
  function renderMarkdown(src) {
    const { body, props } = parseFrontmatter(src);
    let html = '';
    if (props) {
      html += '<div class="note-props"><table>';
      props.forEach(([k, v]) => { html += `<tr><th>${esc(k)}</th><td>${esc(v)}</td></tr>`; });
      html += '</table></div>';
    }
    html += marked.parse(extractFootnotes(body));
    return html;
  }

  /* ── Post-proceso: resaltado de código, callouts, mermaid ────────────────── */
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
      const text = code.textContent;
      try { await navigator.clipboard.writeText(text); }
      catch (_) {
        const ta = document.createElement('textarea'); ta.value = text;
        ta.style.cssText = 'position:fixed;opacity:0'; document.body.appendChild(ta);
        ta.select(); try { document.execCommand('copy'); } catch (__) { } ta.remove();
      }
      btn.classList.add('copied'); btn.innerHTML = CHECK_ICON; btn.title = '¡Copiado!';
      setTimeout(() => { btn.classList.remove('copied'); btn.innerHTML = COPY_ICON; btn.title = 'Copiar'; }, 1400);
    });
    pre.appendChild(btn);
  }
  let mermaidLoaded = false;
  async function renderMermaid(container) {
    const nodes = container.querySelectorAll('.mermaid'); if (!nodes.length) return;
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
  function postProcess(container) {
    let hasMermaid = false;
    container.querySelectorAll('pre code').forEach(code => {
      const lang = (code.className.match(/language-([\w-]+)/) || [])[1];
      if (lang === 'mermaid') {
        const pre = code.closest('pre'); const div = document.createElement('div');
        div.className = 'mermaid'; div.textContent = code.textContent; pre.replaceWith(div); hasMermaid = true; return;
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
      let titleHtml = brm ? html.slice(0, html.indexOf(brm[0])) : html;
      const bodyHtml = brm ? html.slice(html.indexOf(brm[0]) + brm[0].length) : '';
      const title = titleHtml.replace(/^\s*\[![A-Za-z]+\][+-]?\s*/, '').trim() || (type.charAt(0).toUpperCase() + type.slice(1));
      if (bodyHtml.trim()) first.innerHTML = bodyHtml; else first.remove();
      const wrap = document.createElement('div'); wrap.className = 'callout'; wrap.dataset.cl = type;
      const body = document.createElement('div'); body.className = 'callout-content';
      while (bq.firstChild) body.appendChild(bq.firstChild);
      wrap.innerHTML = `<div class="callout-title">${CALLOUT_ICON}<span>${title}</span></div>`;
      wrap.appendChild(body); bq.replaceWith(wrap);
    });
    // Imágenes markdown normales ![alt](ref) / <img src="ref"> — el renderer
    // de `embed` ya resolvió las ![[...]] arriba.
    container.querySelectorAll('img').forEach(img => {
      if (img.hasAttribute('data-resolved')) return;   // ya resuelta por el renderer de `embed`
      const src = img.getAttribute('src') || '';
      if (/^(https?:|data:)/.test(src)) return;
      let url;
      try { url = resolveAsset(decodeURIComponent(src)); } catch (_) { url = null; }
      url = url || resolveAsset(src);
      if (url) img.src = url;
      else img.replaceWith(document.createTextNode('[imagen no disponible en la vista pública]'));
    });
    if (hasMermaid) renderMermaid(container);
  }

  const el = document.getElementById('shared-content');
  el.innerHTML = renderMarkdown(CONTENT);
  postProcess(el);
})();
