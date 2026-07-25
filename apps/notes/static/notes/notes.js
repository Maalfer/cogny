/* Editor del vault de notas (cogny). Extraído de notes.html a fichero
   estático: se lintea/versiona como código y no lo re-parsea el motor de
   plantillas en cada render. Los valores de servidor llegan por window.COGNY
   (definido inline en la plantilla). */
const CSRF = window.COGNY.csrf;
// Las subidas grandes (import de bóvedas) van por un subdominio DNS-only fuera de
// Cloudflare, para esquivar su límite de 100 MB por request. El host lo inyecta el
// servidor (UPLOAD_HOST en .env); si está vacío, se sube al mismo origen.
const UPLOAD_HOST = window.COGNY.uploadHost;
const UPLOAD_BASE = UPLOAD_HOST ? ('https://' + UPLOAD_HOST) : '';
let TREE = [];
let FLAT = [];             // flattened list of notes+files for name lookup
let current = null;        // {path, name, content}
let dirty = false;
let saveTimer = null;
let mermaidLoaded = false;
let ED = null;             // editor CodeMirror (Live Preview)
// Carpetas EXPANDIDAS (por defecto todo contraído → render instantáneo en bóvedas grandes)
const expanded = new Set(JSON.parse(localStorage.getItem('vault-expanded') || '[]'));
let BY_PATH = new Map();   // ruta(minúsculas) -> archivo  (búsqueda O(1) de embeds/imágenes)
let BY_BASE = new Map();   // nombre(+/- extensión) -> archivo
let searchTimer = null;
let dragSrc = null;         // {path, type} del elemento del árbol que se está arrastrando
let dropTargetEl = null;    // elemento con el resaltado de "voy a soltar aquí" activo
const $ = id => document.getElementById(id);
const IMG_EXT = ['png','jpg','jpeg','gif','webp','svg','bmp','ico'];

/* Permiso de escritura del acceso en curso. La UI se apaga en consecuencia
   (botones ocultos por CSS con .role-readonly, acciones cortadas aquí), pero
   quien manda es el servidor: cada endpoint que muta lleva @require_write. */
const CAN_WRITE = window.COGNY.canWrite !== false;
function guardWrite(){
  if(CAN_WRITE) return true;
  alert('Tu acceso a esta bóveda es de sólo lectura.');
  return false;
}

function api(url, body) {
  return fetch(url, {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify(body)}).then(r => r.json());
}
function esc(s){return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
function assetUrl(path){return '/api/notes/asset?path=' + encodeURIComponent(path);}

/* ════════════ Obsidian-flavored Markdown ════════════ */
(function setupMarked(){
  const mathBlock = {name:'mathBlock', level:'block', start(s){return s.indexOf('$$');},
    tokenizer(src){const m=/^\$\$([\s\S]+?)\$\$/.exec(src); if(m) return {type:'mathBlock', raw:m[0], text:m[1]};},
    renderer(t){try{return katex.renderToString(t.text.trim(),{displayMode:true,throwOnError:false});}catch(e){return '<pre>'+esc(t.text)+'</pre>';}}};
  const mathInline = {name:'mathInline', level:'inline', start(s){return s.indexOf('$');},
    tokenizer(src){const m=/^\$(?!\s)((?:\\\$|[^$\n])+?)(?<!\s)\$(?!\d)/.exec(src); if(m) return {type:'mathInline', raw:m[0], text:m[1]};},
    renderer(t){try{return katex.renderToString(t.text,{throwOnError:false});}catch(e){return esc(t.raw);}}};
  const embed = {name:'embed', level:'inline', start(s){return s.indexOf('![[');},
    tokenizer(src){const m=/^!\[\[([^\]\n]+?)\]\]/.exec(src); if(m) return {type:'embed', raw:m[0], target:m[1]};},
    renderer(t){return `<span class="internal-embed" data-target="${esc(t.target)}"></span>`;}};
  const wikilink = {name:'wikilink', level:'inline', start(s){return s.indexOf('[[');},
    tokenizer(src){const m=/^\[\[([^\]\n]+?)\]\]/.exec(src); if(m) return {type:'wikilink', raw:m[0], target:m[1]};},
    renderer(t){const parts=t.target.split('|'); const tgt=parts[0].trim(); const disp=(parts[1]||tgt.split('#')[0]).trim();
      return `<span class="wikilink" data-target="${esc(tgt)}">${esc(disp)}</span>`;}};
  const highlight = {name:'hl', level:'inline', start(s){return s.indexOf('==');},
    tokenizer(src){const m=/^==(?=\S)([\s\S]+?)==/.exec(src); if(m){const tok=this.lexer.inlineTokens(m[1]); return {type:'hl', raw:m[0], tokens:tok};}},
    renderer(t){return '<mark>'+this.parser.parseInline(t.tokens)+'</mark>';}};
  const tag = {name:'tag', level:'inline', start(s){const i=s.search(/#[A-Za-z]/);return i<0?undefined:i;},
    tokenizer(src){const m=/^#([A-Za-z0-9_/-]*[A-Za-z_/-][A-Za-z0-9_/-]*)/.exec(src); if(m) return {type:'tag', raw:m[0], tag:m[1]};},
    renderer(t){return `<a class="tag-pill" data-tag="${esc(t.tag)}">#${esc(t.tag)}</a>`;}};
  const comment = {name:'comment', level:'inline', start(s){return s.indexOf('%%');},
    tokenizer(src){const m=/^%%[\s\S]*?%%/.exec(src); if(m) return {type:'comment', raw:m[0]};},
    renderer(){return '';}};
  marked.use({gfm:true, breaks:true, extensions:[mathBlock, mathInline, embed, wikilink, highlight, tag, comment]});
})();

function parseFrontmatter(src){
  const m=/^---\n([\s\S]*?)\n---\n?/.exec(src);
  if(!m) return {body:src, props:null};
  const props=[];
  m[1].split('\n').forEach(line=>{
    const mm=/^([A-Za-z0-9_ -]+):\s*(.*)$/.exec(line);
    if(mm) props.push([mm[1].trim(), mm[2].trim()]);
  });
  return {body: src.slice(m[0].length), props: props.length?props:null};
}
function extractFootnotes(src){
  const defs={};
  src=src.replace(/^\[\^([^\]]+)\]:\s?(.*)$/gm,(m,id,txt)=>{defs[id]=txt;return '';});
  const ids=Object.keys(defs);
  if(!ids.length) return src;
  let n=0; const order=[];
  src=src.replace(/\[\^([^\]]+)\]/g,(m,id)=>{ if(!(id in defs))return m; if(!order.includes(id))order.push(id);
    const i=order.indexOf(id)+1; return `<sup class="fn-ref" id="fnref-${esc(id)}"><a href="#fn-${esc(id)}">[${i}]</a></sup>`;});
  if(!order.length) return src;
  let foot='\n\n<hr>\n<ol class="footnotes">';
  order.forEach(id=>{foot+=`<li id="fn-${esc(id)}">${esc(defs[id])} <a href="#fnref-${esc(id)}">↩</a></li>`;});
  foot+='</ol>';
  return src+foot;
}

function renderMarkdown(src){
  const {body, props}=parseFrontmatter(src);
  let html='';
  if(props){html+='<div class="note-props"><table>';
    props.forEach(([k,v])=>{html+=`<tr><th>${esc(k)}</th><td>${esc(v)}</td></tr>`;});
    html+='</table></div>';}
  let md=extractFootnotes(body);
  html+=marked.parse(md);
  return html;
}

const CALLOUT_ICON='<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2a10 10 0 100 20 10 10 0 000-20zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/></svg>';
const COPY_ICON='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>';
const CHECK_ICON='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>';
// Añade un botón "copiar" a un <pre> de código (idempotente).
function addCopyBtn(pre){
  if(pre.querySelector('.code-copy')) return;       // ya lo tiene
  const code=pre.querySelector('code'); if(!code) return;
  const btn=document.createElement('button');
  btn.className='code-copy'; btn.type='button';
  btn.title='Copiar'; btn.setAttribute('aria-label','Copiar código');
  btn.innerHTML=COPY_ICON;
  // evita que CodeMirror capture el clic (mover el cursor / seleccionar)
  btn.addEventListener('mousedown', e=>e.preventDefault());
  btn.addEventListener('click', async e=>{
    e.preventDefault(); e.stopPropagation();
    const text=code.textContent;
    try{ await navigator.clipboard.writeText(text); }
    catch(_){ const ta=document.createElement('textarea'); ta.value=text;
      ta.style.cssText='position:fixed;opacity:0'; document.body.appendChild(ta);
      ta.select(); try{document.execCommand('copy');}catch(__){} ta.remove(); }
    btn.classList.add('copied'); btn.innerHTML=CHECK_ICON; btn.title='¡Copiado!';
    setTimeout(()=>{ btn.classList.remove('copied'); btn.innerHTML=COPY_ICON; btn.title='Copiar'; }, 1400);
  });
  pre.appendChild(btn);
}
function postProcess(container, depth){
  depth=depth||0;
  // Code blocks: mermaid + syntax highlight
  let hasMermaid=false;
  container.querySelectorAll('pre code').forEach(code=>{
    const cls=code.className||'';
    const lang=(cls.match(/language-([\w-]+)/)||[])[1];
    if(lang==='mermaid'){ const pre=code.closest('pre'); const div=document.createElement('div');
      div.className='mermaid'; div.textContent=code.textContent; pre.replaceWith(div); hasMermaid=true; return; }
    try{ window.hljs && hljs.highlightElement(code); }catch(e){}
    addCopyBtn(code.closest('pre'));
  });
  // Callouts: blockquote whose first line is [!type] Title
  container.querySelectorAll('blockquote').forEach(bq=>{
    const first=bq.querySelector('p'); if(!first) return;
    if(!/^\s*\[![A-Za-z]+\]/.test(first.textContent)) return;
    const type=(/^\s*\[!([A-Za-z]+)\]/.exec(first.textContent)||[])[1].toLowerCase();
    // First paragraph holds "[!type] Title <br> body…": split at the first <br>
    const html=first.innerHTML;
    const brm=html.match(/<br\s*\/?>/i);
    let titleHtml=brm?html.slice(0,html.indexOf(brm[0])):html;
    const bodyHtml=brm?html.slice(html.indexOf(brm[0])+brm[0].length):'';
    const title=titleHtml.replace(/^\s*\[![A-Za-z]+\][+-]?\s*/,'').trim()
      || (type.charAt(0).toUpperCase()+type.slice(1));
    if(bodyHtml.trim()) first.innerHTML=bodyHtml; else first.remove();
    const wrap=document.createElement('div'); wrap.className='callout'; wrap.dataset.cl=type;
    const body=document.createElement('div'); body.className='callout-content';
    while(bq.firstChild) body.appendChild(bq.firstChild);
    wrap.innerHTML=`<div class="callout-title">${CALLOUT_ICON}<span>${title}</span></div>`;
    wrap.appendChild(body); bq.replaceWith(wrap);
  });
  // Resolve relative images
  container.querySelectorAll('img').forEach(img=>{
    const src=img.getAttribute('src')||'';
    if(/^(https?:|data:|\/)/.test(src)) return;
    const f=findFileByName(decodeURIComponent(src));
    if(f) img.src=assetUrl(f.path);
  });
  // Wikilink existence styling
  container.querySelectorAll('.wikilink').forEach(w=>{
    const name=(w.dataset.target||'').split('#')[0].split('|')[0].trim();
    if(!findFileByName(name)) w.classList.add('missing');
  });
  // Embeds
  if(depth<3) container.querySelectorAll('.internal-embed').forEach(el=>resolveEmbed(el, depth));
  // Mermaid (lazy)
  if(hasMermaid) renderMermaid(container);
}

