/* Pizarra: lienzo de dibujo propio (rectángulos, elipses, líneas, flechas,
 * lápiz, texto, imágenes e iconos) sobre <canvas>. Sin librerías de terceros:
 * un motor de dibujo simple a mano, en el mismo estilo que notes.js. */
(function () {
  const BOOT = window.PIZARRA_BOOT || {};
  const CAN_WRITE = !!BOOT.canWrite;

  const wrap = document.getElementById('pz-canvas-wrap');
  const canvas = document.getElementById('pz-canvas');
  const ctx = canvas.getContext('2d');
  const statusEl = document.getElementById('pz-save-status');
  const zoomLabel = document.getElementById('pz-zoom-level');
  const fileInput = document.getElementById('pz-file-input');
  const iconMenu = document.getElementById('pz-icon-menu');

  const HANDLE_R = 5;
  const HIT_PAD = 6;

  /* ════════════ Iconos (trazos propios, sin dependencias externas) ════════════ */
  const ICONS = {
    star: 'M12 2.5l2.9 6.2 6.8.7-5.1 4.7 1.5 6.7L12 17.4l-6.1 3.4 1.5-6.7-5.1-4.7 6.8-.7z',
    heart: 'M12 21S3 14.5 3 8.8C3 5.6 5.5 3.5 8.2 3.5c1.7 0 3.3.9 3.8 2.3.5-1.4 2.1-2.3 3.8-2.3C18.5 3.5 21 5.6 21 8.8 21 14.5 12 21 12 21z',
    check: 'M4 12.5l5 5L20 6.5',
    cross: 'M5 5l14 14M19 5L5 19',
    flag: 'M5 21V3.8c2.3-1.2 4.6-1.2 7 0 2.4 1.2 4.6 1.2 7 0v9.4c-2.4 1.2-4.6 1.2-7 0-2.4-1.2-4.7-1.2-7 0z',
    bulb: 'M9 18h6M10 21h4M12 3a6 6 0 0 0-3.5 10.9c.6.4.9 1 .9 1.6v.5h5.2v-.5c0-.6.3-1.2.9-1.6A6 6 0 0 0 12 3z',
    cloud: 'M7 18a4.5 4.5 0 0 1-.4-9 5.5 5.5 0 0 1 10.6-1.7A4 4 0 0 1 17 18H7z',
    sun: 'M12 6.5a5.5 5.5 0 1 0 0 11 5.5 5.5 0 0 0 0-11zM12 1v2.3M12 20.7V23M4.2 4.2l1.6 1.6M18.2 18.2l1.6 1.6M1 12h2.3M20.7 12H23M4.2 19.8l1.6-1.6M18.2 5.8l1.6-1.6',
    home: 'M4 11.5 12 4l8 7.5V20a1 1 0 0 1-1 1h-4v-6H9v6H5a1 1 0 0 1-1-1z',
    person: 'M12 12a4.2 4.2 0 1 0 0-8.4 4.2 4.2 0 0 0 0 8.4zM4 21c.7-4 3.8-6.5 8-6.5s7.3 2.5 8 6.5',
    chat: 'M4 4.5h16v11H9.5L5 19.5v-4H4z',
    bolt: 'M13 2 4 14h6l-1 8 9-12h-6z',
  };

  /* ════════════ Fondo del lienzo ════════════ */
  const BG_PRESETS = [
    { name: 'Oscuro', value: '#15181f' },
    { name: 'Gris', value: '#2b2d31' },
    { name: 'Claro', value: '#ffffff' },
    { name: 'Crema', value: '#fdf6e3' },
    { name: 'Amarillo', value: '#fff3bf' },
    { name: 'Rosa', value: '#ffe3ec' },
    { name: 'Azul', value: '#dbe9ff' },
    { name: 'Verde', value: '#dcf5e0' },
  ];

  function buildBgMenu() {
    const bgMenu = document.getElementById('pz-bg-menu');
    const swatches = document.createElement('div');
    swatches.className = 'pz-bg-swatches';
    BG_PRESETS.forEach((preset) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'pz-bg-swatch';
      b.title = preset.name;
      b.style.background = preset.value;
      b.dataset.value = preset.value;
      b.addEventListener('click', () => setBgColor(preset.value));
      swatches.appendChild(b);
    });
    bgMenu.appendChild(swatches);

    const custom = document.createElement('div');
    custom.className = 'pz-bg-custom';
    custom.innerHTML = '<label for="pz-bg-custom-input">Personalizado</label>';
    const input = document.createElement('input');
    input.type = 'color'; input.id = 'pz-bg-custom-input'; input.value = bgColor;
    input.addEventListener('input', (e) => setBgColor(e.target.value));
    custom.appendChild(input);
    bgMenu.appendChild(custom);
  }

  function syncBgUi(value) {
    document.querySelectorAll('.pz-bg-swatch').forEach((b) => b.classList.toggle('active', b.dataset.value === value));
    const customInput = document.getElementById('pz-bg-custom-input');
    if (customInput) customInput.value = value;
  }

  function setBgColor(value) {
    bgColor = value;
    syncBgUi(value);
    render();
    scheduleSave();
  }

  function buildIconMenu() {
    Object.keys(ICONS).forEach((name) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'pz-icon-item';
      b.title = name;
      b.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="${ICONS[name]}"/></svg>`;
      b.addEventListener('click', () => {
        pendingIcon = name;
        setTool('icon');
        iconMenu.classList.add('hidden');
      });
      iconMenu.appendChild(b);
    });
  }

  /* ════════════ Estado ════════════ */
  let elements = (BOOT.scene && BOOT.scene.elements) || [];
  let selectedId = null;
  let tool = 'select';
  let pendingIcon = null;
  let color = '#e9edf5';
  let strokeWidth = 3;

  const savedAppState = (BOOT.scene && BOOT.scene.appState) || {};
  let zoom = savedAppState.zoom || 1;
  let offsetX = savedAppState.offsetX || 0;
  let offsetY = savedAppState.offsetY || 0;
  let bgColor = savedAppState.bgColor || '#15181f';
  let clipboardEl = null;
  let lastCtxWorldPos = null;

  let undoStack = [];
  let redoStack = [];
  let nextId = 1;
  const genId = () => 'el' + (nextId++) + '_' + Math.random().toString(36).slice(2, 7);

  function snapshot() {
    undoStack.push(JSON.stringify(elements));
    if (undoStack.length > 100) undoStack.shift();
    redoStack = [];
    updateUndoRedoButtons();
  }

  function updateUndoRedoButtons() {
    document.getElementById('pz-undo').disabled = undoStack.length === 0;
    document.getElementById('pz-redo').disabled = redoStack.length === 0;
  }

  /* ════════════ Transformación pantalla ⇄ mundo ════════════ */
  function screenToWorld(sx, sy) {
    return { x: (sx - offsetX) / zoom, y: (sy - offsetY) / zoom };
  }

  function resizeCanvas() {
    const dpr = window.devicePixelRatio || 1;
    const rect = wrap.getBoundingClientRect();
    canvas.width = Math.round(rect.width * dpr);
    canvas.height = Math.round(rect.height * dpr);
    canvas.style.width = rect.width + 'px';
    canvas.style.height = rect.height + 'px';
    render();
  }

  /* ════════════ Dibujo de elementos ════════════ */
  function measureText(el) {
    ctx.font = `${el.fontSize || 20}px "Assistant", sans-serif`;
    const lines = (el.text || '').split('\n');
    const w = Math.max(20, ...lines.map((l) => ctx.measureText(l).width));
    const h = Math.max(24, lines.length * (el.fontSize || 20) * 1.3);
    return { w, h };
  }

  function bbox(el) {
    switch (el.type) {
      case 'rect': case 'ellipse': case 'image': case 'icon':
        return { x: Math.min(el.x, el.x + el.w), y: Math.min(el.y, el.y + el.h), w: Math.abs(el.w), h: Math.abs(el.h) };
      case 'line': case 'arrow':
        return { x: Math.min(el.x1, el.x2), y: Math.min(el.y1, el.y2), w: Math.abs(el.x2 - el.x1), h: Math.abs(el.y2 - el.y1) };
      case 'pencil': {
        const xs = el.points.map((p) => p[0]), ys = el.points.map((p) => p[1]);
        return { x: Math.min(...xs), y: Math.min(...ys), w: Math.max(...xs) - Math.min(...xs), h: Math.max(...ys) - Math.min(...ys) };
      }
      case 'text': {
        const { w, h } = measureText(el);
        return { x: el.x, y: el.y, w, h };
      }
      default: return { x: 0, y: 0, w: 0, h: 0 };
    }
  }

  function drawArrowHead(x1, y1, x2, y2, size) {
    const angle = Math.atan2(y2 - y1, x2 - x1);
    ctx.beginPath();
    ctx.moveTo(x2, y2);
    ctx.lineTo(x2 - size * Math.cos(angle - Math.PI / 7), y2 - size * Math.sin(angle - Math.PI / 7));
    ctx.moveTo(x2, y2);
    ctx.lineTo(x2 - size * Math.cos(angle + Math.PI / 7), y2 - size * Math.sin(angle + Math.PI / 7));
    ctx.stroke();
  }

  const imgCache = new Map();
  function getImage(src) {
    if (imgCache.has(src)) return imgCache.get(src);
    const img = new Image();
    img.src = src;
    img.onload = render;
    imgCache.set(src, img);
    return img;
  }

  function drawElement(el) {
    ctx.save();
    ctx.strokeStyle = el.color || '#e9edf5';
    ctx.fillStyle = el.color || '#e9edf5';
    // El grosor vive en coordenadas del mundo (como el propio elemento): al
    // hacer zoom, el trazo escala con el dibujo — no se queda fino a propósito.
    ctx.lineWidth = el.strokeWidth || 2;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    switch (el.type) {
      case 'rect':
        ctx.strokeRect(el.x, el.y, el.w, el.h);
        break;
      case 'ellipse':
        ctx.beginPath();
        ctx.ellipse(el.x + el.w / 2, el.y + el.h / 2, Math.abs(el.w) / 2, Math.abs(el.h) / 2, 0, 0, Math.PI * 2);
        ctx.stroke();
        break;
      case 'line':
        ctx.beginPath();
        ctx.moveTo(el.x1, el.y1);
        ctx.lineTo(el.x2, el.y2);
        ctx.stroke();
        break;
      case 'arrow':
        ctx.beginPath();
        ctx.moveTo(el.x1, el.y1);
        ctx.lineTo(el.x2, el.y2);
        ctx.stroke();
        drawArrowHead(el.x1, el.y1, el.x2, el.y2, Math.max(10, (el.strokeWidth || 2) * 3));
        break;
      case 'pencil':
        if (el.points.length > 1) {
          ctx.beginPath();
          ctx.moveTo(el.points[0][0], el.points[0][1]);
          for (let i = 1; i < el.points.length; i++) ctx.lineTo(el.points[i][0], el.points[i][1]);
          ctx.stroke();
        }
        break;
      case 'text': {
        ctx.font = `${el.fontSize || 20}px "Assistant", sans-serif`;
        ctx.textBaseline = 'top';
        (el.text || '').split('\n').forEach((line, i) => {
          ctx.fillText(line, el.x, el.y + i * (el.fontSize || 20) * 1.3);
        });
        break;
      }
      case 'image': {
        const img = getImage(el.src);
        if (img.complete && img.naturalWidth) ctx.drawImage(img, el.x, el.y, el.w, el.h);
        break;
      }
      case 'icon': {
        const p = new Path2D(ICONS[el.name] || '');
        ctx.save();
        ctx.translate(el.x, el.y);
        ctx.scale(el.w / 24, el.h / 24);
        // El grosor se fija en el espacio local del icono (viewBox 24): al
        // escalar junto con el path, mantiene las proporciones del preview
        // del menú sea cual sea el tamaño final o el zoom del lienzo.
        ctx.lineWidth = 1.8;
        ctx.stroke(p);
        ctx.restore();
        break;
      }
    }
    ctx.restore();
  }

  function drawSelection(el) {
    const b = bbox(el);
    ctx.save();
    ctx.strokeStyle = '#22d3ee';
    ctx.lineWidth = 1 / zoom;
    ctx.setLineDash([4 / zoom, 3 / zoom]);
    ctx.strokeRect(b.x - 4 / zoom, b.y - 4 / zoom, b.w + 8 / zoom, b.h + 8 / zoom);
    ctx.setLineDash([]);
    if (CAN_WRITE && el.type !== 'pencil' && el.type !== 'text') {
      ctx.fillStyle = '#22d3ee';
      handlesFor(el).forEach((h) => {
        ctx.beginPath();
        ctx.arc(h.x, h.y, HANDLE_R / zoom, 0, Math.PI * 2);
        ctx.fill();
      });
    }
    ctx.restore();
  }

  function handlesFor(el) {
    if (el.type === 'line' || el.type === 'arrow') {
      return [{ pos: 'p1', x: el.x1, y: el.y1 }, { pos: 'p2', x: el.x2, y: el.y2 }];
    }
    const b = bbox(el);
    return [
      { pos: 'nw', x: b.x, y: b.y }, { pos: 'ne', x: b.x + b.w, y: b.y },
      { pos: 'sw', x: b.x, y: b.y + b.h }, { pos: 'se', x: b.x + b.w, y: b.y + b.h },
    ];
  }

  function isLightColor(hex) {
    const c = (hex || '').replace('#', '');
    if (c.length !== 6) return false;
    const r = parseInt(c.slice(0, 2), 16), g = parseInt(c.slice(2, 4), 16), b = parseInt(c.slice(4, 6), 16);
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255 > 0.6;
  }

  function render() {
    const dpr = window.devicePixelRatio || 1;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, canvas.width / dpr, canvas.height / dpr);
    ctx.fillStyle = bgColor;
    ctx.fillRect(0, 0, canvas.width / dpr, canvas.height / dpr);

    ctx.save();
    ctx.translate(offsetX, offsetY);
    ctx.scale(zoom, zoom);

    // Puntos de fondo (referencia visual del lienzo infinito). El contraste
    // se adapta al fondo elegido para que sigan visibles sobre uno claro.
    const rect = wrap.getBoundingClientRect();
    const step = 32;
    const tl = screenToWorld(0, 0), br = screenToWorld(rect.width, rect.height);
    ctx.fillStyle = isLightColor(bgColor) ? 'rgba(0,0,0,.08)' : 'rgba(255,255,255,.06)';
    const startX = Math.floor(tl.x / step) * step, startY = Math.floor(tl.y / step) * step;
    for (let x = startX; x < br.x; x += step) {
      for (let y = startY; y < br.y; y += step) {
        ctx.beginPath();
        ctx.arc(x, y, 1 / zoom, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    elements.forEach(drawElement);
    if (draftElement) drawElement(draftElement);
    const sel = elements.find((e) => e.id === selectedId);
    if (sel) drawSelection(sel);
    ctx.restore();
  }

  /* ════════════ Hit-testing ════════════ */
  function distToSegment(px, py, x1, y1, x2, y2) {
    const dx = x2 - x1, dy = y2 - y1;
    const len2 = dx * dx + dy * dy;
    let t = len2 ? ((px - x1) * dx + (py - y1) * dy) / len2 : 0;
    t = Math.max(0, Math.min(1, t));
    const cx = x1 + t * dx, cy = y1 + t * dy;
    return Math.hypot(px - cx, py - cy);
  }

  function hitElement(wx, wy) {
    const pad = HIT_PAD / zoom;
    for (let i = elements.length - 1; i >= 0; i--) {
      const el = elements[i];
      if (el.type === 'line' || el.type === 'arrow') {
        if (distToSegment(wx, wy, el.x1, el.y1, el.x2, el.y2) <= pad) return el;
      } else if (el.type === 'pencil') {
        for (let j = 0; j < el.points.length - 1; j++) {
          const [x1, y1] = el.points[j], [x2, y2] = el.points[j + 1];
          if (distToSegment(wx, wy, x1, y1, x2, y2) <= pad) return el;
        }
      } else if (el.type === 'ellipse') {
        const rx = Math.abs(el.w) / 2, ry = Math.abs(el.h) / 2;
        const cx = el.x + el.w / 2, cy = el.y + el.h / 2;
        if (rx > 0 && ry > 0) {
          const nx = (wx - cx) / rx, ny = (wy - cy) / ry;
          if (nx * nx + ny * ny <= 1.15) return el;
        }
      } else {
        const b = bbox(el);
        if (wx >= b.x - pad && wx <= b.x + b.w + pad && wy >= b.y - pad && wy <= b.y + b.h + pad) return el;
      }
    }
    return null;
  }

  function handleAt(wx, wy) {
    const sel = elements.find((e) => e.id === selectedId);
    if (!sel || !CAN_WRITE || sel.type === 'pencil' || sel.type === 'text') return null;
    const pad = (HANDLE_R + 3) / zoom;
    return handlesFor(sel).find((h) => Math.hypot(wx - h.x, wy - h.y) <= pad) || null;
  }

  /* ════════════ Herramientas ════════════ */
  function setTool(t) {
    tool = t;
    document.querySelectorAll('.pz-tool[data-tool]').forEach((b) => b.classList.toggle('active', b.dataset.tool === t));
    wrap.classList.toggle('tool-select', t === 'select');
    wrap.classList.toggle('tool-pan', t === 'pan');
    if (t !== 'icon') pendingIcon = null;
  }

  function selectElement(id) {
    selectedId = id;
    const del = document.getElementById('pz-delete');
    del.disabled = !CAN_WRITE || !id;
    if (id) {
      const el = elements.find((e) => e.id === id);
      if (el) {
        document.getElementById('pz-color').value = el.color || color;
        if (el.strokeWidth) document.getElementById('pz-stroke').value = String(el.strokeWidth);
      }
    }
    render();
  }

  let draftElement = null;
  let dragMode = null; // 'draw' | 'move' | 'resize' | 'pan' | 'pencil'
  let dragHandle = null;
  let dragStartWorld = null;
  let dragOrig = null;
  let panStart = null;
  let spaceHeld = false;

  function pointerDown(e) {
    if (e.button === 2) return;
    const rect = wrap.getBoundingClientRect();
    const sx = e.clientX - rect.left, sy = e.clientY - rect.top;
    const w = screenToWorld(sx, sy);

    if (e.button === 1 || tool === 'pan' || spaceHeld) {
      dragMode = 'pan';
      panStart = { sx, sy, offsetX, offsetY };
      wrap.classList.add('panning');
      canvas.setPointerCapture(e.pointerId);
      return;
    }
    if (!CAN_WRITE) return;

    if (tool === 'select') {
      const h = handleAt(w.x, w.y);
      if (h) {
        dragMode = 'resize'; dragHandle = h.pos; dragStartWorld = w;
        dragOrig = JSON.parse(JSON.stringify(elements.find((el) => el.id === selectedId)));
        snapshot();
        canvas.setPointerCapture(e.pointerId);
        return;
      }
      const hit = hitElement(w.x, w.y);
      if (hit) {
        selectElement(hit.id);
        dragMode = 'move'; dragStartWorld = w;
        dragOrig = JSON.parse(JSON.stringify(hit));
        snapshot();
      } else {
        selectElement(null);
      }
      canvas.setPointerCapture(e.pointerId);
      return;
    }

    if (tool === 'text') {
      startTextInput(w);
      return;
    }

    if (tool === 'image') {
      pendingImagePos = w;
      fileInput.click();
      return;
    }

    if (tool === 'icon') {
      const name = pendingIcon || Object.keys(ICONS)[0];
      const size = 48;
      const el = { id: genId(), type: 'icon', name, x: w.x - size / 2, y: w.y - size / 2, w: size, h: size, color };
      snapshot();
      elements.push(el);
      selectElement(el.id);
      setTool('select');
      scheduleSave();
      render();
      return;
    }

    // Herramientas de dibujo: rect, ellipse, line, arrow, pencil
    dragMode = 'draw';
    dragStartWorld = w;
    if (tool === 'pencil') {
      draftElement = { id: genId(), type: 'pencil', points: [[w.x, w.y]], color, strokeWidth };
    } else if (tool === 'line' || tool === 'arrow') {
      draftElement = { id: genId(), type: tool, x1: w.x, y1: w.y, x2: w.x, y2: w.y, color, strokeWidth };
    } else {
      draftElement = { id: genId(), type: tool, x: w.x, y: w.y, w: 0, h: 0, color, strokeWidth };
    }
    canvas.setPointerCapture(e.pointerId);
  }

  function pointerMove(e) {
    const rect = wrap.getBoundingClientRect();
    const sx = e.clientX - rect.left, sy = e.clientY - rect.top;
    const w = screenToWorld(sx, sy);

    if (dragMode === 'pan') {
      offsetX = panStart.offsetX + (sx - panStart.sx);
      offsetY = panStart.offsetY + (sy - panStart.sy);
      render();
      return;
    }
    if (dragMode === 'draw' && draftElement) {
      if (draftElement.type === 'pencil') {
        draftElement.points.push([w.x, w.y]);
      } else if (draftElement.type === 'line' || draftElement.type === 'arrow') {
        draftElement.x2 = w.x; draftElement.y2 = w.y;
      } else {
        draftElement.w = w.x - draftElement.x;
        draftElement.h = w.y - draftElement.y;
      }
      render();
      return;
    }
    if (dragMode === 'move' && dragOrig) {
      const dx = w.x - dragStartWorld.x, dy = w.y - dragStartWorld.y;
      const el = elements.find((e2) => e2.id === selectedId);
      applyMove(el, dragOrig, dx, dy);
      render();
      return;
    }
    if (dragMode === 'resize' && dragOrig) {
      const el = elements.find((e2) => e2.id === selectedId);
      applyResize(el, dragOrig, dragHandle, w);
      render();
      return;
    }
  }

  function applyMove(el, orig, dx, dy) {
    if (!el) return;
    switch (el.type) {
      case 'line': case 'arrow':
        el.x1 = orig.x1 + dx; el.y1 = orig.y1 + dy; el.x2 = orig.x2 + dx; el.y2 = orig.y2 + dy;
        break;
      case 'pencil':
        el.points = orig.points.map((p) => [p[0] + dx, p[1] + dy]);
        break;
      default:
        el.x = orig.x + dx; el.y = orig.y + dy;
    }
  }

  function applyResize(el, orig, handle, w) {
    if (!el) return;
    if (el.type === 'line' || el.type === 'arrow') {
      if (handle === 'p1') { el.x1 = w.x; el.y1 = w.y; } else { el.x2 = w.x; el.y2 = w.y; }
      return;
    }
    const ob = { x: orig.x, y: orig.y, w: orig.w, h: orig.h };
    let x = ob.x, y = ob.y, w2 = ob.w, h2 = ob.h;
    if (handle.includes('w')) { w2 = ob.x + ob.w - w.x; x = w.x; }
    if (handle.includes('e')) { w2 = w.x - ob.x; }
    if (handle.includes('n')) { h2 = ob.y + ob.h - w.y; y = w.y; }
    if (handle.includes('s')) { h2 = w.y - ob.y; }
    el.x = x; el.y = y; el.w = w2; el.h = h2;
  }

  function pointerUp(e) {
    if (dragMode === 'pan') {
      wrap.classList.remove('panning');
    } else if (dragMode === 'draw' && draftElement) {
      const b = bbox(draftElement);
      const tooSmall = draftElement.type !== 'pencil' && draftElement.type !== 'line' && draftElement.type !== 'arrow' && b.w < 2 && b.h < 2;
      if (!tooSmall) {
        snapshot();
        elements.push(draftElement);
        selectElement(draftElement.id);
        setTool('select');
        scheduleSave();
      }
      draftElement = null;
    } else if (dragMode === 'move' || dragMode === 'resize') {
      scheduleSave();
    }
    dragMode = null; dragOrig = null; dragHandle = null;
    try { canvas.releasePointerCapture(e.pointerId); } catch (_e) { /* noop */ }
    render();
  }

  /* ════════════ Texto ════════════ */
  function startTextInput(worldPos, existing) {
    const canvasRect = canvas.getBoundingClientRect();
    const ta = document.createElement('textarea');
    ta.className = 'pz-text-input';
    ta.setAttribute('wrap', 'off');
    ta.spellcheck = false;
    ta.value = existing ? existing.text : '';
    const fontSize = (existing && existing.fontSize) || 20;
    const fontStr = `${fontSize * zoom}px "Assistant", sans-serif`;
    ta.style.font = fontStr;
    ta.style.color = (existing && existing.color) || color;
    // `position:fixed` va relativo al viewport, así que basta con la posición
    // en pantalla del punto del mundo — no hace falta restar scroll alguno.
    const sx = canvasRect.left + worldPos.x * zoom + offsetX;
    const sy = canvasRect.top + worldPos.y * zoom + offsetY;
    ta.style.left = sx + 'px'; ta.style.top = sy + 'px';
    document.body.appendChild(ta);
    ta.focus();
    // El textarea envuelve por defecto (`wrap=off`/`white-space:pre` sólo
    // evita el salto de línea automático, no cambia cómo mide el propio
    // elemento su tamaño): medir el ancho por `scrollWidth` da el ancho de la
    // caja, no del texto. Se mide con el mismo `ctx.font` que usa el lienzo,
    // así el tamaño en pantalla mientras se escribe coincide con el que
    // tendrá el texto ya dibujado.
    const autoSize = () => {
      ctx.font = fontStr;
      const lines = ta.value.split('\n');
      const textW = Math.max(...lines.map((l) => ctx.measureText(l || ' ').width));
      ta.style.width = (textW + 10) + 'px';
      ta.style.height = 'auto';
      ta.style.height = ta.scrollHeight + 'px';
    };
    ta.addEventListener('input', autoSize);
    autoSize();
    let done = false;
    const commit = () => {
      if (done) return;
      done = true;
      const text = ta.value;
      ta.remove();
      if (!text.trim()) { setTool('select'); return; }
      if (existing) {
        snapshot();
        existing.text = text;
      } else {
        snapshot();
        const el = { id: genId(), type: 'text', x: worldPos.x, y: worldPos.y, text, color, fontSize };
        elements.push(el);
        selectElement(el.id);
      }
      setTool('select');
      scheduleSave();
      render();
    };
    ta.addEventListener('blur', commit);
    ta.addEventListener('keydown', (ev) => {
      if (ev.key === 'Escape') { done = true; ta.remove(); setTool('select'); }
      ev.stopPropagation();
    });
  }

  /* ════════════ Imagen ════════════ */
  let pendingImagePos = null;
  fileInput.addEventListener('change', () => {
    const f = fileInput.files[0];
    fileInput.value = '';
    if (!f) return;
    const reader = new FileReader();
    reader.onload = () => insertImage(reader.result, pendingImagePos);
    reader.readAsDataURL(f);
  });

  function insertImage(dataUrl, worldPos) {
    const img = new Image();
    img.onload = () => {
      const maxDim = 360;
      let w = img.naturalWidth, h = img.naturalHeight;
      if (w > maxDim || h > maxDim) {
        const s = maxDim / Math.max(w, h);
        w *= s; h *= s;
      }
      const pos = worldPos || screenToWorld(wrap.clientWidth / 2, wrap.clientHeight / 2);
      const el = { id: genId(), type: 'image', x: pos.x - w / 2, y: pos.y - h / 2, w, h, src: dataUrl };
      snapshot();
      elements.push(el);
      selectElement(el.id);
      setTool('select');
      scheduleSave();
      render();
    };
    img.src = dataUrl;
  }

  window.addEventListener('paste', (e) => {
    if (!CAN_WRITE) return;
    const items = (e.clipboardData && e.clipboardData.items) || [];
    for (const item of items) {
      if (item.type.startsWith('image/')) {
        const blob = item.getAsFile();
        const reader = new FileReader();
        reader.onload = () => insertImage(reader.result, null);
        reader.readAsDataURL(blob);
        e.preventDefault();
        break;
      }
    }
  });

  /* ════════════ Zoom ════════════ */
  function setZoom(newZoom, screenCx, screenCy) {
    newZoom = Math.max(0.15, Math.min(5, newZoom));
    const before = screenToWorld(screenCx, screenCy);
    zoom = newZoom;
    offsetX = screenCx - before.x * zoom;
    offsetY = screenCy - before.y * zoom;
    zoomLabel.textContent = Math.round(zoom * 100) + '%';
    render();
    scheduleSave();
  }

  wrap.addEventListener('wheel', (e) => {
    e.preventDefault();
    const rect = wrap.getBoundingClientRect();
    const sx = e.clientX - rect.left, sy = e.clientY - rect.top;
    if (e.ctrlKey || e.metaKey) {
      setZoom(zoom * (1 - e.deltaY * 0.002), sx, sy);
    } else {
      offsetX -= e.deltaX; offsetY -= e.deltaY;
      render();
      scheduleSave();
    }
  }, { passive: false });

  document.getElementById('pz-zoom-in').addEventListener('click', () => {
    const r = wrap.getBoundingClientRect();
    setZoom(zoom * 1.2, r.width / 2, r.height / 2);
  });
  document.getElementById('pz-zoom-out').addEventListener('click', () => {
    const r = wrap.getBoundingClientRect();
    setZoom(zoom / 1.2, r.width / 2, r.height / 2);
  });

  /* ════════════ Deshacer / rehacer / eliminar ════════════ */
  function undo() {
    if (!undoStack.length) return;
    redoStack.push(JSON.stringify(elements));
    elements = JSON.parse(undoStack.pop());
    selectElement(null);
    updateUndoRedoButtons();
    scheduleSave();
  }
  function redo() {
    if (!redoStack.length) return;
    undoStack.push(JSON.stringify(elements));
    elements = JSON.parse(redoStack.pop());
    selectElement(null);
    updateUndoRedoButtons();
    scheduleSave();
  }
  function deleteSelected() {
    if (!selectedId) return;
    snapshot();
    elements = elements.filter((e) => e.id !== selectedId);
    selectElement(null);
    scheduleSave();
  }

  /* ════════════ Copiar / duplicar / pegar / orden ════════════ */
  function cloneElementWithOffset(el, dx, dy) {
    const c = JSON.parse(JSON.stringify(el));
    c.id = genId();
    switch (c.type) {
      case 'line': case 'arrow':
        c.x1 += dx; c.y1 += dy; c.x2 += dx; c.y2 += dy;
        break;
      case 'pencil':
        c.points = c.points.map((p) => [p[0] + dx, p[1] + dy]);
        break;
      default:
        c.x += dx; c.y += dy;
    }
    return c;
  }

  function copySelected() {
    const el = elements.find((e) => e.id === selectedId);
    if (el) clipboardEl = JSON.parse(JSON.stringify(el));
  }

  function duplicateSelected() {
    const el = elements.find((e) => e.id === selectedId);
    if (!el || !CAN_WRITE) return;
    snapshot();
    const copy = cloneElementWithOffset(el, 20, 20);
    elements.push(copy);
    selectElement(copy.id);
    scheduleSave();
  }

  function pasteClipboard(worldPos) {
    if (!clipboardEl || !CAN_WRITE) return;
    snapshot();
    let copy;
    if (worldPos) {
      const b = bbox(clipboardEl);
      const cx = b.x + b.w / 2, cy = b.y + b.h / 2;
      copy = cloneElementWithOffset(clipboardEl, worldPos.x - cx, worldPos.y - cy);
    } else {
      copy = cloneElementWithOffset(clipboardEl, 20, 20);
    }
    elements.push(copy);
    selectElement(copy.id);
    scheduleSave();
  }

  function reorderSelected(dir) {
    if (!selectedId || !CAN_WRITE) return;
    const idx = elements.findIndex((e) => e.id === selectedId);
    if (idx < 0) return;
    snapshot();
    const [el] = elements.splice(idx, 1);
    if (dir > 0) elements.push(el); else elements.unshift(el);
    render();
    scheduleSave();
  }

  document.getElementById('pz-undo').addEventListener('click', undo);
  document.getElementById('pz-redo').addEventListener('click', redo);
  document.getElementById('pz-delete').addEventListener('click', deleteSelected);

  /* ════════════ Barra de herramientas ════════════ */
  document.querySelectorAll('.pz-tool[data-tool]').forEach((btn) => {
    btn.addEventListener('click', () => {
      if (btn.dataset.tool === 'icon') {
        iconMenu.classList.toggle('hidden');
        return;
      }
      setTool(btn.dataset.tool);
    });
  });
  document.getElementById('pz-bg-btn').addEventListener('click', () => {
    document.getElementById('pz-bg-menu').classList.toggle('hidden');
  });
  document.addEventListener('click', (e) => {
    if (!document.getElementById('pz-icon-wrap').contains(e.target)) iconMenu.classList.add('hidden');
    if (!document.getElementById('pz-bg-wrap').contains(e.target)) document.getElementById('pz-bg-menu').classList.add('hidden');
  });

  document.getElementById('pz-color').addEventListener('input', (e) => {
    color = e.target.value;
    const sel = elements.find((el) => el.id === selectedId);
    if (sel) { sel.color = color; render(); scheduleSave(); }
  });
  document.getElementById('pz-stroke').addEventListener('change', (e) => {
    strokeWidth = parseFloat(e.target.value);
    const sel = elements.find((el) => el.id === selectedId);
    if (sel && 'strokeWidth' in sel) { sel.strokeWidth = strokeWidth; render(); scheduleSave(); }
  });

  /* ════════════ Teclado ════════════ */
  window.addEventListener('keydown', (e) => {
    if (['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) return;
    if (e.code === 'Space') { spaceHeld = true; wrap.classList.add('tool-pan'); }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') {
      e.preventDefault();
      e.shiftKey ? redo() : undo();
      return;
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'c') {
      if (selectedId) { copySelected(); }
      return;
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'v') {
      if (clipboardEl) { e.preventDefault(); pasteClipboard(null); }
      return;
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'd') {
      if (selectedId) { e.preventDefault(); duplicateSelected(); }
      return;
    }
    if ((e.key === 'Delete' || e.key === 'Backspace') && selectedId) { e.preventDefault(); deleteSelected(); return; }
    if (!CAN_WRITE) return;
    const map = { v: 'select', h: 'pan', r: 'rect', o: 'ellipse', l: 'line', a: 'arrow', p: 'pencil', t: 'text' };
    const k = e.key.toLowerCase();
    if (map[k]) setTool(map[k]);
  });
  window.addEventListener('keyup', (e) => {
    if (e.code === 'Space') { spaceHeld = false; wrap.classList.toggle('tool-pan', tool === 'pan'); }
  });

  canvas.addEventListener('dblclick', () => {
    if (!CAN_WRITE || tool !== 'select') return;
    const el = elements.find((x) => x.id === selectedId);
    if (el && el.type === 'text') startTextInput({ x: el.x, y: el.y }, el);
  });

  /* ════════════ Guardado ════════════ */
  let saveTimer = null;
  let thumbTimer = null;
  function flashStatus(text, ok) {
    statusEl.textContent = text;
    statusEl.classList.add('show');
    statusEl.classList.toggle('error', ok === false);
    clearTimeout(statusEl._t);
    statusEl._t = setTimeout(() => statusEl.classList.remove('show'), 1600);
  }

  async function saveNow() {
    if (!CAN_WRITE) return;
    try {
      const res = await fetch(BOOT.saveUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: BOOT.id,
          elements,
          appState: { zoom, offsetX, offsetY, bgColor },
          files: {},
        }),
      });
      const data = await res.json();
      flashStatus(data.success ? 'Guardado' : (data.error || 'Error al guardar'), !!data.success);
    } catch (_e) {
      flashStatus('Error al guardar', false);
    }
  }

  function scheduleSave() {
    if (!CAN_WRITE) return;
    clearTimeout(saveTimer);
    saveTimer = setTimeout(saveNow, 900);
    clearTimeout(thumbTimer);
    thumbTimer = setTimeout(saveThumb, 4000);
  }

  function saveThumb() {
    if (!CAN_WRITE || !elements.length) return;
    const pad = 40;
    const boxes = elements.map(bbox);
    const minX = Math.min(...boxes.map((b) => b.x)) - pad;
    const minY = Math.min(...boxes.map((b) => b.y)) - pad;
    const maxX = Math.max(...boxes.map((b) => b.x + b.w)) + pad;
    const maxY = Math.max(...boxes.map((b) => b.y + b.h)) + pad;
    const cw = Math.max(1, maxX - minX), ch = Math.max(1, maxY - minY);
    const tw = 480, th = 360;
    const scale = Math.min(tw / cw, th / ch);

    const off = document.createElement('canvas');
    off.width = tw; off.height = th;
    const octx = off.getContext('2d');
    octx.fillStyle = bgColor;
    octx.fillRect(0, 0, tw, th);
    octx.translate((tw - cw * scale) / 2, (th - ch * scale) / 2);
    octx.scale(scale, scale);
    octx.translate(-minX, -minY);

    elements.forEach((el) => {
      octx.save();
      octx.strokeStyle = el.color || '#e9edf5';
      octx.fillStyle = el.color || '#e9edf5';
      octx.lineWidth = (el.strokeWidth || 2);
      octx.lineCap = 'round'; octx.lineJoin = 'round';
      drawElementOn(octx, el);
      octx.restore();
    });
    fetch(BOOT.thumbUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: BOOT.id, dataUrl: off.toDataURL('image/png') }),
    }).catch(() => {});
  }

  function drawElementOn(c, el) {
    switch (el.type) {
      case 'rect': c.strokeRect(el.x, el.y, el.w, el.h); break;
      case 'ellipse':
        c.beginPath();
        c.ellipse(el.x + el.w / 2, el.y + el.h / 2, Math.abs(el.w) / 2, Math.abs(el.h) / 2, 0, 0, Math.PI * 2);
        c.stroke();
        break;
      case 'line':
        c.beginPath(); c.moveTo(el.x1, el.y1); c.lineTo(el.x2, el.y2); c.stroke();
        break;
      case 'arrow':
        c.beginPath(); c.moveTo(el.x1, el.y1); c.lineTo(el.x2, el.y2); c.stroke();
        break;
      case 'pencil':
        if (el.points.length > 1) {
          c.beginPath(); c.moveTo(el.points[0][0], el.points[0][1]);
          el.points.slice(1).forEach((p) => c.lineTo(p[0], p[1]));
          c.stroke();
        }
        break;
      case 'text':
        c.font = `${el.fontSize || 20}px sans-serif`; c.textBaseline = 'top';
        (el.text || '').split('\n').forEach((line, i) => c.fillText(line, el.x, el.y + i * (el.fontSize || 20) * 1.3));
        break;
      case 'image': {
        const img = imgCache.get(el.src);
        if (img && img.complete && img.naturalWidth) c.drawImage(img, el.x, el.y, el.w, el.h);
        break;
      }
      case 'icon': {
        const p = new Path2D(ICONS[el.name] || '');
        c.save(); c.translate(el.x, el.y); c.scale(el.w / 24, el.h / 24); c.lineWidth = 1.8;
        c.stroke(p); c.restore();
        break;
      }
    }
  }

  /* ════════════ Menú contextual (clic derecho) ════════════ */
  const ctxMenu = document.getElementById('pz-ctx-menu');

  function hideContextMenu() {
    ctxMenu.classList.add('hidden');
  }

  function showContextMenu(e) {
    e.preventDefault();
    if (!CAN_WRITE) return;
    const rect = wrap.getBoundingClientRect();
    const sx = e.clientX - rect.left, sy = e.clientY - rect.top;
    const w = screenToWorld(sx, sy);
    lastCtxWorldPos = w;
    const hit = hitElement(w.x, w.y);
    if (hit) selectElement(hit.id);
    ctxMenu.querySelectorAll('[data-need-target]').forEach((el) => {
      el.style.display = hit ? '' : 'none';
    });
    document.getElementById('pz-ctx-paste').disabled = !clipboardEl;

    ctxMenu.classList.remove('hidden');
    ctxMenu.style.left = '0px'; ctxMenu.style.top = '0px';
    const menuRect = ctxMenu.getBoundingClientRect();
    const maxLeft = window.innerWidth - menuRect.width - 8;
    const maxTop = window.innerHeight - menuRect.height - 8;
    ctxMenu.style.left = Math.max(8, Math.min(e.clientX, maxLeft)) + 'px';
    ctxMenu.style.top = Math.max(8, Math.min(e.clientY, maxTop)) + 'px';
  }

  ctxMenu.addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-action]');
    if (!btn || btn.disabled || btn.style.display === 'none') return;
    hideContextMenu();
    const action = btn.dataset.action;
    if (action === 'copy') copySelected();
    else if (action === 'duplicate') duplicateSelected();
    else if (action === 'front') reorderSelected(1);
    else if (action === 'back') reorderSelected(-1);
    else if (action === 'delete') deleteSelected();
    else if (action === 'paste') pasteClipboard(lastCtxWorldPos);
  });
  document.addEventListener('click', (e) => {
    if (!ctxMenu.contains(e.target)) hideContextMenu();
  });
  window.addEventListener('blur', hideContextMenu);
  window.addEventListener('keydown', (e) => { if (e.key === 'Escape') hideContextMenu(); });

  /* ════════════ Arranque ════════════ */
  buildIconMenu();
  buildBgMenu();
  syncBgUi(bgColor);
  if (!CAN_WRITE) {
    document.querySelectorAll('.pz-toolbar .pz-tool[data-tool]:not([data-tool="select"]):not([data-tool="pan"])')
      .forEach((b) => { b.disabled = true; });
    document.getElementById('pz-color').disabled = true;
    document.getElementById('pz-stroke').disabled = true;
    document.getElementById('pz-bg-btn').disabled = true;
    setTool('select');
  } else {
    setTool('select');
  }
  zoomLabel.textContent = Math.round(zoom * 100) + '%';

  canvas.addEventListener('pointerdown', pointerDown);
  canvas.addEventListener('pointermove', pointerMove);
  window.addEventListener('pointerup', pointerUp);
  window.addEventListener('resize', resizeCanvas);
  canvas.addEventListener('contextmenu', showContextMenu);

  resizeCanvas();
  render();
})();