// Extrae solo una sección (encabezado) de una nota, como hace Obsidian con
// ![[nota#Encabezado]]. Devuelve el markdown desde ese encabezado hasta el
// siguiente del mismo nivel o superior. Si no la encuentra, devuelve todo.
function extractSection(md, heading){
  if(!heading) return md;
  const target=heading.replace(/^#*/,'').trim().toLowerCase();
  if(!target) return md;
  const lines=md.split('\n');
  let start=-1, level=0;
  for(let i=0;i<lines.length;i++){
    const m=/^(#{1,6})\s+(.*)$/.exec(lines[i]);
    if(m && m[2].trim().toLowerCase()===target){ start=i; level=m[1].length; break; }
  }
  if(start<0) return md;
  let end=lines.length;
  for(let i=start+1;i<lines.length;i++){
    const m=/^(#{1,6})\s+/.exec(lines[i]);
    if(m && m[1].length<=level){ end=i; break; }
  }
  return lines.slice(start, end).join('\n');
}
function resolveEmbed(el, depth){
  const raw=el.dataset.target||'';
  const [namePart, extra]=raw.split('|');
  const name=namePart.split('#')[0].trim();
  const section=namePart.indexOf('#')>=0 ? namePart.slice(namePart.indexOf('#')+1) : '';
  const f=findFileByName(name);
  if(!f){ el.innerHTML='<span class="embed-missing">⚠ No encontrado: '+esc(name)+'</span>'; return; }
  const ext=(f.ext||f.path.split('.').pop()||'').toLowerCase();
  if(IMG_EXT.includes(ext)){
    // Tamaño estilo Obsidian: |ancho  o  |anchoxalto
    const m=(extra||'').trim().match(/^(\d+)(?:x(\d+))?$/);
    let dim=''; if(m){ dim+=` width="${m[1]}"`; if(m[2]) dim+=` height="${m[2]}"`; }
    el.innerHTML=`<img src="${assetUrl(f.path)}"${dim}>`; el.style.border='none'; return;
  }
  if(ext==='pdf'){ el.innerHTML=`<iframe src="${assetUrl(f.path)}" style="width:100%;height:480px;border:0"></iframe>`; return; }
  if(ext==='md'){
    const titleTxt = section ? `${f.name} › ${section.replace(/^\^/,'')}` : f.name;
    el.innerHTML=`<div class="embed-title" data-open="${esc(f.path)}">▣ ${esc(titleTxt)}</div><div class="embed-body">Cargando…</div>`;
    el.querySelector('.embed-title').onclick=()=>openNote(f.path);
    fetch('/api/notes/file?path='+encodeURIComponent(f.path)).then(r=>r.json()).then(res=>{
      const bodyEl=el.querySelector('.embed-body'); if(!bodyEl)return;
      const md = section && !section.startsWith('^') ? extractSection(res.content||'', section) : (res.content||'');
      bodyEl.innerHTML=renderMarkdown(md); postProcess(bodyEl, depth+1);
    }).catch(()=>{}); return;
  }
  el.innerHTML=`<a class="embed-title" href="${assetUrl(f.path)}" target="_blank">⬇ ${esc(f.name)}</a>`;
}

async function renderMermaid(container){
  const nodes=container.querySelectorAll('.mermaid'); if(!nodes.length) return;
  if(!mermaidLoaded){
    await new Promise((res,rej)=>{const s=document.createElement('script');
      s.src='/static/vendor/mermaid.min.js?v=' + window.COGNY.assetVersion; s.onload=res; s.onerror=rej; document.head.appendChild(s);}).catch(()=>{});
    if(window.mermaid){ mermaid.initialize({startOnLoad:false, theme:'dark'}); mermaidLoaded=true; }
  }
  try{ window.mermaid && await mermaid.run({nodes:[...nodes]}); }catch(e){}
}

/* ════════════ Tree ════════════ */
function flatten(items){ items.forEach(it=>{
  if(it.type==='folder') flatten(it.children||[]);
  else {
    FLAT.push(it);
    BY_PATH.set(it.path.toLowerCase(), it);
    const base=it.path.split('/').pop().toLowerCase();
    if(!BY_BASE.has(base)) BY_BASE.set(base, it);
    const noExt=base.replace(/\.[^.]+$/,'');
    if(!BY_BASE.has(noExt)) BY_BASE.set(noExt, it);
  }
}); }
function findFileByName(name){
  name=name.replace(/\\/g,'/');
  const hit=BY_PATH.get(name.toLowerCase()); if(hit) return hit;
  const base=name.split('/').pop().toLowerCase();
  return BY_BASE.get(base) || BY_BASE.get(base.replace(/\.[^.]+$/,'')) || null;
}

function iconFolder(open){return open
  ? '<svg class="ico" viewBox="0 0 24 24" fill="currentColor"><path d="M19 20H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h6l2 2h7a2 2 0 0 1 2 2H4v10l2.14-7H23l-2.28 7.62A2 2 0 0 1 19 20z"/></svg>'
  : '<svg class="ico" viewBox="0 0 24 24" fill="currentColor"><path d="M10 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z"/></svg>';}
const iconNote='<svg class="ico" viewBox="0 0 24 24" fill="currentColor"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6zm-1 7V3.5L18.5 9H13z"/></svg>';
const iconImg='<svg class="ico" viewBox="0 0 24 24" fill="currentColor"><path d="M21 19V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2zM8.5 13.5l2.5 3 3.5-4.5 4.5 6H5l3.5-4.5z"/></svg>';
const iconFile='<svg class="ico" viewBox="0 0 24 24" fill="currentColor"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9l-7-7zm0 7V3.5L18.5 9H13z"/></svg>';
const iconChev='<svg viewBox="0 0 24 24" fill="currentColor"><path d="M8.59 16.59 13.17 12 8.59 7.41 10 6l6 6-6 6z"/></svg>';
const iconDots='<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 8a2 2 0 1 0 0-4 2 2 0 0 0 0 4zm0 2a2 2 0 1 0 0 4 2 2 0 0 0 0-4zm0 6a2 2 0 1 0 0 4 2 2 0 0 0 0-4z"/></svg>';

function persistExpanded(){ localStorage.setItem('vault-expanded', JSON.stringify([...expanded])); }
// Construye los hijos de una carpeta SOLO cuando hace falta (perezoso) → en bóvedas
// grandes nunca se crea DOM de ramas cerradas, así el árbol va fluido.
function buildChildren(kids){
  if(kids.dataset.built) return;
  const frag=document.createDocumentFragment();
  buildTreeDOM(kids._items||[], frag, kids._depth||0, kids._parentPath||'');
  kids.appendChild(frag); kids.dataset.built='1';
}
function buildTreeDOM(items, container, depth, parentPath){
  items.forEach(it=>{
    const row=document.createElement('div');
    row.className='tree-row'+(it.type==='file'?' is-file':'');
    row.dataset.path=it.path; row.dataset.type=it.type;
    // La carpeta de adjuntos concentra cientos de imágenes subidas por el backend
    // (upload() la fuerza siempre en la raíz): no se puede arrastrar ni recibir
    // sueltas "dentro" o se rompería esa ruta fija y el propósito de la carpeta.
    // OJO: comparar por PATH (no por nombre) — si no, una subcarpeta cualquiera
    // que el usuario llame "Adjuntos" en otro sitio del árbol heredaría por error
    // esta restricción (no expandible / no arrastrable).
    const isAttach=(it.type==='folder' && it.path==='Adjuntos');
    if(it.type==='folder'){
      // No expandible por click, para no generar un DOM enorme que ralentiza la web.
      const isOpen=!isAttach && expanded.has(it.path); if(!isOpen && !isAttach) row.classList.add('collapsed');
      row.innerHTML=`<span class="twirl">${isAttach?'':iconChev}</span>${iconFolder(isOpen)}<span class="label">${esc(it.name)}</span><button class="row-menu" aria-label="Opciones de ${esc(it.name)}">${iconDots}</button>`;
      container.appendChild(row);
      const kids=document.createElement('div'); kids.className='tree-children'+(isOpen?'':' hidden');
      kids._items=it.children||[]; kids._depth=depth+1; kids._parentPath=it.path;
      container.appendChild(kids);
      if(isOpen) buildChildren(kids);
      row.setAttribute('tabindex','0');
      row.setAttribute('role','button');
      row.setAttribute('aria-expanded', isOpen.toString());
      row.addEventListener('click', e=>{ if(e.target.closest('.row-menu'))return;
        if(isAttach) return;
        const willOpen=kids.classList.contains('hidden');
        if(willOpen) buildChildren(kids);
        kids.classList.toggle('hidden', !willOpen); row.classList.toggle('collapsed', !willOpen);
        row.querySelector('.ico').outerHTML=iconFolder(willOpen);
        row.setAttribute('aria-expanded', willOpen.toString());
        if(willOpen) expanded.add(it.path); else expanded.delete(it.path);
        persistExpanded();});
      row.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();row.click();}
        if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();
          const rows=[...document.querySelectorAll('#vault-tree .tree-row')].filter(r=>!r.closest('.tree-children.hidden'));
          const i=rows.indexOf(row);const next=rows[i+(e.key==='ArrowDown'?1:-1)];if(next)next.focus();}});
      if(!isAttach) wireRowDrop(kids, it.path);
    } else {
      const ico=it.type==='note'?iconNote:(IMG_EXT.includes(it.ext)?iconImg:iconFile);
      row.innerHTML=`<span style="width:16px"></span>${ico}<span class="label">${esc(it.name)}</span><button class="row-menu" aria-label="Opciones de ${esc(it.name)}">${iconDots}</button>`;
      if(current && current.path===it.path) row.classList.add('active');
      row.setAttribute('tabindex','0');
      container.appendChild(row);
      row.addEventListener('click', e=>{ if(e.target.closest('.row-menu'))return;
        if(it.type==='note') openNote(it.path); else window.open(assetUrl(it.path),'_blank');});
      row.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();row.click();}
        if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();
          const rows=[...document.querySelectorAll('#vault-tree .tree-row')].filter(r=>!r.closest('.tree-children.hidden'));
          const i=rows.indexOf(row);const next=rows[i+(e.key==='ArrowDown'?1:-1)];if(next)next.focus();}});
    }
    const menuBtn=row.querySelector('.row-menu');
    menuBtn.addEventListener('click', e=>{e.stopPropagation(); showCtxMenu(e, it);});
    menuBtn.draggable=false;   // que un clic impreciso sobre "···" no arranque el drag de la fila
    wireRowDrag(row, it, parentPath, isAttach);
  });
}

/* ════════════ Arrastrar y soltar en el árbol (reordenar / mover de carpeta) ════════════ */
function fsName(path){ return path.split('/').pop(); }
function parentPathOf(path){ const p=path.split('/'); p.pop(); return p.join('/'); }
function findNode(items, path){
  for(const n of items){
    if(n.path===path) return n;
    if(n.type==='folder'){ const f=findNode(n.children||[], path); if(f) return f; }
  }
  return null;
}
function setDropVisual(el, mode){
  if(dropTargetEl && (dropTargetEl!==el || dropTargetEl.dataset.dropMode!==mode)) clearDropVisual();
  el.classList.add('drop-'+mode); el.dataset.dropMode=mode; dropTargetEl=el;
}
function clearDropVisual(){
  if(dropTargetEl){ dropTargetEl.classList.remove('drop-before','drop-after','drop-into'); delete dropTargetEl.dataset.dropMode; }
  dropTargetEl=null;
}
// Cablea dragstart/dragover/drop de UNA fila (nota, archivo o carpeta) del árbol.
function wireRowDrag(row, it, parentPath, isAttach){
  if(!CAN_WRITE) return;
  if(isAttach) return;   // Adjuntos no se puede arrastrar (ruta fija en el backend)
  row.draggable=true;
  row.addEventListener('dragstart', e=>{
    e.stopPropagation();
    dragSrc={path:it.path, type:it.type};
    e.dataTransfer.effectAllowed='move';
    e.dataTransfer.setData('text/plain', it.path);   // Firefox exige setData para permitir el drag
    requestAnimationFrame(()=>row.classList.add('dragging'));
  });
  row.addEventListener('dragend', ()=>{ row.classList.remove('dragging'); clearDropVisual(); dragSrc=null; });
  row.addEventListener('dragover', e=>{
    if(!dragSrc || dragSrc.path===it.path) return;
    const rect=row.getBoundingClientRect(); const y=e.clientY-rect.top, h=rect.height;
    const canDropInto = it.type==='folder' && !isAttach;
    const mode = (canDropInto && y>h*0.25 && y<h*0.75) ? 'into' : (y<h/2 ? 'before' : 'after');
    // La carpeta destino EFECTIVA es esta misma (modo "into") o su padre (before/after,
    // reordenar como hermano). Si arrastramos una carpeta, ninguna de las dos puede ser
    // ella misma ni un descendiente suyo — si no, se movería dentro de sí misma. Comprobar
    // solo `it.path` (como en un primer intento) se queda corto: soltar sobre una NOTA que
    // vive dentro de una subcarpeta de la carpeta arrastrada también sería un ciclo, porque
    // el padre de esa nota (el targetParent real) sigue siendo un descendiente.
    const targetParent = mode==='into' ? it.path : parentPath;
    if(dragSrc.type==='folder' && (targetParent===dragSrc.path || targetParent.startsWith(dragSrc.path+'/'))) return;
    e.preventDefault(); e.stopPropagation(); e.dataTransfer.dropEffect='move';
    setDropVisual(row, mode);
  });
  row.addEventListener('drop', e=>{
    if(!dragSrc || dragSrc.path===it.path) return;
    e.preventDefault(); e.stopPropagation();
    const mode=row.dataset.dropMode; const src=dragSrc; dragSrc=null; clearDropVisual();
    if(!mode) return;
    if(mode==='into') dropItem(src, it.path, null, null);
    else dropItem(src, parentPath, fsName(it.path), mode);
  });
}
// Cablea el contenedor de hijos de una carpeta, para poder soltar "dentro" cuando
// está vacía o cuando se apunta al hueco bajo el último elemento visible.
function wireRowDrop(kids, folderPath){
  kids.addEventListener('dragover', e=>{
    if(!dragSrc || e.target!==kids) return;
    if(dragSrc.type==='folder' && (folderPath===dragSrc.path || folderPath.startsWith(dragSrc.path+'/'))) return;
    e.preventDefault(); e.stopPropagation(); e.dataTransfer.dropEffect='move';
    setDropVisual(kids, 'into');
  });
  kids.addEventListener('drop', e=>{
    if(!dragSrc || e.target!==kids) return;
    e.preventDefault(); e.stopPropagation();
    const src=dragSrc; dragSrc=null; clearDropVisual();
    dropItem(src, folderPath, null, null);
  });
}
// Mueve (si hace falta) y/o fija el nuevo orden tras soltar. `anchorName` es el
// nombre del hermano de referencia en la carpeta destino ('before'/'after'), o
// null para soltar al final (incluido el caso "dentro de esta carpeta").
async function dropItem(src, targetParent, anchorName, anchorSide){
  if(!guardWrite()) return;
  const sourceParent=parentPathOf(src.path);
  const sameParent=sourceParent===targetParent;
  const workingName=fsName(src.path);

  const destArr = targetParent ? ((findNode(TREE, targetParent)||{}).children||[]) : TREE;
  const originalNames = destArr.map(n=>fsName(n.path));
  const destNames = originalNames.filter(n=>n!==workingName);
  let idx=destNames.length;
  if(anchorName){
    const ai=destNames.indexOf(anchorName);
    if(ai>=0) idx = anchorSide==='after' ? ai+1 : ai;
  }
  destNames.splice(idx, 0, workingName);
  if(sameParent && destNames.every((n,i)=>n===originalNames[i])) return; // sin cambio real

  let finalPath=src.path;
  if(!sameParent){
    const moved=await moveItem(src, targetParent);
    if(!moved) return;
    finalPath=moved;
  }
  await api('/api/notes/reorder', {folder:targetParent, order:destNames});
  if(!sameParent){
    const srcArr = sourceParent ? ((findNode(TREE, sourceParent)||{}).children||[]) : TREE;
    const srcNames = srcArr.map(n=>fsName(n.path)).filter(n=>n!==workingName);
    await api('/api/notes/reorder', {folder:sourceParent, order:srcNames});
    revealPath(finalPath);
  }
  await loadTree(); renderTabs();
  // Confirmación visual de dónde quedó (mismo patrón que el clic en una miga de pan):
  // útil sobre todo tras un move a una carpeta lejana/colapsada.
  setTimeout(()=>{
    const row=document.querySelector('.tree-row[data-path="'+cssEsc(finalPath)+'"]');
    if(!row) return;
    row.scrollIntoView({behavior:'smooth', block:'nearest'});
    row.classList.remove('flash-locate'); void row.offsetWidth; row.classList.add('flash-locate');
  }, 60);
}
// Mueve un elemento a otra carpeta y recoloca pestañas/historial/expandidos que
// referenciaran su ruta antigua (misma lógica que ya usa renameItem, extendida
// a subrutas completas porque mover una carpeta arrastra también a sus hijos).
async function moveItem(it, targetParent){
  if(!guardWrite()) return;
  if(dirty) await saveNow();   // evita reescribir la ruta antigua si se autoguarda después de moverla
  const res=await api('/api/notes/move', {path:it.path, target:targetParent});
  if(res.error){ alert(res.error); return null; }
  const oldPath=it.path, newPath=res.path;
  const remap = p => (p===oldPath || p.startsWith(oldPath+'/')) ? newPath + p.slice(oldPath.length) : p;
  const reopenPath = (current && (current.path===oldPath || current.path.startsWith(oldPath+'/'))) ? remap(current.path) : null;
  tabs.forEach(t=>{ t.path=remap(t.path); t.history=t.history.map(remap); });
  const remappedExpanded=new Set([...expanded].map(remap));
  expanded.clear(); remappedExpanded.forEach(p=>expanded.add(p)); persistExpanded();
  if(reopenPath) await openNote(reopenPath, undefined, {_fromTab:true});
  return newPath;
}

async function loadTree(){
  const res=await fetch('/api/notes/tree').then(r=>r.json()).catch(()=>null);
  if(!res) return;
  TREE=res.tree; FLAT=[]; BY_PATH=new Map(); BY_BASE=new Map(); flatten(TREE);
  renderTree(); flashSync();
}
function renderTree(){
  const tree=$('vault-tree');
  const q=($('vault-search-input').value||'').toLowerCase().trim();
  tree.innerHTML='';
  if(q){ renderSearchResults(tree, q); return; }
  if(!TREE.length){ tree.innerHTML='<div class="tree-empty">Bóveda vacía.<br>Crea tu primera nota<br>o importa una bóveda.</div>'; return; }
  const frag=document.createDocumentFragment();
  buildTreeDOM(TREE, frag, 0, '');
  tree.appendChild(frag);
}
// Una fila de resultado (opcionalmente con fragmento de texto resaltado).
function hitRow(it, snippetHtml, terms){
  const row=document.createElement('div');
  row.className='tree-row search-hit'+(it.type==='file'?' is-file':'')+((current&&current.path===it.path)?' active':'');
  const ico=it.type==='note'?iconNote:(IMG_EXT.includes(it.ext)?iconImg:iconFile);
  const dir=it.path.split('/').slice(0,-1).join('/');
  const sub=snippetHtml?`<span class="hit-snippet">${snippetHtml}</span>`:(dir?`<span class="hit-path">${esc(dir)}</span>`:'');
  // Mismo botón de "tres puntos" que en el árbol normal, para poder borrar /
  // imprimir / etc. desde los resultados de búsqueda.
  row.innerHTML=`${ico}<span class="hit-text"><span class="label">${esc(it.name)}</span>${sub}</span><button class="row-menu" aria-label="Opciones de ${esc(it.name)}">${iconDots}</button>`;
  row.setAttribute('tabindex','0');
  row.addEventListener('click', e=>{
    if(e.target.closest('.row-menu')) return;
    if(it.type==='note') openNote(it.path, terms);
    else window.open(assetUrl(it.path),'_blank');
  });
  row.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();row.click();}
    if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();
      const rows=[...document.querySelectorAll('#vault-tree .tree-row')];
      const i=rows.indexOf(row);const next=rows[i+(e.key==='ArrowDown'?1:-1)];if(next)next.focus();}});
  row.querySelector('.row-menu').addEventListener('click', e=>{
    e.stopPropagation();
    showCtxMenu(e, it);
  });
  return row;
}
function hlTerms(text, terms){ let h=esc(text);
  terms.forEach(t=>{ if(!t) return; const re=new RegExp('('+t.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+')','ig'); h=h.replace(re,'<mark>$1</mark>'); });
  return h; }
let searchSeq=0;
// Coincidencias por NOMBRE/ruta (instantáneo, cliente) + por CONTENIDO (servidor, async).
function renderSearchResults(tree, q){
  const terms=q.split(/\s+/).filter(Boolean);
  // Solo buscamos NOTAS: excluimos imágenes, adjuntos y carpetas de los resultados.
  const nameMatches=FLAT.filter(f=>{if(f.type!=='note') return false; const hay=(f.name+' '+f.path).toLowerCase(); return terms.every(t=>hay.includes(t));});
  const namePaths=new Set(nameMatches.map(f=>f.path));
  const frag=document.createDocumentFragment();
  if(nameMatches.length){
    const lbl=document.createElement('div'); lbl.className='search-section'; lbl.textContent='Nombres ('+nameMatches.length+')'; frag.appendChild(lbl);
    nameMatches.slice(0,300).forEach(it=>frag.appendChild(hitRow(it, null, terms)));
  }
  const cwrap=document.createElement('div'); cwrap.id='content-results';
  cwrap.innerHTML='<div class="search-section">En el contenido <span class="search-spin">buscando…</span></div>';
  frag.appendChild(cwrap);
  tree.appendChild(frag);
  searchContent(q, namePaths);
}
async function searchContent(q, namePaths){
  const seq=++searchSeq;
  const terms=q.split(/\s+/).filter(Boolean);
  let data=null;
  try{ data=await fetch('/api/notes/search?q='+encodeURIComponent(q)).then(r=>r.json()); }catch(e){}
  if(seq!==searchSeq) return;                       // ignora respuestas obsoletas
  const wrap=$('content-results'); if(!wrap) return;
  const extra=((data&&data.results)||[]).filter(r=>!namePaths.has(r.path));
  if(!extra.length){ wrap.innerHTML = namePaths.size ? '' : '<div class="tree-empty">Sin resultados</div>'; return; }
  wrap.innerHTML='';
  const lbl=document.createElement('div'); lbl.className='search-section'; lbl.textContent='En el contenido ('+extra.length+(extra.length>=100?'+':'')+')'; wrap.appendChild(lbl);
  extra.forEach(r=>wrap.appendChild(hitRow({type:'note', name:r.name, path:r.path}, hlTerms(r.snippet||'', terms), terms)));
}
function allFolderPaths(items, acc){ items.forEach(it=>{ if(it.type==='folder'){ acc.push(it.path); allFolderPaths(it.children||[], acc);} }); return acc; }
function expandAll(){ allFolderPaths(TREE, []).forEach(p=>expanded.add(p)); persistExpanded(); renderTree(); }
function collapseAll(){ expanded.clear(); persistExpanded(); renderTree(); }
function syncSearchClear(){ $('vault-search').classList.toggle('has-value', !!$('vault-search-input').value); }
function toggleSearch(force){
  const box=$('vault-search'); const show = (force!==undefined) ? force : box.classList.contains('hidden');
  box.classList.toggle('hidden', !show);
  $('btn-search').classList.toggle('on', show);
  $('btn-search').setAttribute('aria-pressed', show.toString());
  if(show){ $('vault-search-input').focus(); }
  else if($('vault-search-input').value){ $('vault-search-input').value=''; renderTree(); }
  syncSearchClear();
}

/* ════════════ Open / edit / save ════════════ */
async function openNote(path, terms, opts){
  opts = opts || {};
  // Si la nota ya está en otra pestaña, conmutar a ella en lugar de duplicar (estilo Obsidian).
  if(!opts._fromTab){
    const dup = tabs.findIndex((t,i)=> i!==activeTabIdx && t.path===path);
    if(dup >= 0){ return switchToTab(dup); }
  }
  if(dirty) await saveNow();
  const res=await fetch('/api/notes/file?path='+encodeURIComponent(path)).then(r=>r.json());
  if(res.error){ if(opts.silent) return false; alert(res.error); loadTree(); return false; }
  current={path:res.path, name:res.name, content:res.content}; dirty=false;
  $('vault-empty').style.display='none'; $('vault-toolbar').style.display='flex'; $('vault-body').style.display='flex';
  const parts=res.path.split('/');
  const noteCrumb='<span class="crumb-note" title="Ir al inicio de la nota">'+esc(res.name)+'</span>';
  if(parts.length>1){const fp=parts.slice(0,-1);const ch=fp.map((seg,i)=>{const p=fp.slice(0,i+1).join('/');return '<span class="crumb crumb-link" data-path="'+esc(p)+'">'+esc(seg)+'</span>';}).join('<span class="crumb"> / </span>');$('vault-title').innerHTML=ch+'<span class="crumb"> / </span>'+noteCrumb;}else{$('vault-title').innerHTML=noteCrumb;}
  if(ED) ED.set(res.content.replace(/\n+$/, '') + '\n\n\n\n\n');  // 5 blank lines → clickable space below last block
  dirty=false; clearTimeout(saveTimer);   // ED.set dispara onChange: ignora ese "cambio" inicial (no es edición del usuario)
  // Restaurar el foco al editor inmediatamente tras ED.set para evitar la ventana de fuga
  // de foco que provoca pérdida del primer carácter al escribir rápido tras cambiar de nota.
  if(ED) try { ED.view.focus(); } catch(_){}
  setStatus('Guardado', true);
  applyViewMode();   // respeta el modo elegido (lectura por defecto) al abrir la nota
  document.querySelectorAll('.tree-row.active').forEach(r=>r.classList.remove('active'));
  const row=document.querySelector(`.tree-row[data-path="${cssEsc(path)}"]`); if(row) row.classList.add('active');
  if(window.innerWidth<760) $('vault').classList.add('side-hidden');
  if(ED) ED.view.scrollDOM.scrollTop=0;
  if(terms && terms.length) jumpToMatch(terms);   // venido de un resultado de búsqueda
  // Pestañas: actualizar la activa (o crear la primera) con esta ruta.
  if(activeTabIdx < 0 || tabs.length === 0){ tabs.push({path:res.path, history:[], idx:-1}); activeTabIdx = 0; }
  else { tabs[activeTabIdx].path = res.path; }
  pushHistory(res.path);
  renderTabs();
  updateNavButtons();
  return true;
}
/* ════════════ Pestañas con historial por pestaña (estilo Obsidian) ════════════ */
const tabs = [];          // [{path, history:[paths], idx:int}]
let activeTabIdx = -1;
let navSuppress = false;
let focusActiveTab = false;
function activeTab(){ return tabs[activeTabIdx] || null; }
function updateNavButtons(){
  const back=$('btn-nav-back'), fwd=$('btn-nav-fwd'); const t=activeTab();
  if(back) back.disabled = !t || t.idx <= 0;
  if(fwd)  fwd.disabled  = !t || t.idx >= t.history.length - 1;
}
function pushHistory(path){
  if(navSuppress) return;
  const t = activeTab(); if(!t) return;
  if(t.history[t.idx] === path) return;
  t.history.length = t.idx + 1;
  t.history.push(path);
  t.idx = t.history.length - 1;
}
async function navStep(delta){
  const t = activeTab(); if(!t) return;
  const target = t.idx + delta;
  if(target < 0 || target >= t.history.length) return;
  navSuppress = true;
  t.idx = target;
  try { await openNote(t.history[target], undefined, {_fromTab:true}); }
  finally { navSuppress = false; updateNavButtons(); }
}
function tabNameFromPath(p){ return (p.split('/').pop() || p).replace(/\.md$/i, ''); }
const TABS_STORAGE_KEY = 'vault-tabs-state';
function saveTabsState(){
  try{
    localStorage.setItem(TABS_STORAGE_KEY, JSON.stringify({
      tabs: tabs.map(t => ({path: t.path})),
      activeTabIdx
    }));
  }catch(_){}
}
async function restoreTabsState(){
  let s; try{ s = JSON.parse(localStorage.getItem(TABS_STORAGE_KEY)||'null'); }catch(_){}
  if(!s || !Array.isArray(s.tabs) || s.tabs.length === 0) return;
  // Rehidrata pestañas (sin cargar contenido aún).
  for(const t of s.tabs) if(t && t.path) tabs.push({path:t.path, history:[], idx:-1});
  if(!tabs.length) return;
  let target = Math.max(0, Math.min(s.activeTabIdx|0, tabs.length-1));
  activeTabIdx = target;
  renderTabs();
  // Intenta abrir la pestaña activa; si la nota ya no existe, ciérrala y prueba con la siguiente.
  while(tabs.length){
    const ok = await openNote(tabs[activeTabIdx].path, undefined, {silent:true, _fromTab:true});
    if(ok) break;
    tabs.splice(activeTabIdx, 1);
    if(!tabs.length){ activeTabIdx = -1; renderTabs(); return; }
    activeTabIdx = Math.min(activeTabIdx, tabs.length-1);
    renderTabs();
  }
}
function renderTabs(){
  const bar = $('tab-bar'); if(!bar) return;
  saveTabsState();
  if(tabs.length <= 1){ bar.classList.remove('show'); bar.innerHTML=''; return; }
  bar.setAttribute('role','tablist'); bar.setAttribute('aria-label','Notas abiertas');
  bar.classList.add('show'); bar.innerHTML='';
  tabs.forEach((t, i)=>{
    const el = document.createElement('div');
    el.className = 'tab-item' + (i === activeTabIdx ? ' active' : '');
    el.title = t.path;
    el.setAttribute('role','tab');
    el.setAttribute('aria-selected',(i===activeTabIdx).toString());
    el.setAttribute('tabindex',i===activeTabIdx?'0':'-1');
    el.innerHTML = `<span class="tab-name">${esc(tabNameFromPath(t.path))}</span><span class="tab-close" title="Cerrar pestaña" aria-label="Cerrar pestaña">×</span>`;
    el.addEventListener('click', e=>{
      if(e.target.closest('.tab-close')){ e.stopPropagation(); closeTab(i); return; }
      if(i !== activeTabIdx) switchToTab(i);
    });
    el.addEventListener('mousedown', e=>{ if(e.button===1){ e.preventDefault(); closeTab(i); } });
    el.addEventListener('keydown', e=>{
      if(e.key==='ArrowLeft'){e.preventDefault();if(i>0){focusActiveTab=true;switchToTab(i-1);}}
      if(e.key==='ArrowRight'){e.preventDefault();if(i<tabs.length-1){focusActiveTab=true;switchToTab(i+1);}}
      // Delete sin modificador no cierra pestaña (confuso con navegación del navegador)
    });
    bar.appendChild(el);
  });
  if(focusActiveTab){focusActiveTab=false;setTimeout(()=>bar.querySelector('.tab-item.active')?.focus(),30);}
}
async function switchToTab(idx){
  if(idx < 0 || idx >= tabs.length) return;
  activeTabIdx = idx;
  navSuppress = true;                       // cambiar de pestaña no añade entrada al historial
  try {
    const ok = await openNote(tabs[idx].path, undefined, {silent:true, _fromTab:true});
    if(!ok){ /* nota ya no existe en disco → cerrar pestaña rota silenciosamente */
      tabs.splice(idx, 1);
      if(tabs.length === 0){
        activeTabIdx = -1; current=null; dirty=false;
        $('vault-toolbar').style.display='none'; $('vault-body').style.display='none'; $('vault-empty').style.display='flex';
        document.querySelectorAll('.tree-row.active').forEach(r=>r.classList.remove('active'));
        renderTabs();
      } else {
        activeTabIdx = Math.min(idx, tabs.length - 1);
        renderTabs();
        await openNote(tabs[activeTabIdx].path, undefined, {silent:true, _fromTab:true});
      }
    }
  } finally {
    navSuppress = false;
    updateNavButtons();
  }
}
async function openInNewTab(path){
  const ex = tabs.findIndex(t => t.path === path);
  if(ex >= 0) return switchToTab(ex);
  tabs.push({path, history:[], idx:-1});
  activeTabIdx = tabs.length - 1;
  renderTabs();
  return openNote(path);
}
async function closeTab(idx){
  const wasActive = idx === activeTabIdx;
  if(wasActive && dirty) await saveNow();                 // no perder edits al cerrar la pestaña activa
  tabs.splice(idx, 1);
  if(tabs.length === 0){
    activeTabIdx = -1; current = null; dirty = false;
    $('vault-toolbar').style.display='none'; $('vault-body').style.display='none'; $('vault-empty').style.display='flex';
    document.querySelectorAll('.tree-row.active').forEach(r=>r.classList.remove('active'));
    renderTabs(); return;
  }
  if(wasActive){
    activeTabIdx = Math.min(idx, tabs.length - 1);
    renderTabs();
    await openNote(tabs[activeTabIdx].path);
  } else {
    if(activeTabIdx > idx) activeTabIdx--;
    renderTabs();
  }
}

// Coloca el cursor del editor en la primera coincidencia y hace scroll (CM
// revela ese bloque en crudo automáticamente al tener el cursor dentro).
function jumpToMatch(terms){
  if(!ED) return;
  const list=terms.filter(Boolean); if(!list.length) return;
  const text=ED.getValue().toLowerCase();
  let pos=-1; list.forEach(t=>{const i=text.indexOf(t.toLowerCase()); if(i>=0&&(pos<0||i<pos))pos=i;});
  if(pos>=0){ try{ ED.view.dispatch({selection:{anchor:pos, head:pos}, scrollIntoView:true}); ED.focus(); }catch(e){} }
}
// Exporta una nota a PDF imprimiendo su vista previa renderizada (máxima fidelidad:
// KaTeX, código, imágenes, callouts…). El usuario elige "Guardar como PDF".
async function exportNotePDF(it, dark){
  if(!current || current.path!==it.path){ await openNote(it.path); await new Promise(r=>setTimeout(r,150)); }
  setStatus('Generando PDF…', false);
  const pp=$('print-pane');
  pp.innerHTML=renderMarkdown(ED?ED.getValue():((current&&current.content)||'')); postProcess(pp,0);
  await new Promise(r=>setTimeout(r,250));   // deja que rendericen KaTeX / imágenes
  try{
    // Las imágenes del vault se sirven con sesión y el Chromium del servidor no
    // la tiene, así que las incrustamos como data-URI antes de mandar el HTML.
    await Promise.all(Array.from(pp.querySelectorAll('img')).map(async img=>{
      const src=img.getAttribute('src')||'';
      if(!src || src.startsWith('data:')) return;
      try{
        const r=await fetch(src); if(!r.ok) return;
        const blob=await r.blob();
        img.setAttribute('src', await new Promise((res,rej)=>{const fr=new FileReader();fr.onload=()=>res(fr.result);fr.onerror=rej;fr.readAsDataURL(blob);}));
      }catch(_){}
    }));
    const base=(((current&&current.name)||it.name||'nota')).replace(/\.md$/i,'');
    const res=await fetch('/api/notes/pdf',{method:'POST',
      headers:{'Content-Type':'application/json','X-CSRFToken':CSRF},
      body:JSON.stringify({html:pp.innerHTML, title:base, dark:!!dark})});
    if(!res.ok) throw new Error('http '+res.status);
    const blob=await res.blob();
    const url=URL.createObjectURL(blob);
    const a=document.createElement('a'); a.href=url; a.download=(base||'nota')+'.pdf';
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(()=>URL.revokeObjectURL(url), 5000);
    setStatus('PDF generado', true);
  }catch(e){
    setStatus('Error al generar el PDF', false);
  }finally{
    pp.innerHTML='';
  }
}
function cssEsc(s){return (window.CSS&&CSS.escape)?CSS.escape(s):s.replace(/["\\]/g,'\\$&');}
// Renderiza UN bloque de markdown dentro del editor live-preview (reutiliza todo
// el pipeline: marked + KaTeX + resaltado + callouts + embeds/imágenes).
function renderBlockLP(src, container){ container.innerHTML=renderMarkdown(src); postProcess(container,0); }
// Lightbox: ver una imagen en grande (móvil y escritorio).
function openLightbox(src){ const lb=$('img-lightbox'); lb.querySelector('img').src=src; lb.classList.add('show'); lb.setAttribute('aria-hidden','false'); }
function closeLightbox(){ const lb=$('img-lightbox'); lb.classList.remove('show'); lb.setAttribute('aria-hidden','true'); lb.querySelector('img').removeAttribute('src'); }
// Zoom de la nota completa (texto + imágenes) con Ctrl + / Ctrl - / Ctrl 0.
let noteFs = parseFloat(localStorage.getItem('note-fs')||'1') || 1;
function applyNoteFs(){ if(ED) ED.dom.style.setProperty('--note-fs', noteFs.toFixed(2)); const rd=$('cm-reader'); if(rd) rd.style.setProperty('--note-fs', noteFs.toFixed(2)); updateZoomLabel(); }
function updateZoomLabel(){ const el=document.getElementById('zoom-val'); if(el) el.textContent=Math.round(noteFs*100)+'%'; }
function setNoteFs(v){ noteFs=Math.max(0.7, Math.min(2.4, +v.toFixed(2))); localStorage.setItem('note-fs', noteFs); applyNoteFs(); }
function setStatus(t,saved){const el=$('vault-status'); el.textContent=t; el.classList.toggle('saved',!!saved);}
function onEdit(){ dirty=true; setStatus('Editando…',false);
  clearTimeout(saveTimer); saveTimer=setTimeout(saveNow,900); }
async function saveNow(){
  if(!CAN_WRITE){ dirty=false; return; }
  if(!current||!dirty) return; clearTimeout(saveTimer);
  const content=(ED?ED.getValue():current.content).replace(/\n+$/, ''); current.content=content; dirty=false; setStatus('Guardando…',false);
  const res=await api('/api/notes/save',{path:current.path, content});
  if(res.success) setStatus('Guardado', true); else { setStatus('Error al guardar',false); dirty=true; }
}

/* ════════════ Modo lectura / edición ════════════ */
/* 'read' = nota renderizada (bonita, sin editar) · 'edit' = editor CodeMirror.
   Por defecto las notas se abren en lectura; la preferencia se recuerda. */
let viewMode = CAN_WRITE ? (localStorage.getItem('cogny-view-mode') || 'read') : 'read';
function renderReader(){
  const rd=$('cm-reader'); if(!rd) return;
  const md=(current&&current.content)||'';
  rd.innerHTML=renderMarkdown(md); postProcess(rd,0);
  rd.scrollTop=0;
}
function applyViewMode(){
  const btn=$('btn-view-toggle'), host=$('cm-host'), rd=$('cm-reader');
  const reading = viewMode==='read';
  if(btn){ btn.classList.toggle('reading', reading);
    btn.title = reading ? 'Editar nota' : 'Modo lectura'; }
  if(host) host.style.display = reading ? 'none' : 'flex';
  if(rd) rd.style.display = reading ? 'block' : 'none';
  if(reading) renderReader();
  else if(ED) try { ED.view.focus(); } catch(_){}
}
function toggleViewMode(){
  if(!CAN_WRITE) return;   // sin escritura no hay modo edición
  // Al salir de edición, sincroniza el contenido más reciente del editor antes de renderizar.
  if(viewMode==='edit' && ED && current) current.content = ED.getValue().replace(/\n+$/, '');
  viewMode = viewMode==='read' ? 'edit' : 'read';
  localStorage.setItem('cogny-view-mode', viewMode);
  applyViewMode();
}

/* ════════════ Editor Live Preview (CodeMirror) ════════════ */
function initEditor(){
  if(ED || !window.BaluCM){ return; }
  ED = BaluCM.create($('cm-host'), { doc:'', renderBlock:renderBlockLP, onChange:()=>onEdit() });
  window.ED = ED;
  applyNoteFs();
  const dom = ED.dom;
  // Atrapa Tab/Shift+Tab dentro del editor para que el foco no salte a los
  // botones/sidebar de la página (comportamiento por defecto de CM6 por accesibilidad).
  dom.addEventListener('keydown', e=>{
    if(e.key!=='Tab') return;
    e.preventDefault(); e.stopPropagation();
    const view=ED.view; if(!view) return;
    const st=view.state;
    if(e.shiftKey){
      const changes=[]; const seen=new Set();
      for(const r of st.selection.ranges){
        const l1=st.doc.lineAt(r.from).number, l2=st.doc.lineAt(r.to).number;
        for(let n=l1;n<=l2;n++){ if(seen.has(n)) continue; seen.add(n);
          const ln=st.doc.line(n);
          const m=ln.text.match(/^(\t| {1,4})/);
          if(m) changes.push({from:ln.from, to:ln.from+m[0].length});
        }
      }
      if(changes.length) view.dispatch({changes});
    } else {
      view.dispatch(st.replaceSelection('\t'));
    }
  });
  // Aislar el editor del teclado: cualquier pérdida de foco que NO venga de un clic/touch
  // reciente (ni de un input/textarea legítimo como la búsqueda o un modal) vuelve a
  // poner el foco en el editor. Solo el ratón puede sacarte del editor.
  dom.addEventListener('focusout', ()=>{
    setTimeout(()=>{
      if(!current) return;                                                            // sin nota abierta
      const a=document.activeElement;
      if(!a || dom.contains(a)) return;                                               // sigue en el editor
      if(performance.now() - lastPointerAt < 350) return;                             // clic/toque reciente: respetar
      if(a.isContentEditable || ['INPUT','TEXTAREA','SELECT'].includes(a.tagName)) return;
      if(a.closest('.modal-back')||a.closest('#ctx-menu')||a.closest('#input-dialog')||a.closest('#confirm-dialog')) return;
      try { ED.view.focus(); } catch(_){}
    }, 0);
  });
  // Navegación de wikilinks / tags / embeds dentro de los bloques renderizados.
  dom.addEventListener('click', async e=>{
    const im=e.target.closest('img');
    if(im && im.closest('.cm-lp-block')){ e.preventDefault(); e.stopPropagation(); openLightbox(im.src); return; }
    const wl=e.target.closest('.wikilink');
    if(wl){ const name=(wl.dataset.target||'').split('#')[0].split('|')[0].trim();
      const f=findFileByName(name);
      if(f) openNote(f.path);
      else showConfirmDialog('Crear nota',`La nota «${name}» no existe. ¿Crearla?`,'Crear',async()=>{
        const res=await api('/api/notes/create',{parent: current?current.path.split('/').slice(0,-1).join('/'):'', name, type:'note'});
        if(res.error){alert(res.error);return;} revealPath(res.path); await loadTree(); openNote(res.path);});
      return; }
    const tg=e.target.closest('.tag-pill');
    if(tg){ toggleSearch(true); $('vault-search-input').value='#'+tg.dataset.tag; syncSearchClear(); renderTree(); return; }
    const op=e.target.closest('.embed-title[data-open]');
    if(op){ openNote(op.dataset.open); }
  });
  // Doble clic en imagen de bloque LP → lightbox
  dom.addEventListener('dblclick', e=>{
    const im=e.target.closest('img');
    if(im && im.closest('.cm-lp-block')){ openLightbox(im.src); }
  });
  // FIX cursor: al clicar un bloque renderizado (live-preview) CM6 coloca mal el
  // cursor (lo lleva al inicio de la linea, o a la linea equivocada si hay lineas
  // en blanco). posAtCoords() SI devuelve la posicion exacta, asi que tras el clic
  // corregimos la seleccion a esa posicion. Solo para clics simples (sin arrastre)
  // y fuera de elementos interactivos (enlaces, imagenes, checkboxes, codigo).
  let _lpDownX=0,_lpDownY=0,_lpDownPos=null;
  dom.addEventListener('mousedown', e=>{
    _lpDownPos=null;
    if(e.button!==0) return;
    const blk=e.target.closest('.cm-lp-block'); if(!blk) return;
    if(e.target.closest('a,button,input,textarea,img,.wikilink,.tag-pill,.embed-title,.internal-embed,.code-copy,.cm-code-line,.task-list-item-checkbox,input[type=checkbox]')) return;
    const v=ED.view; if(!v) return;
    const pos=v.posAtCoords({x:e.clientX,y:e.clientY});
    if(pos==null) return;
    _lpDownX=e.clientX; _lpDownY=e.clientY; _lpDownPos=pos;
  }, true);
  dom.addEventListener('mouseup', e=>{
    if(_lpDownPos==null) return;
    const pos=_lpDownPos; _lpDownPos=null;
    // si hubo arrastre (seleccion), no tocar
    if(Math.abs(e.clientX-_lpDownX)>3 || Math.abs(e.clientY-_lpDownY)>3) return;
    const v=ED.view; if(!v) return;
    requestAnimationFrame(()=>{ try{
      const cur=v.state.selection.main;
      if(cur.empty && cur.head!==pos){ v.dispatch({selection:{anchor:pos}}); v.focus(); }
      // 2a pasada: revelada ya la fuente de la linea, posAtCoords es preciso por
      // caracter; afinamos a donde se hizo clic (solo si cae en la MISMA linea).
      requestAnimationFrame(()=>{ try{
        const pos2=v.posAtCoords({x:_lpDownX,y:_lpDownY});
        if(pos2==null) return;
        const l1=v.state.doc.lineAt(pos).number, l2=v.state.doc.lineAt(pos2).number;
        const c=v.state.selection.main;
        if(l1===l2 && c.empty && c.head!==pos2){ v.dispatch({selection:{anchor:pos2}}); }
      }catch(_){}});
    }catch(_){}});
  }, true);
  // Image LP blocks: clicking them places cursor near the image.
  // The 5 blank lines appended in openNote ensure there are always real text
  // lines BELOW the image that the user can click to continue writing.
  // Clic derecho sobre imagen → menú "Borrar imagen".
  dom.addEventListener('contextmenu', e=>{
    const img=e.target.closest('img'); if(!img) return;
    const info=imageInfoFromEl(img); if(!info) return;
    e.preventDefault(); showImageCtxMenu(e, info);
  });
  // Pegar imágenes del portapapeles.
  dom.addEventListener('paste', e=>{
    const items=(e.clipboardData&&e.clipboardData.items)||[];
    for(const it of items){ if(it.kind==='file'&&it.type.startsWith('image/')){ e.preventDefault(); const f=it.getAsFile(); if(f) handleImageFile(f); return; } }
  });
  // Arrastrar y soltar imágenes.
  ['dragover','dragenter'].forEach(ev=>dom.addEventListener(ev, e=>{
    if(e.dataTransfer&&[...e.dataTransfer.types||[]].includes('Files')){ e.preventDefault(); dom.classList.add('drag'); }}));
  ['dragleave','dragend'].forEach(ev=>dom.addEventListener(ev, ()=>dom.classList.remove('drag')));
  dom.addEventListener('drop', e=>{ if(!e.dataTransfer||!e.dataTransfer.files.length) return;
    e.preventDefault(); dom.classList.remove('drag'); handleImageFiles([...e.dataTransfer.files]); });
}

/* ════════════ Paneles redimensionables (escritorio): lista / editor / vista ════════════ */
(function setupResizers(){
  const PX=e=>e.touches?e.touches[0].clientX:e.clientX;
  // Crea el comportamiento de arrastre de un divisor.
  function makeDrag(rz, onMove, onEnd){
    if(!rz) return;
    function down(e){ if(window.innerWidth<768) return; e.preventDefault();
      const x0=PX(e); const ctx=onMove.start();
      rz.classList.add('dragging'); document.body.style.cursor='col-resize'; document.body.style.userSelect='none';
      function move(ev){ onMove.run(ctx, PX(ev)-x0); if(ev.cancelable) ev.preventDefault(); }
      function up(){ rz.classList.remove('dragging'); document.body.style.cursor=''; document.body.style.userSelect='';
        onEnd&&onEnd(ctx);
        window.removeEventListener('mousemove',move); window.removeEventListener('mouseup',up);
        window.removeEventListener('touchmove',move); window.removeEventListener('touchend',up); }
      window.addEventListener('mousemove',move); window.addEventListener('mouseup',up);
      window.addEventListener('touchmove',move,{passive:false}); window.addEventListener('touchend',up);
    }
    rz.addEventListener('mousedown',down); rz.addEventListener('touchstart',down,{passive:false});
  }
  // 1) Ancho de la columna del árbol
  const side=$('vault-side'), KEY_S='vault-side-w';
  const sw=parseInt(localStorage.getItem(KEY_S)||'',10);
  if(sw>=180 && window.innerWidth>=768) side.style.width=sw+'px';
  makeDrag($('rz-side'),
    {start:()=>({w:side.offsetWidth}), run:(c,dx)=>{ side.style.width=Math.max(180,Math.min(560,c.w+dx))+'px'; }},
    ()=>localStorage.setItem(KEY_S, side.offsetWidth));
})();

/* ════════════ Diálogos inline (prompt/confirm accesibles) ════════════ */
function showInputDialog(title, defaultVal, onOk, opts){
  opts=opts||{};
  const dlg=$('input-dialog'),field=$('id-field'),desc=$('id-desc');
  $('id-title').textContent=title;
  if(opts.desc){desc.textContent=opts.desc;desc.style.display='';}else desc.style.display='none';
  field.value=defaultVal||''; field.placeholder=opts.placeholder||'';
  $('id-ok').textContent=opts.okLabel||'Aceptar';
  dlg.style.display=''; dlg.classList.add('show');
  const prev=document.activeElement;
  setTimeout(()=>{field.focus();if(defaultVal)field.select();},60);
  function close(ok){
    dlg.classList.remove('show'); dlg.style.display='none';
    okBtn.removeEventListener('click',okH); cancelBtn.removeEventListener('click',cancelH);
    field.removeEventListener('keydown',keyH);
    if(ok && field.value.trim()) onOk(field.value.trim());
    if(prev&&prev.focus) try{prev.focus();}catch(_){}
  }
  function keyH(e){if(e.key==='Enter'){e.preventDefault();close(true);}if(e.key==='Escape'){e.preventDefault();close(false);}}
  const okBtn=$('id-ok'),cancelBtn=$('id-cancel');
  const okH=()=>close(true),cancelH=()=>close(false);
  okBtn.addEventListener('click',okH); cancelBtn.addEventListener('click',cancelH);
  field.addEventListener('keydown',keyH);
}
function showConfirmDialog(title, msg, okLabel, onOk, onCancel){
  const dlg=$('confirm-dialog');
  $('cd-title').textContent=title; $('cd-msg').textContent=msg;
  $('cd-ok').textContent=okLabel||'Confirmar';
  dlg.style.display=''; dlg.classList.add('show');
  const prev=document.activeElement;
  setTimeout(()=>$('cd-cancel').focus(),60);
  function close(ok){
    dlg.classList.remove('show'); dlg.style.display='none';
    okBtn.removeEventListener('click',okH); cancelBtn.removeEventListener('click',cancelH);
    dlg.removeEventListener('keydown',keyH);
    if(ok) onOk(); else if(onCancel) onCancel();
    if(prev&&prev.focus) try{prev.focus();}catch(_){}
  }
  function keyH(e){if(e.key==='Escape'){e.preventDefault();close(false);}}
  const okBtn=$('cd-ok'),cancelBtn=$('cd-cancel');
  const okH=()=>close(true),cancelH=()=>close(false);
  okBtn.addEventListener('click',okH); cancelBtn.addEventListener('click',cancelH);
  dlg.addEventListener('keydown',keyH);
}

function confirmAsync(title, msg, okLabel){
  return new Promise(resolve=>showConfirmDialog(title, msg, okLabel, ()=>resolve(true), ()=>resolve(false)));
}
/* ════════════ Create / rename / delete ════════════ */
function currentFolderContext(){
  const active=document.querySelector('.tree-row.active');
  if(active){ if(active.dataset.type==='folder') return active.dataset.path;
    const p=active.dataset.path.split('/'); p.pop(); return p.join('/'); }
  return '';
}
// Abre todas las carpetas ancestro de una ruta para que el elemento sea visible.
function revealPath(path){ const parts=path.split('/'); let acc='';
  for(let i=0;i<parts.length-1;i++){ acc=acc?acc+'/'+parts[i]:parts[i]; expanded.add(acc); } persistExpanded(); }
async function newNote(parent){
  if(!guardWrite()) return;
  showInputDialog('Nueva nota','',async name=>{
    const res=await api('/api/notes/create',{parent: parent ?? currentFolderContext(), name, type:'note'});
    if(res.error){alert(res.error);return;} revealPath(res.path); await loadTree(); openNote(res.path);
  },{placeholder:'Nombre de la nota',okLabel:'Crear'});
}
async function newFolder(parent){
  if(!guardWrite()) return;
  showInputDialog('Nueva carpeta','',async name=>{
    const res=await api('/api/notes/create',{parent: parent ?? currentFolderContext(), name, type:'folder'});
    if(res.error){alert(res.error);return;} revealPath(res.path); expanded.add(res.path); persistExpanded(); await loadTree();
  },{placeholder:'Nombre de la carpeta',okLabel:'Crear'});
}
async function renameItem(it){
  if(!guardWrite()) return;
  showInputDialog('Renombrar',it.name,async name=>{
    if(name===it.name) return;
    const res=await api('/api/notes/rename',{path:it.path, name}); if(res.error){alert(res.error);return;}
    const wasOpen=current&&current.path===it.path;
    const remap = p => (p===it.path || p.startsWith(it.path+'/')) ? res.path + p.slice(it.path.length) : p;
    tabs.forEach(t=>{ t.path = remap(t.path); t.history = t.history.map(remap); });
    await loadTree(); renderTabs();
    if(wasOpen) openNote(res.path);
  },{okLabel:'Renombrar'});
}
async function deleteItem(it){
  if(!guardWrite()) return;
  const what=it.type==='folder'?'la carpeta y todo su contenido':(it.type==='note'?'la nota':'el archivo');
  showConfirmDialog('Borrar',`¿Borrar ${what} «${it.name}»?`,'Sí, borrar',async ()=>{
    const res=await api('/api/notes/delete',{path:it.path}); if(res.error){alert(res.error);return;}
    const isHit = p => p===it.path || p.startsWith(it.path+'/');
    for(let i=tabs.length-1;i>=0;i--){
      const t = tabs[i];
      for(let j=t.history.length-1;j>=0;j--) if(isHit(t.history[j])){ t.history.splice(j,1); if(j<=t.idx) t.idx--; }
      if(isHit(t.path)){
        tabs.splice(i,1);
        if(i < activeTabIdx) activeTabIdx--;
        else if(i === activeTabIdx) activeTabIdx = -1;
      }
    }
    if(current&&isHit(current.path)){
      current=null; dirty=false; $('vault-toolbar').style.display='none'; $('vault-body').style.display='none'; $('vault-empty').style.display='flex'; }
    if(tabs.length>0 && (activeTabIdx<0 || activeTabIdx>=tabs.length)){
      activeTabIdx = 0; openNote(tabs[0].path);
    }
    renderTabs(); updateNavButtons();
    loadTree();
  });
}

/* ════════════ Context menu ════════════ */
function showCtxMenu(e,it){
  const m=$('ctx-menu'); let html='';
  if(it.type==='folder' && CAN_WRITE){
    html+=`<button data-act="new-note">${iconNote.replace('ico','')}Nueva nota aquí</button>`;
    html+=`<button data-act="new-folder">${iconFolder(false).replace('ico','')}Nueva subcarpeta</button><div class="ctx-sep"></div>`;
  }
  if(it.type==='note'){
    html+=`<button data-act="open-new-tab"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M19 19H5V5h7V3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7h-2v7zM14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3h-7z"/></svg>Abrir en nueva pestaña</button><div class="ctx-sep"></div>`;
    const pdfIco=`<svg viewBox="0 0 24 24" fill="currentColor"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6zm-1 7V3.5L18.5 9H13zM8 13h1.5a1.5 1.5 0 0 1 0 3H9v2H8v-5zm1.5 2a.5.5 0 0 0 0-1H9v1h.5zM12 13h1.5a1.5 1.5 0 0 1 1.5 1.5v2A1.5 1.5 0 0 1 13.5 18H12v-5zm1 4a.5.5 0 0 0 .5-.5v-2a.5.5 0 0 0-.5-.5v3zm3-4h2v1h-1v1h1v1h-1v2h-1v-5z"/></svg>`;
    html+=`<button data-act="pdf">${pdfIco}Exportar a PDF</button>`;
    html+=`<button data-act="pdf-dark"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 3a9 9 0 1 0 9 9c0-.46-.04-.92-.1-1.36a5.39 5.39 0 0 1-4.4 2.26 5.4 5.4 0 0 1-5.4-5.4c0-1.81.89-3.42 2.26-4.4-.44-.06-.9-.1-1.36-.1z"/></svg>Exportar a PDF (oscuro)</button>
    ${CAN_WRITE ? `<button data-act="share"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M18 16.08c-.76 0-1.44.3-1.96.77L8.91 12.7c.05-.23.09-.46.09-.7s-.04-.47-.09-.7l7.05-4.11c.54.5 1.25.81 2.04.81a3 3 0 1 0-3-3c0 .24.04.47.09.7L8.04 9.81C7.5 9.31 6.79 9 6 9a3 3 0 1 0 0 6c.79 0 1.5-.31 2.04-.81l7.12 4.16c-.05.21-.08.43-.08.65 0 1.61 1.31 2.92 2.92 2.92 1.61 0 2.92-1.31 2.92-2.92s-1.31-2.92-2.92-2.92z"/></svg>Compartir</button>` : ''}<div class="ctx-sep"></div>`;
  }
  if(CAN_WRITE){
  html+=`<button data-act="rename"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg>Renombrar</button>`;
  html+=`<button data-act="delete" class="danger"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M6 19a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>Borrar</button>`;
  }
  // Con acceso de sólo lectura sobre un adjunto no queda ninguna acción:
  // mejor no abrir el menú que enseñar un recuadro vacío.
  if(!html.trim()){ hideCtx(); return; }
  m.setAttribute('role','menu');
  m.innerHTML=html; m.style.display='block';
  m.style.left=Math.min(e.clientX, window.innerWidth-190)+'px';
  m.style.top=Math.min(e.clientY, window.innerHeight-m.offsetHeight-10)+'px';
  const _ctxBtns=[...m.querySelectorAll('button')];
  _ctxBtns.forEach((b,_ci)=>{
    b.setAttribute('role','menuitem');
    b.setAttribute('tabindex',_ci===0?'0':'-1');
    b.addEventListener('keydown',_ek=>{
      if(_ek.key==='ArrowDown'){_ek.preventDefault();_ctxBtns[(_ci+1)%_ctxBtns.length].focus();}
      if(_ek.key==='ArrowUp'){_ek.preventDefault();_ctxBtns[(_ci-1+_ctxBtns.length)%_ctxBtns.length].focus();}
      if(_ek.key==='Escape'){_ek.preventDefault();hideCtx();}
    });
    b.onclick=()=>{ hideCtx(); const a=b.dataset.act;
      if(a==='new-note') newNote(it.path); else if(a==='new-folder') newFolder(it.path);
      else if(a==='open-new-tab') openInNewTab(it.path);
      else if(a==='pdf') exportNotePDF(it,false);
      else if(a==='pdf-dark') exportNotePDF(it,true);
      else if(a==='share') openShareModal(it);
      else if(a==='rename') renameItem(it); else if(a==='delete') deleteItem(it); };
  });
  setTimeout(()=>_ctxBtns[0]?.focus(),20);
}
function hideCtx(){ $('ctx-menu').style.display='none'; }
document.addEventListener('click', e=>{ if(!e.target.closest('#ctx-menu')) hideCtx(); });
document.addEventListener('scroll', hideCtx, true);

/* (Los clics de wikilink/tag/embed se gestionan en initEditor, sobre el editor CM.) */

/* ════════════ Compartir nota (enlace público, con contraseña opcional) ════════ */
let shareItem = null;
let sharePwOn = false;

function closeShareModal(){ $('share-modal').classList.remove('show'); shareItem=null; }

async function openShareModal(it){
  shareItem = it;
  $('share-modal').classList.add('show');
  $('share-loading').style.display=''; $('share-body').style.display='none';
  $('share-save').disabled = true; $('share-stop').style.display='none';
  sharePwOn = false;
  $('share-pw-switch').classList.remove('on'); $('share-pw-switch').setAttribute('aria-checked','false');
  $('share-pw-field').classList.remove('show'); $('share-pw-input').value='';
  try{
    let res = await fetch('/api/notes/share/status?path='+encodeURIComponent(it.path)).then(r=>r.json());
    if(!res.shared){
      // El enlace se genera en el acto al abrir el modal (sin contraseña por
      // defecto); "Guardar" queda para aplicar/quitar la contraseña después.
      res = await api('/api/notes/share/create', {path: it.path, password:''});
      if(res.error) throw new Error(res.error);
    }
    $('share-link-field').value = res.url;
    $('share-status-text').textContent = res.has_password ? 'Enlace activo · con contraseña' : 'Enlace activo · público';
    $('share-stop').style.display='';
    if(res.has_password){
      sharePwOn = true;
      $('share-pw-switch').classList.add('on'); $('share-pw-switch').setAttribute('aria-checked','true');
      $('share-pw-field').classList.add('show');
      $('share-pw-input').placeholder = 'Dejar en blanco para no cambiarla';
    }
  }catch(e){
    $('share-status-text').textContent = 'Error al generar el enlace';
  }
  $('share-loading').style.display='none'; $('share-body').style.display='';
  $('share-save').disabled = false;
}

$('share-pw-toggle-row').addEventListener('click', ()=>{
  sharePwOn = !sharePwOn;
  $('share-pw-switch').classList.toggle('on', sharePwOn);
  $('share-pw-switch').setAttribute('aria-checked', String(sharePwOn));
  $('share-pw-field').classList.toggle('show', sharePwOn);
  if(sharePwOn) setTimeout(()=>$('share-pw-input').focus(), 10);
});

$('share-save').addEventListener('click', async ()=>{
  if(!shareItem) return;
  const btn=$('share-save'); btn.disabled=true; btn.textContent='Guardando…';
  const password = sharePwOn ? $('share-pw-input').value : '';
  try{
    const res = await api('/api/notes/share/create', {path: shareItem.path, password});
    if(res.error){ alert(res.error); return; }
    $('share-link-field').value = res.url;
    $('share-status-text').textContent = res.has_password ? 'Enlace activo · con contraseña' : 'Enlace activo · público';
    $('share-stop').style.display='';
    if(res.has_password) $('share-pw-input').placeholder='Dejar en blanco para no cambiarla';
    $('share-pw-input').value='';
  }catch(e){
    alert('Error de red al compartir la nota');
  }finally{
    btn.disabled=false; btn.textContent='Guardar';
  }
});

$('share-copy-btn').addEventListener('click', async ()=>{
  const val=$('share-link-field').value; if(!val) return;
  try{ await navigator.clipboard.writeText(val); }
  catch(_){ $('share-link-field').select(); try{document.execCommand('copy');}catch(__){} }
  const btn=$('share-copy-btn'); const orig=btn.textContent;
  btn.textContent='¡Copiado!'; btn.classList.add('copied');
  setTimeout(()=>{ btn.textContent=orig; btn.classList.remove('copied'); }, 1400);
});

$('share-stop').addEventListener('click', async ()=>{
  if(!shareItem) return;
  if(!confirm('¿Dejar de compartir esta nota? El enlace actual dejará de funcionar.')) return;
  const res = await api('/api/notes/share/revoke', {path: shareItem.path});
  if(res.error){ alert(res.error); return; }
  closeShareModal();
});

$('share-cancel').addEventListener('click', closeShareModal);
$('share-modal').addEventListener('click', e=>{ if(e.target===$('share-modal')) closeShareModal(); });

/* Nota: el panel "Enlaces compartidos" vive en el modal global de Ajustes
   (templates/base.html), accesible desde el icono de la cabecera — el botón
   de la barra lateral se quitó por quedar duplicado con ese icono. */

/* ════════════ Imágenes: clic derecho → Eliminar (borra el archivo y la referencia) ════════════ */
const iconTrash='<svg viewBox="0 0 24 24" fill="currentColor"><path d="M6 19a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>';
// Quita del texto TODAS las referencias a un adjunto por su nombre de archivo,
// tanto embeds de Obsidian ![[archivo]] (con |tamaño o #sección) como imágenes ![](ruta).
function stripImageRefs(text, basename){
  const b=basename.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
  text=text.replace(new RegExp('!\\[\\[[^\\]\\n]*'+b+'[^\\]\\n]*\\]\\]','gi'),'');
  text=text.replace(new RegExp('!\\[[^\\]\\n]*\\]\\([^)\\n]*'+b+'[^)\\n]*\\)','gi'),'');
  return text.replace(/\n{3,}/g,'\n\n');
}
// Deduce la ruta del adjunto a partir de la imagen pulsada (embed o imagen normal).
function imageInfoFromEl(img){
  let path=null;
  const emb=img.closest('.internal-embed');
  if(emb && emb.dataset.target){
    const nm=emb.dataset.target.split('|')[0].split('#')[0].trim();
    const f=findFileByName(nm); if(f) path=f.path;
  }
  if(!path){ const src=img.getAttribute('src')||''; const m=src.match(/[?&]path=([^&]+)/); if(m) path=decodeURIComponent(m[1]); }
  return path ? {path, name:path.split('/').pop()} : null;
}
function showImageCtxMenu(e, info){
  if(!CAN_WRITE) return;
  const m=$('ctx-menu');
  // Dos pasos DENTRO del propio menú (sin confirm() del navegador, que no es
  // fiable en PWA/algunos navegadores): "Borrar imagen" → "¿Seguro? Sí, borrar".
  m.innerHTML=`<button data-act="del-img" class="danger">${iconTrash}Borrar imagen</button>`;
  m.style.display='block';
  m.style.left=Math.min(e.clientX, window.innerWidth-185)+'px';
  m.style.top=Math.min(e.clientY, window.innerHeight-m.offsetHeight-10)+'px';
  m.querySelector('[data-act="del-img"]').onclick=(ev)=>{
    ev.stopPropagation();   // evita que el clic global cierre el menú al reemplazar su contenido
    m.innerHTML=`<button data-act="del-yes" class="danger">${iconTrash}¿Seguro? Sí, borrar</button>`;
    m.querySelector('[data-act="del-yes"]').onclick=(ev2)=>{ ev2.stopPropagation(); hideCtx(); deleteImage(info); };
  };
}
async function deleteImage(info){
  if(!guardWrite()) return;
  if(!info || !current) return;
  setStatus('Borrando imagen…', false);
  const res=await api('/api/notes/delete',{path:info.path});
  if(res && res.error){ alert(res.error); setStatus('Error al borrar', false); return; }
  if(ED) ED.set(stripImageRefs(ED.getValue(), info.name));
  dirty=true; await saveNow();
  await loadTree();
  setStatus('Imagen borrada', true);
}
// (El menú contextual de imagen se engancha en initEditor, sobre el editor CM.)

/* ════════════ Imágenes: pegar / arrastrar / insertar ════════════ */
function insertIntoEditor(text){ if(ED){ ED.insert(text); onEdit(); } }
function uploadAsset(file){
  const fd=new FormData(); fd.append('file', file, file.name||'image.png'); fd.append('csrfmiddlewaretoken', CSRF);
  fd.append('dir', localStorage.getItem('vault-img-dir')||'');   // carpeta elegida (vacío = automático)
  return fetch('/api/notes/upload',{method:'POST', body:fd}).then(r=>r.json());
}
/* ════════════ Selector de carpeta para imágenes ════════════ */
function collectFolders(items, acc){ (items||[]).forEach(it=>{ if(it.type==='folder'){ acc.push(it.path); collectFolders(it.children, acc); } }); return acc; }
function openImgDirModal(){
  // Las imágenes se centralizan siempre en "Adjuntos" (forzado en el backend),
  // así que el selector de carpeta ya no aplica: mostramos solo el aviso.
  $('imgdir-list').innerHTML=
    '<div class="imgdir-info">'
    + '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M10 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z"/></svg>'
    + '<span>Todas las imágenes se guardan en <b>Adjuntos</b>.</span>'
    + '</div>';
  $('imgdir-modal').classList.add('show');
}
let imgBusy=false;
async function handleImageFile(file){
  if(!guardWrite()) return;
  if(!file || !file.type.startsWith('image/')) return;
  if(!current){ alert('Abre o crea una nota antes de añadir una imagen.'); return; }
  if(imgBusy){ return; }            // sube de una en una para no entrelazar inserciones
  imgBusy=true; setStatus('Subiendo imagen…', false);
  try{
    const res=await uploadAsset(file);
    if(res && res.success){
      await loadTree();             // refresca el índice ANTES de insertar, así el embed resuelve al renderizar
      insertIntoEditor('\n![['+res.name+']]\n');
      setStatus('Imagen añadida', true);
    } else { alert((res&&res.error)||'No se pudo subir la imagen'); setStatus('Editando…', false); }
  }catch(e){ alert('Error al subir la imagen'); setStatus('Editando…', false); }
  imgBusy=false;
}
async function handleImageFiles(files){
  for(const f of files){ if(f.type.startsWith('image/')) await handleImageFile(f); }
}
// (Pegar / arrastrar imágenes se engancha en initEditor, sobre el editor CM.)
// Botón de la barra + selector (esencial en móvil)
$('btn-insert-img').addEventListener('click', ()=>$('asset-file').click());
$('asset-file').addEventListener('change', e=>{ handleImageFiles([...e.target.files]); e.target.value=''; });

// Alternar lectura / edición (botón ojo/lápiz junto a «Guardado»).
$('btn-view-toggle').addEventListener('click', toggleViewMode);
// Navegación desde la nota renderizada en modo lectura (wikilinks, etiquetas, embeds, imágenes).
$('cm-reader').addEventListener('click', async e=>{
  const im=e.target.closest('img');
  if(im){ e.preventDefault(); openLightbox(im.src); return; }
  const wl=e.target.closest('.wikilink');
  if(wl){ const name=(wl.dataset.target||'').split('#')[0].split('|')[0].trim();
    const f=findFileByName(name); if(f) openNote(f.path); return; }
  const tg=e.target.closest('.tag-pill');
  if(tg){ toggleSearch(true); $('vault-search-input').value='#'+tg.dataset.tag; syncSearchClear(); renderTree(); return; }
  const op=e.target.closest('.embed-title[data-open]');
  if(op){ openNote(op.dataset.open); }
});

// Flechas atrás/adelante: navegan por el historial de notas abiertas.
$('btn-nav-back').addEventListener('click', ()=>navStep(-1));
$('btn-nav-fwd').addEventListener('click', ()=>navStep(+1));
updateNavButtons();

// Popover de zoom (lupa): − / % / +. Reaprovecha setNoteFs (clamp 0.7..2.4, paso 0.1).
$('btn-zoom').addEventListener('click', e=>{ e.stopPropagation();
  $('zoom-pop').classList.toggle('open'); updateZoomLabel(); });
$('zoom-in').addEventListener('click', e=>{ e.stopPropagation(); setNoteFs(noteFs+0.1); });
$('zoom-out').addEventListener('click', e=>{ e.stopPropagation(); setNoteFs(noteFs-0.1); });
$('zoom-val').addEventListener('click', e=>{ e.stopPropagation(); setNoteFs(1); });
document.addEventListener('click', e=>{
  if(!e.target.closest('#zoom-pop') && !e.target.closest('#btn-zoom'))
    $('zoom-pop').classList.remove('open');
});
updateZoomLabel();

/* ════════════ Barra de formato (estilo Word) ════════════ */
// Envuelve la selección (negrita, cursiva, código en línea, enlace…).
function fmtWrap(before, after, placeholder){
  if(!ED){ return; }
  const view=ED.view, sel=view.state.selection.main;
  const has=sel.from!==sel.to;
  const text=has?view.state.sliceDoc(sel.from, sel.to):(placeholder||'');
  view.dispatch({
    changes:{from:sel.from, to:sel.to, insert:before+text+after},
    selection:{anchor:sel.from+before.length, head:sel.from+before.length+text.length}
  });
  view.focus(); onEdit();
}
// Prefija la línea actual (encabezados, citas, listas).
function fmtLinePrefix(prefix){
  if(!ED){ return; }
  const view=ED.view, sel=view.state.selection.main;
  const line=view.state.doc.lineAt(sel.from);
  view.dispatch({
    changes:{from:line.from, to:line.from, insert:prefix},
    selection:{anchor:sel.from+prefix.length}
  });
  view.focus(); onEdit();
}
// Inserta un bloque en su propia línea (tabla, bloque de código, callout…).
function fmtBlock(text){
  if(!ED){ return; }
  const view=ED.view, sel=view.state.selection.main;
  const lead=(sel.from>0 && view.state.sliceDoc(sel.from-1, sel.from)!=='\n')?'\n':'';
  ED.insert(lead+text);
  onEdit();
}
function fmtCallout(type){
  const titles={info:'Información',tip:'Consejo',success:'Éxito',warning:'Aviso',
    danger:'Peligro',note:'Nota',question:'Pregunta',example:'Ejemplo',
    quote:'Cita',abstract:'Resumen'};
  fmtBlock('> [!'+type+'] '+(titles[type]||'Título')+'\n> Escribe aquí el contenido.\n');
}
// Nota al pie: inserta la referencia [^n] en el cursor y su definición al final del documento.
function fmtFootnote(){
  if(!ED){ return; }
  const view=ED.view, sel=view.state.selection.main, docLen=view.state.doc.length;
  const used=(view.state.doc.toString().match(/\[\^\d+\]:/g)||[]).length;
  const id=used+1, ref='[^'+id+']';
  const tail=(docLen>0?'\n\n':'')+ref+': Escribe aquí la nota al pie.';
  view.dispatch({
    changes:[{from:sel.from, to:sel.to, insert:ref}, {from:docLen, insert:tail}],
    selection:{anchor:sel.from+ref.length}
  });
  view.focus(); onEdit();
}
// Propiedades (frontmatter YAML): solo al principio del documento.
function fmtFrontmatter(){
  if(!ED){ return; }
  const view=ED.view;
  if(/^---\r?\n/.test(view.state.doc.toString())){
    alert('La nota ya empieza con propiedades (frontmatter).'); return;
  }
  const fm='---\ntitulo: Mi nota\ntags: ejemplo\n---\n\n';
  view.dispatch({changes:{from:0, to:0, insert:fm}, selection:{anchor:12, head:19}});
  view.focus(); onEdit();
}
const FMT_ACTIONS={
  h1:()=>fmtLinePrefix('# '),
  h2:()=>fmtLinePrefix('## '),
  h3:()=>fmtLinePrefix('### '),
  h4:()=>fmtLinePrefix('#### '),
  bold:()=>fmtWrap('**','**','texto'),
  italic:()=>fmtWrap('*','*','texto'),
  strike:()=>fmtWrap('~~','~~','texto'),
  code:()=>fmtWrap('`','`','código'),
  highlight:()=>fmtWrap('==','==','resaltado'),
  ul:()=>fmtLinePrefix('- '),
  ol:()=>fmtLinePrefix('1. '),
  task:()=>fmtLinePrefix('- [ ] '),
  quote:()=>fmtLinePrefix('> '),
  codeblock:()=>fmtBlock('```bash\ncódigo aquí\n```\n'),
  table:()=>fmtBlock('| Columna 1 | Columna 2 | Columna 3 |\n|-----------|-----------|-----------|\n| Celda | Celda | Celda |\n| Celda | Celda | Celda |\n'),
  hr:()=>fmtBlock('\n---\n'),
  link:()=>fmtWrap('[','](https://)','texto'),
  image:()=>$('asset-file').click(),
  wikilink:()=>fmtWrap('[[',']]','Nombre de la nota'),
  tag:()=>fmtWrap('#','','etiqueta'),
  mathinline:()=>fmtWrap('$','$','x^2'),
  mathblock:()=>fmtBlock('$$\nf(x) = x^2 + 1\n$$\n'),
  footnote:()=>fmtFootnote(),
  mermaid:()=>fmtBlock('```mermaid\nflowchart TD\n  A[Inicio] --> B{¿Decisión?}\n  B -->|Sí| C[Opción 1]\n  B -->|No| D[Opción 2]\n```\n'),
  comment:()=>fmtWrap('%%','%%','comentario oculto'),
  frontmatter:()=>fmtFrontmatter(),
  calloutfold:()=>fmtBlock('> [!note]- Título plegable\n> Este contenido permanece oculto hasta hacer clic en el título.\n'),
};
(function initFormatBar(){
  const fbar=$('format-bar'), btn=$('btn-format');
  if(!fbar || !btn){ return; }
  btn.addEventListener('click', e=>{ e.stopPropagation();
    fbar.classList.toggle('open'); $('zoom-pop').classList.remove('open'); });
  // Evita que el editor pierda la selección al pulsar un botón de la barra.
  fbar.addEventListener('mousedown', e=>{ if(e.target.closest('button')) e.preventDefault(); });
  fbar.addEventListener('click', e=>{
    const b=e.target.closest('button'); if(!b){ return; }
    e.stopPropagation();
    if(!current){ alert('Abre o crea una nota antes de insertar elementos.'); return; }
    if(b.dataset.fmt && FMT_ACTIONS[b.dataset.fmt]){ FMT_ACTIONS[b.dataset.fmt](); }
    else if(b.dataset.call){ fmtCallout(b.dataset.call); }
    if(b.dataset.fmt!=='image'){ fbar.classList.remove('open'); }
  });
  document.addEventListener('click', e=>{
    if(!e.target.closest('#format-bar') && !e.target.closest('#btn-format'))
      fbar.classList.remove('open');
  });
  document.addEventListener('keydown', e=>{ if(e.key==='Escape') fbar.classList.remove('open'); });
})();

/* ════════════ Export / Import ════════════ */
$('btn-export').addEventListener('click', ()=>{ if(dirty) saveNow(); window.location='/api/notes/export'; });
let importFile=null;
function openImport(){ if(!guardWrite()) return; importFile=null; $('import-fname').style.display='none'; $('import-go').disabled=true;
  $('import-file').value=''; $('import-modal').classList.add('show'); }
function closeImport(){ $('import-modal').classList.remove('show'); }
$('btn-import').addEventListener('click', openImport);
$('import-cancel').addEventListener('click', closeImport);
$('import-drop').addEventListener('click', ()=>$('import-file').click());
$('import-file').addEventListener('change', e=>{ if(e.target.files.length) setImportFile(e.target.files[0]); });
['dragover','dragenter'].forEach(ev=>$('import-drop').addEventListener(ev, e=>{e.preventDefault(); $('import-drop').classList.add('hover');}));
['dragleave','drop'].forEach(ev=>$('import-drop').addEventListener(ev, e=>{e.preventDefault(); $('import-drop').classList.remove('hover');}));
$('import-drop').addEventListener('drop', e=>{ if(e.dataTransfer.files.length) setImportFile(e.dataTransfer.files[0]); });
const MAX_IMPORT_MB=1000;  // tope práctico vía subdominio uploads. (fuera de Cloudflare)
function setImportFile(f){ const ok=/\.(zip|md)$/i.test(f.name);
  if(!ok){ alert('Solo .zip o .md'); return; }
  importFile=f; const mb=f.size/1048576; const el=$('import-fname');
  el.innerHTML='📦 '+esc(f.name)+'  ('+mb.toFixed(1)+' MB)'+
    (mb>MAX_IMPORT_MB?'<br><span style="color:#f59e0b">⚠ Supera '+MAX_IMPORT_MB+' MB; puede que no se suba. Reduce las imágenes o divide la bóveda.</span>':'');
  el.style.display='block'; $('import-go').disabled=false; }
document.querySelectorAll('input[name=impmode]').forEach(r=>r.addEventListener('change', ()=>{
  document.querySelectorAll('#import-modal label').forEach(l=>l.classList.toggle('sel', l.dataset.mode===r.value && r.checked));}));
$('import-go').addEventListener('click', ()=>{
  if(!importFile) return;
  const btn=$('import-go'), bar=$('import-progress'), fill=bar.querySelector('span');
  btn.disabled=true; btn.textContent='Importando…'; bar.classList.add('show'); fill.style.width='0%';
  const fd=new FormData(); fd.append('file', importFile);
  fd.append('mode', document.querySelector('input[name=impmode]:checked').value); fd.append('csrfmiddlewaretoken', CSRF);
  const xhr=new XMLHttpRequest();
  xhr.open('POST', UPLOAD_BASE+'/api/notes/import');
  xhr.withCredentials=true;   // envía la cookie de sesión al subdominio uploads.
  xhr.upload.onprogress=e=>{ if(e.lengthComputable){ const p=Math.round(e.loaded/e.total*100);
    fill.style.width=p+'%'; btn.textContent=(p<100?'Subiendo '+p+'%':'Procesando…'); } };
  const done=()=>{ btn.textContent='Importar'; btn.disabled=false; bar.classList.remove('show'); };
  const tooBig=()=>'El archivo es demasiado grande para subirlo ('+(importFile.size/1048576).toFixed(0)+' MB). '+
    'El límite es ~'+MAX_IMPORT_MB+' MB. Reduce el tamaño de las imágenes de la bóveda o divídela en varias partes.';
  xhr.onload=async ()=>{
    let res={}; try{ res=JSON.parse(xhr.responseText); }catch(e){}
    if(xhr.status===413){ alert(tooBig()); done(); return; }
    if(xhr.status>=400 || res.error){ alert(res.error||('Error al importar ('+xhr.status+')')); done(); return; }
    closeImport(); done(); current=null;
    $('vault-toolbar').style.display='none'; $('vault-body').style.display='none'; $('vault-empty').style.display='flex';
    await loadTree();
    const _ep=$('vault-empty').querySelector('p'); const _eo=_ep.textContent;
    _ep.textContent='✓ Importadas '+(res.imported||0)+' notas · selecciona una para empezar';
    setTimeout(()=>{_ep.textContent=_eo;},5000);
  };
  xhr.onerror=()=>{ alert(importFile.size>MAX_IMPORT_MB*1048576 ? tooBig() : 'Error de red al importar. Revisa tu conexión e inténtalo de nuevo.'); done(); };
  xhr.send(fd);
});
$('empty-new').addEventListener('click', ()=>newNote());
$('empty-import').addEventListener('click', openImport);

/* ════════════ Wiring ════════════ */
// Ctrl/Cmd+S guarda ya (el editor CM gestiona escritura y tabulación).
document.addEventListener('keydown', e=>{ if((e.ctrlKey||e.metaKey)&&e.key==='s' && current){ e.preventDefault(); saveNow(); } });
document.addEventListener('keydown', e=>{
  if(!(e.ctrlKey||e.metaKey)||e.altKey) return;
  if(e.key==='k'){ e.preventDefault(); toggleSearch(true); }
  else if(e.key==='n'&&!e.shiftKey){
    const _t=document.activeElement;
    if(_t&&(_t.tagName==='INPUT'||_t.tagName==='TEXTAREA')) return;
    e.preventDefault(); newNote();
  }
});
// Lightbox: cerrar al pulsar o con Escape.
$('img-lightbox').addEventListener('click', closeLightbox);
// Backdrop click cierra modales secundarios
$('imgdir-modal').addEventListener('click',e=>{if(e.target===$('imgdir-modal'))$('imgdir-modal').classList.remove('show');});
$('storage-modal').addEventListener('click',e=>{if(e.target===$('storage-modal'))$('storage-modal').classList.remove('show');});
document.addEventListener('keydown', e=>{
  if(e.key!=='Escape') return;
  if($('img-lightbox').classList.contains('show')){ closeLightbox(); return; }
  if($('storage-modal').classList.contains('show')){ $('storage-modal').classList.remove('show'); return; }
  if($('imgdir-modal').classList.contains('show')){ $('imgdir-modal').classList.remove('show'); return; }
  if($('share-modal').classList.contains('show')){ closeShareModal(); return; }
  if($('import-modal').classList.contains('show')){ $('import-cancel').click(); return; }
  if(!$('vault-settings-menu').classList.contains('hidden')){ closeVaultSettingsMenu(); $('btn-img-dir').focus(); return; }
});
// Ctrl + / Ctrl - / Ctrl 0 → zoom de la nota (evita el zoom del navegador).
document.addEventListener('keydown', e=>{
  if(!(e.ctrlKey||e.metaKey)) return;
  if(e.key==='+'||e.key==='='){ e.preventDefault(); setNoteFs(noteFs+0.1); }
  else if(e.key==='-'||e.key==='_'){ e.preventDefault(); setNoteFs(noteFs-0.1); }
  else if(e.key==='0'){ e.preventDefault(); setNoteFs(1); }
});
$('btn-new-note').addEventListener('click', ()=>newNote());
$('btn-new-folder').addEventListener('click', ()=>newFolder());
$('btn-search').addEventListener('click', ()=>toggleSearch());
// Dropdown de ajustes de la bóveda
function toggleVaultSettingsMenu(e) {
  e.stopPropagation();
  const menu = $('vault-settings-menu');
  const nowHidden = menu.classList.toggle('hidden');
  $('btn-img-dir').setAttribute('aria-expanded', (!nowHidden).toString());
  if(!nowHidden) setTimeout(()=>menu.querySelector('button')?.focus(), 20);
}
function closeVaultSettingsMenu() {
  const menu = $('vault-settings-menu');
  if (menu) menu.classList.add('hidden');
}
$('btn-img-dir').addEventListener('click', toggleVaultSettingsMenu);
$('vault-settings-menu').addEventListener('keydown', e=>{
  const _vsmBtns=[...$('vault-settings-menu').querySelectorAll('button')];
  const _vi=_vsmBtns.indexOf(document.activeElement);
  if(e.key==='ArrowDown'){e.preventDefault();_vsmBtns[(_vi+1)%_vsmBtns.length]?.focus();}
  if(e.key==='ArrowUp'){e.preventDefault();_vsmBtns[(_vi-1+_vsmBtns.length)%_vsmBtns.length]?.focus();}
  if(e.key==='Escape'){e.preventDefault();closeVaultSettingsMenu();$('btn-img-dir').focus();}
});
$('vsm-imgdir').addEventListener('click', () => { closeVaultSettingsMenu(); openImgDirModal(); });
$('vsm-export').addEventListener('click', () => { closeVaultSettingsMenu(); if(dirty) saveNow(); window.location='/api/notes/export'; });
$('vsm-import').addEventListener('click', () => { closeVaultSettingsMenu(); openImport(); });
$('vsm-storage').addEventListener('click', () => { closeVaultSettingsMenu(); openStorageModal(); });

/* ════════════ Modal de Almacenamiento ════════════ */
function fmtBytes(n) {
  n = +n || 0;
  const u = ['B','KB','MB','GB','TB'];
  let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return n.toFixed(n < 10 && i > 0 ? 1 : 0) + ' ' + u[i];
}
async function openStorageModal() {
  $('storage-modal').classList.add('show');
  $('storage-body').style.display = 'none';
  $('storage-err').style.display = 'none';
  $('storage-loading').style.display = '';
  $('storage-progress').style.display = 'none';
  $('storage-result').style.display = 'none';
  try {
    const r = await fetch('/api/notes/storage').then(x => x.json());
    if (!r.success) throw new Error(r.error || 'Error');
    $('storage-loading').style.display = 'none';
    $('storage-body').style.display = '';
    renderStorageStats(r);
  } catch (e) {
    $('storage-loading').style.display = 'none';
    $('storage-err').textContent = e.message || 'No se pudo calcular el almacenamiento';
    $('storage-err').style.display = '';
  }
}
function renderStorageStats(s) {
  $('storage-total').textContent = fmtBytes(s.total_bytes);
  const tot = Math.max(1, s.total_bytes);
  // Barra apilada (segments)
  const segs = [
    {bytes: s.notes_bytes,  color: 'var(--storage-c-notes)'},
    {bytes: s.images_bytes, color: 'var(--storage-c-images)'},
    {bytes: s.other_bytes,  color: 'var(--storage-c-other)'},
  ];
  $('storage-stack').innerHTML = segs
    .map(seg => `<span style="width:${((seg.bytes/tot)*100).toFixed(2)}%;background:${seg.color}"></span>`)
    .join('');

  // Cards
  $('storage-notes-bytes').textContent  = fmtBytes(s.notes_bytes);
  $('storage-images-bytes').textContent = fmtBytes(s.images_bytes);
  $('storage-other-bytes').textContent  = fmtBytes(s.other_bytes);
  const f = (n, label) => `${n} ${label}${n === 1 ? '' : 's'}`;
  $('storage-notes-n').textContent  = f(s.n_notes,  'archivo');
  $('storage-images-n').textContent = f(s.n_images, 'archivo');
  $('storage-other-n').textContent  = f(s.n_other,  'archivo');

  const total = s.n_notes + s.n_images + s.n_other;
  $('storage-files').textContent   = f(total, 'archivo');
  $('storage-folders').textContent = `${s.n_folders} carpeta${s.n_folders===1?'':'s'}`;
}
$('storage-cancel').addEventListener('click', () => $('storage-modal').classList.remove('show'));

/* ── Optimizar imágenes (backup opcional + recode WebP + rewrite refs) ──── */
$('btn-optimize-images').addEventListener('click', async () => {
  const btn = $('btn-optimize-images');
  const wantsBackup = $('opt-backup-first').checked;
  const prev = btn.innerHTML;

  // 1) Confirmación
  const _confirmed = await confirmAsync(
    wantsBackup ? 'Optimizar imágenes' : '⚠ Sin backup previo',
    wantsBackup
      ? '¿Lanzar? Se descargará primero un backup ZIP y se recodificarán las imágenes ráster a WebP. Reversible importando el backup.'
      : 'Vas a optimizar SIN backup previo. Se recodificarán las imágenes a WebP. Esta acción NO es reversible automáticamente.',
    'Sí, optimizar'
  );
  if (!_confirmed) return;

  btn.disabled = true;
  $('storage-progress').style.display = '';
  $('storage-result').style.display = 'none';
  $('storage-err').style.display = 'none';

  // 2) Backup opcional
  if (wantsBackup) {
    btn.textContent = 'Descargando backup…';
    $('storage-progress-msg').textContent = 'Generando backup ZIP de toda la bóveda…';
    try {
      const r = await fetch('/api/notes/export');
      if (!r.ok) throw new Error('No se pudo generar el backup');
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `boveda-backup-${new Date().toISOString().slice(0, 10)}.zip`;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      $('storage-progress').style.display = 'none';
      alert('Error generando backup: ' + e.message + '\n\nNo se ha optimizado nada.');
      btn.disabled = false; btn.innerHTML = prev;
      return;
    }
  }

  // 3) Ejecutar bulk en streaming NDJSON con progreso real
  btn.textContent = 'Optimizando…';
  $('storage-progress-msg').textContent = 'Preparando…';
  // Pasar la barra a modo determinado
  const bar = document.querySelector('.storage-progress-bar-fill');
  bar.style.animation = 'none';
  bar.style.width = '0%';
  bar.style.left = '0';
  bar.style.transition = 'width .2s ease';

  let summary = null;
  try {
    const r = await fetch('/api/notes/optimize-images', { method: 'POST' });
    if (!r.ok || !r.body) throw new Error('HTTP ' + r.status);
    const reader = r.body.getReader();
    const dec = new TextDecoder();
    let buf = '';
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let nl;
      while ((nl = buf.indexOf('\n')) >= 0) {
        const line = buf.slice(0, nl).trim();
        buf = buf.slice(nl + 1);
        if (!line) continue;
        let upd;
        try { upd = JSON.parse(line); } catch (_) { continue; }
        handleOptimizeEvent(upd);
        if (upd.phase === 'done')  summary = upd;
        if (upd.phase === 'error') throw new Error(upd.error || 'Error');
      }
    }
    $('storage-progress').style.display = 'none';
    if (summary) {
      const out = $('storage-result');
      out.style.display = '';
      out.textContent = `${summary.converted} imágenes optimizadas, ${summary.skipped} omitidas. Ahorrado: ${fmtBytes(summary.saved_bytes)}.`;
    }
    // Refrescar stats y árbol
    const s = await fetch('/api/notes/storage').then(x => x.json());
    if (s.success) renderStorageStats(s);
    await loadTree();
    if (current) {
      const candidate = current.path.replace(/\.(jpe?g|png|bmp|tiff?|heic|avif)$/i, '.webp');
      if (candidate !== current.path) openNote(candidate);
    }
  } catch (e) {
    $('storage-progress').style.display = 'none';
    const err = $('storage-err');
    err.textContent = 'Error: ' + e.message;
    err.style.display = '';
  } finally {
    // Restaurar la barra al modo indeterminado para futuras ejecuciones.
    bar.style.transition = '';
    bar.style.width = '35%';
    bar.style.animation = '';
    btn.disabled = false;
    btn.innerHTML = prev;
  }

  function handleOptimizeEvent(u) {
    const msg = $('storage-progress-msg');
    const fill = document.querySelector('.storage-progress-bar-fill');
    switch (u.phase) {
      case 'scan':
        msg.textContent = 'Escaneando bóveda…';
        break;
      case 'start':
        msg.textContent = u.total === 0
          ? 'No hay imágenes ráster que optimizar.'
          : `0 / ${u.total} imágenes`;
        fill.style.width = u.total === 0 ? '100%' : '0%';
        break;
      case 'progress': {
        const pct = u.total ? (u.i / u.total) * 100 : 0;
        fill.style.width = pct.toFixed(1) + '%';
        msg.textContent =
          `${u.i} / ${u.total} · convertidas ${u.converted} · ahorrado ${fmtBytes(u.saved_bytes)}`;
        break;
      }
      case 'rewriting':
        msg.textContent = `Actualizando referencias en ${u.notes} notas…`;
        fill.style.width = '100%';
        break;
      case 'done':
        msg.textContent = `Listo: ${u.converted} convertidas, ${u.skipped} omitidas, ${fmtBytes(u.saved_bytes)} ahorrados.`;
        fill.style.width = '100%';
        break;
    }
  }
});
document.addEventListener('click', e => {
  if (!$('vault-settings-wrap').contains(e.target)) closeVaultSettingsMenu();
});
$('imgdir-cancel').addEventListener('click', ()=>$('imgdir-modal').classList.remove('show'));
$('btn-collapse-all').addEventListener('click', collapseAll);
$('btn-expand-all').addEventListener('click', expandAll);
$('vault-search-input').addEventListener('input', ()=>{ clearTimeout(searchTimer); searchTimer=setTimeout(renderTree, 140); syncSearchClear(); });
$('vault-search-input').addEventListener('keydown', e=>{ if(e.key==='Escape') toggleSearch(false); });
$('vault-search-clear').addEventListener('click', ()=>{ const inp=$('vault-search-input'); inp.value=''; syncSearchClear(); inp.focus(); renderTree(); });
// Soltar en el hueco vacío bajo el último elemento (o en una bóveda vacía) → mueve a la raíz.
$('vault-tree').addEventListener('dragover', e=>{
  if(!dragSrc || e.target!==$('vault-tree')) return;
  e.preventDefault(); e.dataTransfer.dropEffect='move';
  setDropVisual($('vault-tree'), 'into');
});
$('vault-tree').addEventListener('drop', e=>{
  if(!dragSrc || e.target!==$('vault-tree')) return;
  e.preventDefault();
  const src=dragSrc; dragSrc=null; clearDropVisual();
  dropItem(src, '', null, null);
});
// Si el puntero abandona toda la barra lateral durante el arrastre, quita cualquier resaltado.
$('vault-side').addEventListener('dragleave', e=>{
  if(dragSrc && !$('vault-side').contains(e.relatedTarget)) clearDropVisual();
});
$('btn-toggle-sidebar').addEventListener('click', ()=>{
  const hidden=$('vault').classList.toggle('side-hidden');
  $('btn-toggle-sidebar').setAttribute('aria-expanded',(!hidden).toString());
  if(window.innerWidth>=760) localStorage.setItem('vault-side-hidden',hidden?'1':'0');
});
window.addEventListener('beforeunload', ()=>{ if(dirty) saveNow(); });
document.addEventListener('visibilitychange', ()=>{ if(document.hidden&&dirty) saveNow(); });
function flashSync(){ const d=$('sync-dot'); d.classList.add('visible'); setTimeout(()=>d.classList.remove('visible'),700); }

if(localStorage.getItem('vault-side-hidden')==='1'&&window.innerWidth>=760){
  $('vault').classList.add('side-hidden');
  $('btn-toggle-sidebar').setAttribute('aria-expanded','false');
}
initEditor();
$('vault-title').addEventListener('click',e=>{
  // Clic en el nombre de la NOTA (último elemento): ir al inicio del contenido (panel derecho).
  if(e.target.closest('.crumb-note')){
    if(ED){ try{ED.view.scrollDOM.scrollTo({top:0,behavior:'smooth'});}catch(_){ED.view.scrollDOM.scrollTop=0;} try{ED.view.focus();}catch(_){} }
    return;
  }
  // Clic en una CARPETA: expandirla, hacer scroll hasta ella en el árbol (panel izquierdo) y resaltarla.
  const link=e.target.closest('.crumb-link');if(!link)return;const fp=link.dataset.path;if(!fp)return;
  fp.split('/').forEach((_,i,a)=>expanded.add(a.slice(0,i+1).join('/')));persistExpanded();renderTree();
  if(window.innerWidth<760)$('vault').classList.remove('side-hidden');
  setTimeout(()=>{const row=document.querySelector('.tree-row[data-path="'+cssEsc(fp)+'"]');if(!row)return;row.scrollIntoView({behavior:'smooth',block:'center'});row.classList.remove('flash-locate');void row.offsetWidth;row.classList.add('flash-locate');},60);
});
(async ()=>{
  await loadTree(); await restoreTabsState();
  // Deep-link desde fuera del vault (p.ej. "Abrir esta nota" en el modal de
  // Ajustes de otra página): /?open=<ruta> abre la nota y limpia la URL.
  const openParam=new URLSearchParams(location.search).get('open');
  if(openParam){
    await openInNewTab(openParam);
    history.replaceState(null, '', location.pathname);
  }
})();

// Rastreador de eventos de puntero: usado por el aislador de foco del editor
// para distinguir "el usuario clicó fuera" (permitido) de "el teclado movió el foco" (revertir).
let lastPointerAt = 0;
['mousedown','touchstart','pointerdown'].forEach(ev =>
  document.addEventListener(ev, ()=>{ lastPointerAt = performance.now(); }, true));

// Trap global de Backspace/Delete: evita la navegación atrás del navegador cuando el foco
// no está en ningún elemento editable. Con CM6 enfocado (isContentEditable=true) no se llama
// preventDefault para no bloquear el evento beforeinput del que depende el borrado de texto.
document.addEventListener('keydown', function(e) {
  if (e.key !== 'Backspace' && e.key !== 'Delete') return;
  if (e.ctrlKey || e.metaKey) return; // Ctrl+Backspace = borrar palabra (válido en editor)
  const t = document.activeElement;
  const inEditable = t && (t.isContentEditable || t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT');
  if (!inEditable) {
    e.preventDefault();
    e.stopPropagation(); // doble seguro frente a navegadores que aplican el back antes del default
    if (ED && current) { try { ED.view.focus(); } catch(_) {} }
  }
}, true);

// Typing sink: si el usuario pulsa una tecla de escritura con el foco fuera del editor
// (p.ej. tras hacer clic en el árbol de notas), redirigir el foco al editor al instante.
// El beforeinput se disparará sobre el editor y CodeMirror lo procesará con normalidad.
document.addEventListener('keydown', function(e) {
  if (!ED || !current) return;
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  if (e.key.length !== 1) return; // solo caracteres imprimibles (letras, números, símbolos)
  const t = document.activeElement;
  if (!t || t.isContentEditable) return; // ya está en el editor
  if (['INPUT','TEXTAREA','SELECT'].includes(t.tagName)) return; // campo legítimo
  if (t.closest('.modal-back, #ctx-menu')) return;
  if (!t.closest('#vault')) return; // fuera de la app
  // Redirigir foco: el beforeinput se disparará sobre el editor
  try { ED.view.focus(); } catch(_) {}
}, true);

// Fix: clicking in bottom padding → cursor to end (always an empty line due to trailing-\n)
(function() {
  if (!ED || !ED.view) return;
  ED.view.scrollDOM.addEventListener('mousedown', function(e) {
    if (e.button !== 0) return;
    if (e.target.closest('a, img, button, input, select, .cm-content')) return;
    if (e.target !== ED.view.scrollDOM) return;
    e.preventDefault();
    ED.view.dispatch({ selection: { anchor: ED.view.state.doc.length }, scrollIntoView: false });
    ED.view.focus();
  });
})();

if (window.visualViewport) {
  window.visualViewport.addEventListener('resize', function() {
    if (!ED || !ED.view) return;
    setTimeout(function() {
      try {
        ED.view.dispatch({ selection: ED.view.state.selection, scrollIntoView: true });
      } catch(e) {}
    }, 80);
  });
}
