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
    lock: 'M6 11V8a6 6 0 0 1 12 0v3M5 11h14v9H5z',
    unlock: 'M7 11V7a5 5 0 0 1 9.6-2M5 11h14v9H5z',
    eye: 'M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7z M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z',
    bell: 'M6.5 17h11v-1l-1.5-1.6V10a4.5 4.5 0 0 0-3.5-4.4V4.2a1.5 1.5 0 0 0-3 0v1.4A4.5 4.5 0 0 0 6 10v4.4L4.5 16v1zM10 19.2a2 2 0 0 0 4 0',
    calendar: 'M4 5h16v16H4zM4 9.5h16M8 2.5v5M16 2.5v5M8 13h3v3H8z',
    clock: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z M12 7.5v5l3.3 2',
    pin: 'M12 22s7-7.4 7-12.5a7 7 0 1 0-14 0C5 14.6 12 22 12 22z M12 12.7a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4z',
    bookmark: 'M6.5 3h11v18l-5.5-4-5.5 4z',
    trophy: 'M7 4h10v5a5 5 0 0 1-10 0V4zM7 5H4.2A2.8 2.8 0 0 0 7 9.5M17 5h2.8A2.8 2.8 0 0 1 17 9.5M9 21h6M12 15v6',
    gift: 'M4 9h16v4H4zM6 9v11h12V9M12 9v11M8.3 9c-1-2.6.8-4.5 2.4-3C11.8 7 12 9 12 9c0-2 .2-4 1.3-5 1.6-1.5 3.4.4 2.4 3',
    camera: 'M4 8h3l1.6-2h6.8L17 8h3v11H4z M12 18.2a4.2 4.2 0 1 0 0-8.4 4.2 4.2 0 0 0 0 8.4z',
    mail: 'M3 5h18v14H3zM3 5.5l9 6.8 9-6.8',
    play: 'M8 5.5v13l11-6.5z',
    thumbsup: 'M7 22V11H4v11zM7 11l4.3-7.6c.8-.3 1.9.4 1.7 1.5L12.3 11h5.4c1.1 0 1.9 1 1.6 2.1l-2 7c-.2.8-1 1.4-1.8 1.4H7',
    smile: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z M8.3 10h.01M15.7 10h.01M7.7 14.5c1 1.6 2.6 2.5 4.3 2.5s3.3-.9 4.3-2.5',
    warning: 'M12 3.3 2 21h20L12 3.3zM12 10v4.5M12 17.8h.01',
    info: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z M12 8.2h.01 M10.7 11h1.6v6h1.4',
    question: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z M9.3 9.2a2.7 2.7 0 1 1 3.7 2.5c-.8.4-1 1-1 1.8v.3M12 17h.01',
    trash: 'M6 7h12M9 7V4.3h6V7M7.3 7 8.2 20h7.6L16.7 7',
    folder: 'M3 6h6l2 2h10v11H3z',
    link: 'M9.5 14.5l5-5 M8.2 11.8l-2 2a3 3 0 1 0 4.2 4.2l2-2 M15.8 12.2l2-2a3 3 0 1 0-4.2-4.2l-2 2',
    search: 'M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16z M21 21l-4.4-4.4',
    shield: 'M12 2.2 20 5.5v6.1c0 5-3.4 8.6-8 10.2-4.6-1.6-8-5.2-8-10.2V5.5z',
    key: 'M8 14.3a4.3 4.3 0 1 1 0-8.6 4.3 4.3 0 0 1 0 8.6z M11.3 11h9.2 M17.2 11v3.2 M20 11v3.2',
    globe: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z M3 12h18 M12 3c2.4 2.4 3.6 5.7 3.6 9s-1.2 6.6-3.6 9c-2.4-2.4-3.6-5.7-3.6-9S9.6 5.4 12 3z',
    compass: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z M15.2 8.8l-2 5.4-5.4 2 2-5.4z',
    crown: 'M3 8.5l4.2 3 4.8-6 4.8 6 4.2-3-2 9.8H5z',
    umbrella: 'M12 2a10 10 0 0 1 10 10H2A10 10 0 0 1 12 2zM12 12v8a2 2 0 0 1-4 0',
    fire: 'M12 22c4 0 6.5-2.6 6.5-6.3 0-3.2-2.2-4.8-2.2-4.8.1 2.1-1 3.2-1 3.2.6-3.2-2-6.3-3.6-7.5.1 2.1-.5 4.2-2.1 5.8-1.4 1.3-2.9 2.4-2.9 4.8 0 2.8 2.3 4.8 5.3 6.8z',
    car: 'M8 12l2-4h4l2 4M3 12h18v4H3zM7 19a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM17 19a2 2 0 1 0 0-4 2 2 0 0 0 0 4z',
    cart: 'M3 4h3l2 12h11l2-8H7 M9.2 20.2a1.2 1.2 0 1 0 0-2.4 1.2 1.2 0 0 0 0 2.4zM17.2 20.2a1.2 1.2 0 1 0 0-2.4 1.2 1.2 0 0 0 0 2.4z',
    dollar: 'M12 2.5v19M16 6.8c0-1.6-1.7-2.8-4-2.8s-4 1.1-4 2.8 1.7 2.5 4 2.8 4 1.2 4 2.9-1.7 2.7-4 2.7-4-1-4-2.7',
  };

  /* ════════════ Elementos (dispositivos, trazos propios) ════════════ */
  const ELEMENT_ICONS = {
    monitor: 'M3 4h18v12H3zM8 20h8M12 16v4',
    desktop: 'M7 3h10v18H7zM9 7h6M9 11h.01M9 15h6',
    laptop: 'M5 5h14v9H5zM2 18h20l-1.5-3h-17z',
    server: 'M4 4h16v6H4zM4 12h16v6H4zM7 7h.01M7 15h.01',
    printer: 'M7 9V4h10v5M4 9h16v7h-4v3H8v-3H4zM8 13h8',
    phone: 'M8 2h8a1 1 0 0 1 1 1v18a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1zM11.5 19h1',
    tablet: 'M5 3h14a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1zM11 18h2',
    router: 'M4.5 16h15v4h-15zM8.5 13a5 5 0 0 1 7 0M6 10a9 9 0 0 1 12 0',
    keyboard: 'M2 6h20v12H2zM5 9h.01M8 9h.01M11 9h.01M14 9h.01M17 9h.01M5 12h.01M8 12h8',
    database: 'M12 4c3.9 0 7 1 7 2.2S15.9 8.4 12 8.4 5 7.4 5 6.2 8.1 4 12 4zM5 6.2v11.6c0 1.2 3.1 2.2 7 2.2s7-1 7-2.2V6.2M5 12c0 1.2 3.1 2.2 7 2.2s7-1 7-2.2',
    mouse: 'M12 2a5 5 0 0 0-5 5v10a5 5 0 0 0 10 0V7a5 5 0 0 0-5-5zM12 2v6',
    speaker: 'M4 8h4l6-4v16l-6-4H4zM16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12',
    headphones: 'M4 15v-3a8 8 0 0 1 16 0v3M4 15h1.6a1 1 0 0 1 1 1v3a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-3a1 1 0 0 1 1-1zM18.4 15H20a1 1 0 0 1 1 1v3a1 1 0 0 1-1 1h-1.6a1 1 0 0 1-1-1v-3a1 1 0 0 1 1-1z',
    webcam: 'M12 15a5 5 0 1 0 0-10 5 5 0 0 0 0 10zM12 10h.01M8 21h8M12 15v6',
    gamepad: 'M6.5 9h11a4 4 0 0 1 4 4v2.5a2 2 0 0 1-3.6 1.2L16 15H8l-1.9 1.7A2 2 0 0 1 2.5 15.5V13a4 4 0 0 1 4-4zM6.7 12v2M5.7 13h2M15.3 11.2h.01M17.8 13.2h.01',
    usbdrive: 'M2 10h5v4H2zM7 8h11a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2H7zM11 12h.01',
    harddisk: 'M4.5 6h15v12h-15zM4.5 14.5h15M8 17.3h.01M11.3 17.3h.01',
    cpu: 'M8.5 4v3M12 4v3M15.5 4v3M8.5 17v3M12 17v3M15.5 17v3M4 8.5h3M4 12h3M4 15.5h3M17 8.5h3M17 12h3M17 15.5h3M7.5 7.5h9v9h-9z',
    powerplug: 'M9 2.5v5.5M15 2.5v5.5M6 8h12v3.5a6 6 0 0 1-12 0zM12 17.5v4',
    smartwatch: 'M8 8h8v8H8zM9 8V5.3h6V8M9 16v2.7h6V16M6 11h2M16 11h2',
  };
  // No forma parte del set "General" (aparece sólo en la pestaña "Personas"
  // del picker), pero necesita estar en la tabla de búsqueda de trazos para
  // que un elemento type:'icon' con name:'hacker' se pueda dibujar.
  const HACKER_PATH = 'M12 3a5 5 0 0 0-5 5c0 1.9.9 3.6 2.3 4.6L8 15h8l-1.3-2.4A5 5 0 0 0 17 8a5 5 0 0 0-5-5z M8.3 9.3h7.4 M4 21c1.1-4.3 4.2-6.5 8-6.5s6.9 2.2 8 6.5';
  const ALL_ICONS = Object.assign({}, ICONS, ELEMENT_ICONS, { hacker: HACKER_PATH });

  /* ════════════ Biblioteca de iconos importados (PNG propios, ver
   * apps/whiteboard/static/whiteboard/library/) ════════════ */
  const LIBRARY_ICONS = {
    brands: [
      { key: 'slack', label: 'Slack', w: 84.5, h: 84.4 },
      { key: 'docker', label: 'Docker', w: 84.5, h: 84.4 },
      { key: 'github', label: 'GitHub', w: 84.5, h: 84.4 },
    ],
    network: [
      { key: 'vpc', label: 'VPC', w: 289.5, h: 184.5 },
      { key: 'device', label: 'dispositivo', w: 64.9, h: 88.7 },
      { key: 'server2', label: 'servidor 2', w: 57.3, h: 89.6 },
      { key: 'computer-kb', label: 'ordenador (teclado)', w: 93.9, h: 100.5 },
      { key: 'computer-kb-mouse', label: 'ordenador (teclado+ratón)', w: 103.4, h: 107.6 },
      { key: 'computer', label: 'ordenador', w: 83.3, h: 96.5 },
      { key: 'vpn', label: 'VPN', w: 141.2, h: 51.6 },
      { key: 'firewall', label: 'firewall', w: 73.6, h: 112.7 },
      { key: 'server', label: 'servidor', w: 89.3, h: 107.8 },
      { key: 'switch', label: 'switch', w: 98.1, h: 76.3 },
      { key: 'hub', label: 'hub', w: 101.5, h: 75.5 },
      { key: 'router', label: 'router', w: 88.0, h: 74.8 },
      { key: 'client', label: 'cliente', w: 88.3, h: 72.4 },
    ],
    people: [
      { key: 'user', label: 'usuario', w: 71.6, h: 87.0 },
      { key: 'users', label: 'usuarios', w: 103.6, h: 79.8 },
    ],
    office: [
      { key: 'email', label: 'email', w: 82.5, h: 61.8 },
      { key: 'parcel', label: 'paquete', w: 91.8, h: 75.5 },
      { key: 'mail', label: 'correo', w: 51.4, h: 38.1 },
      { key: 'letter', label: 'carta', w: 70.6, h: 88.0 },
      { key: 'colour-pen', label: 'rotuladores', w: 77.8, h: 62.7 },
      { key: 'pencil', label: 'lápiz', w: 67.0, h: 63.0 },
      { key: 'screen', label: 'pantalla', w: 130.8, h: 106.6 },
      { key: 'microphone', label: 'micrófono', w: 46.6, h: 60.5 },
      { key: 'headphone-mic', label: 'auriculares+mic', w: 66.6, h: 73.2 },
      { key: 'headphone', label: 'auriculares', w: 66.6, h: 57.8 },
      { key: 'usb-stick', label: 'memoria USB', w: 52.3, h: 101.3 },
      { key: 'cd', label: 'CD', w: 65.4, h: 64.2 },
      { key: 'stamp', label: 'sello', w: 55.7, h: 61.1 },
      { key: 'folder', label: 'carpeta', w: 70.7, h: 131.1 },
      { key: 'paperclip', label: 'clip', w: 36.9, h: 69.5 },
      { key: 'eraser', label: 'goma', w: 75.3, h: 49.5 },
      { key: 'disc', label: 'disquete', w: 58.2, h: 61.1 },
      { key: 'folder2', label: 'carpeta 2', w: 76.7, h: 62.1 },
    ],
    places: [
      { key: 'hq', label: 'oficina central', w: 187, h: 202 },
      { key: 'office', label: 'oficina', w: 78, h: 201 },
      { key: 'city', label: 'ciudad', w: 241.5, h: 204 },
      { key: 'house', label: 'casa', w: 154, h: 181.5 },
      { key: 'datacenter', label: 'centro de datos', w: 264.5, h: 170 },
    ],
  };

  function libraryUrl(cat, key) {
    const v = (window.COGNY && window.COGNY.assetVersion) || 'v1';
    return `/static/whiteboard/library/${cat}/${key}.png?v=${v}`;
  }
  function libItems(cat) {
    return (LIBRARY_ICONS[cat] || []).map((it) => ({
      key: it.key, label: it.label, kind: 'image', url: libraryUrl(cat, it.key), w: it.w, h: it.h,
    }));
  }

  // Categorías del selector "Iconos" (pestañas).
  const ICON_CATEGORIES = [
    { id: 'general', label: 'General', items: Object.keys(ICONS).map((k) => ({ key: k, label: k, kind: 'path', d: ICONS[k] })) },
    { id: 'people', label: 'Personas', items: [
        { key: 'person', label: 'persona', kind: 'path', d: ICONS.person },
        { key: 'hacker', label: 'hacker', kind: 'path', d: HACKER_PATH },
        ...libItems('people'),
      ] },
    { id: 'elements', label: 'Elementos', items: Object.keys(ELEMENT_ICONS).map((k) => ({ key: k, label: k, kind: 'path', d: ELEMENT_ICONS[k] })) },
    { id: 'network', label: 'Red y sistemas', items: libItems('network') },
    { id: 'office', label: 'Oficina', items: libItems('office') },
    { id: 'places', label: 'Lugares', items: libItems('places') },
    { id: 'brands', label: 'Apps y marcas', items: libItems('brands') },
  ];

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

  // ── Contraste automático: si al cambiar de fondo un trazo queda casi
  // invisible (p.ej. un contorno blanco sobre un fondo blanco), se voltea su
  // luminosidad manteniendo el tono — blanco->negro, azul claro->azul oscuro,
  // etc. — en vez de forzar siempre blanco/negro puro.
  function hexToRgb(hex) {
    const c = (hex || '').replace('#', '');
    return { r: parseInt(c.slice(0, 2), 16) || 0, g: parseInt(c.slice(2, 4), 16) || 0, b: parseInt(c.slice(4, 6), 16) || 0 };
  }
  function rgbToHex(r, g, b) {
    const h = (n) => Math.max(0, Math.min(255, Math.round(n))).toString(16).padStart(2, '0');
    return `#${h(r)}${h(g)}${h(b)}`;
  }
  function relLuminance(hex) {
    const { r, g, b } = hexToRgb(hex);
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  }
  function rgbToHsl(r, g, b) {
    r /= 255; g /= 255; b /= 255;
    const max = Math.max(r, g, b), min = Math.min(r, g, b);
    let h = 0, s = 0; const l = (max + min) / 2;
    if (max !== min) {
      const d = max - min;
      s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
      if (max === r) h = (g - b) / d + (g < b ? 6 : 0);
      else if (max === g) h = (b - r) / d + 2;
      else h = (r - g) / d + 4;
      h /= 6;
    }
    return { h, s, l };
  }
  function hslToRgb(h, s, l) {
    if (s === 0) return { r: l * 255, g: l * 255, b: l * 255 };
    const hue2rgb = (p, q, t) => {
      if (t < 0) t += 1;
      if (t > 1) t -= 1;
      if (t < 1 / 6) return p + (q - p) * 6 * t;
      if (t < 1 / 2) return q;
      if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6;
      return p;
    };
    const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
    const p = 2 * l - q;
    return { r: hue2rgb(p, q, h + 1 / 3) * 255, g: hue2rgb(p, q, h) * 255, b: hue2rgb(p, q, h - 1 / 3) * 255 };
  }
  function ensureContrast(colorHex, bgHex) {
    const cl = relLuminance(colorHex), bl = relLuminance(bgHex);
    if (Math.abs(cl - bl) >= 0.35) return colorHex;
    const rgb = hexToRgb(colorHex);
    const hsl = rgbToHsl(rgb.r, rgb.g, rgb.b);
    const targetL = bl > 0.5 ? 0.16 : 0.92;
    const out = hslToRgb(hsl.h, hsl.s, targetL);
    return rgbToHex(out.r, out.g, out.b);
  }

  function autoContrastElements(bg) {
    const toFix = elements.filter((el) => el.color && ensureContrast(el.color, bg) !== el.color);
    if (toFix.length) {
      snapshot();
      toFix.forEach((el) => { el.color = ensureContrast(el.color, bg); });
      syncSelectionUi();
    }
    const newDefault = ensureContrast(color, bg);
    if (newDefault !== color) {
      color = newDefault;
      const colorInput = document.getElementById('pz-color');
      if (colorInput) colorInput.value = color;
    }
  }

  function setBgColor(value) {
    bgColor = value;
    syncBgUi(value);
    if (CAN_WRITE) autoContrastElements(value);
    render();
    scheduleSave();
  }

  // Picker "Iconos" con pestañas por categoría (General, Personas, Red y
  // sistemas, Oficina, Lugares, Apps y marcas) — a diferencia de "Elementos",
  // varias de estas categorías son imágenes PNG propias (ver LIBRARY_ICONS),
  // no trazos, así que el render de cada botón depende de item.kind.
  let activeIconCategory = ICON_CATEGORIES[0].id;
  function buildIconTabs() {
    const tabsEl = document.getElementById('pz-icon-tabs');
    ICON_CATEGORIES.forEach((cat) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'pz-icon-tab';
      b.textContent = cat.label;
      b.dataset.cat = cat.id;
      b.addEventListener('click', () => { activeIconCategory = cat.id; renderIconGrid(); });
      tabsEl.appendChild(b);
    });
    renderIconGrid();
  }
  function renderIconGrid() {
    const gridEl = document.getElementById('pz-icon-grid');
    gridEl.innerHTML = '';
    document.querySelectorAll('#pz-icon-tabs .pz-icon-tab').forEach((b) => {
      b.classList.toggle('active', b.dataset.cat === activeIconCategory);
    });
    const cat = ICON_CATEGORIES.find((c) => c.id === activeIconCategory);
    if (!cat) return;
    cat.items.forEach((item) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = item.kind === 'image' ? 'pz-icon-item is-image' : 'pz-icon-item';
      b.title = item.label;
      b.innerHTML = item.kind === 'image'
        ? `<img src="${item.url}" alt="" loading="lazy">`
        : `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="${item.d}"/></svg>`;
      b.addEventListener('click', () => {
        pendingPlacement = item.kind === 'image'
          ? { kind: 'image', url: item.url, w: item.w, h: item.h }
          : { kind: 'path', name: item.key };
        setTool('icon');
        iconMenu.classList.add('hidden');
      });
      gridEl.appendChild(b);
    });
  }

  /* ════════════ Estado ════════════ */
  let elements = (BOOT.scene && BOOT.scene.elements) || [];
  let selectedIds = new Set();
  let tool = 'select';
  // { kind: 'path', name } para un icono de trazo propio, o
  // { kind: 'image', url, w, h } para uno de la biblioteca importada.
  let pendingPlacement = null;
  let strokeWidth = 3;

  const savedAppState = (BOOT.scene && BOOT.scene.appState) || {};
  let zoom = savedAppState.zoom || 1;
  let offsetX = savedAppState.offsetX || 0;
  let offsetY = savedAppState.offsetY || 0;
  let bgColor = savedAppState.bgColor || '#15181f';
  let clipboardEls = null;
  let lastCtxWorldPos = null;
  // El color por defecto del pincel se calcula contra el fondo GUARDADO, no
  // se hereda de una sesión anterior: si el board se quedó con fondo claro,
  // recargar la página no debe volver a ofrecer un trazo casi blanco.
  let color = ensureContrast('#e9edf5', bgColor);

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
        const p = new Path2D(ALL_ICONS[el.name] || '');
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

  function drawSelection(el, showHandles) {
    const b = bbox(el);
    ctx.save();
    ctx.strokeStyle = '#22d3ee';
    ctx.lineWidth = 1 / zoom;
    ctx.setLineDash([4 / zoom, 3 / zoom]);
    ctx.strokeRect(b.x - 4 / zoom, b.y - 4 / zoom, b.w + 8 / zoom, b.h + 8 / zoom);
    ctx.setLineDash([]);
    // Las asas de redimensión sólo tienen sentido con un único elemento
    // seleccionado — con varios, arrastrar sólo los mueve en bloque.
    if (CAN_WRITE && showHandles && el.type !== 'pencil') {
      ctx.fillStyle = '#22d3ee';
      handlesFor(el).forEach((h) => {
        ctx.beginPath();
        ctx.arc(h.x, h.y, HANDLE_R / zoom, 0, Math.PI * 2);
        ctx.fill();
      });
    }
    ctx.restore();
  }

  function drawMarquee() {
    if (!marqueeRect) return;
    const mx = Math.min(marqueeRect.x0, marqueeRect.x1), my = Math.min(marqueeRect.y0, marqueeRect.y1);
    const mw = Math.abs(marqueeRect.x1 - marqueeRect.x0), mh = Math.abs(marqueeRect.y1 - marqueeRect.y0);
    ctx.save();
    ctx.fillStyle = 'rgba(34,211,238,.1)';
    ctx.strokeStyle = '#22d3ee';
    ctx.lineWidth = 1 / zoom;
    ctx.fillRect(mx, my, mw, mh);
    ctx.strokeRect(mx, my, mw, mh);
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
    if (selectedIds.size) {
      const showHandles = selectedIds.size === 1;
      elements.forEach((e) => { if (selectedIds.has(e.id)) drawSelection(e, showHandles); });
    }
    drawMarquee();
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

  function singleSelected() {
    if (selectedIds.size !== 1) return null;
    return elements.find((e) => selectedIds.has(e.id)) || null;
  }

  function handleAt(wx, wy) {
    // Redimensionar por asas sólo tiene sentido con un único elemento
    // seleccionado; con varios, las asas ni se dibujan (ver drawSelection).
    const sel = singleSelected();
    if (!sel || !CAN_WRITE || sel.type === 'pencil') return null;
    const pad = (HANDLE_R + 3) / zoom;
    return handlesFor(sel).find((h) => Math.hypot(wx - h.x, wy - h.y) <= pad) || null;
  }

  /* ════════════ Herramientas ════════════ */
  function setTool(t) {
    tool = t;
    document.querySelectorAll('.pz-tool[data-tool]').forEach((b) => b.classList.toggle('active', b.dataset.tool === t));
    wrap.classList.toggle('tool-select', t === 'select');
    wrap.classList.toggle('tool-pan', t === 'pan');
    if (t !== 'icon') pendingPlacement = null;
  }

  function syncSelectionUi() {
    const del = document.getElementById('pz-delete');
    del.disabled = !CAN_WRITE || selectedIds.size === 0;
    // El swatch de color/grosor sólo refleja un valor concreto cuando hay UN
    // único elemento elegido — con varios, mostrar el de cualquiera de ellos
    // sería engañoso (parecería que todos comparten ese color).
    if (selectedIds.size === 1) {
      const el = elements.find((e) => selectedIds.has(e.id));
      if (el) {
        document.getElementById('pz-color').value = el.color || color;
        if (el.strokeWidth) document.getElementById('pz-stroke').value = String(el.strokeWidth);
      }
    }
  }

  function selectElement(id) {
    selectedIds = id ? new Set([id]) : new Set();
    syncSelectionUi();
    render();
  }

  function selectMany(ids) {
    selectedIds = new Set(ids);
    syncSelectionUi();
    render();
  }

  function toggleSelect(id) {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id); else next.add(id);
    selectedIds = next;
    syncSelectionUi();
    render();
  }

  let draftElement = null;
  let dragMode = null; // 'draw' | 'move' | 'resize' | 'pan' | 'marquee'
  let dragHandle = null;
  let dragStartWorld = null;
  let dragOrig = null;
  let dragOrigMap = null;
  let marqueeStart = null;
  let marqueeBase = null;
  let marqueeRect = null;
  let panStart = null;
  let spaceHeld = false;

  // El navegador puede negarse a capturar un puntero que no reconoce como
  // "activo" (algún caso raro de entrada táctil/stylus, o un pointerId ya
  // liberado a mitad de un gesto); no es un fallo del que el usuario deba
  // enterarse — el arrastre en curso sigue funcionando igual sin captura,
  // sólo deja de seguir al puntero si sale fuera del lienzo.
  function safeSetCapture(pointerId) {
    try { canvas.setPointerCapture(pointerId); } catch (_e) { /* noop */ }
  }

  function pointerDown(e) {
    if (e.button === 2) return;
    const rect = wrap.getBoundingClientRect();
    const sx = e.clientX - rect.left, sy = e.clientY - rect.top;
    const w = screenToWorld(sx, sy);

    if (e.button === 1 || tool === 'pan' || spaceHeld) {
      dragMode = 'pan';
      panStart = { sx, sy, offsetX, offsetY };
      wrap.classList.add('panning');
      safeSetCapture(e.pointerId);
      return;
    }
    if (!CAN_WRITE) return;

    if (tool === 'select') {
      const h = handleAt(w.x, w.y);
      if (h) {
        dragMode = 'resize'; dragHandle = h.pos; dragStartWorld = w;
        dragOrig = JSON.parse(JSON.stringify(singleSelected()));
        snapshot();
        safeSetCapture(e.pointerId);
        return;
      }
      const hit = hitElement(w.x, w.y);
      if (hit) {
        if (e.shiftKey) {
          // Mayús+clic sólo cambia la pertenencia al grupo — no arrastra, para
          // no mover el elemento sin querer al intentar sumarlo a la selección.
          toggleSelect(hit.id);
          safeSetCapture(e.pointerId);
          return;
        }
        // Clic normal sobre un elemento YA seleccionado (dentro de una
        // selección múltiple): se conserva el grupo entero y se mueve junto.
        // Sobre uno nuevo: la selección se reemplaza por él, como antes.
        if (!selectedIds.has(hit.id)) selectElement(hit.id);
        dragMode = 'move'; dragStartWorld = w;
        dragOrigMap = new Map();
        selectedIds.forEach((id) => {
          const el = elements.find((e2) => e2.id === id);
          if (el) dragOrigMap.set(id, JSON.parse(JSON.stringify(el)));
        });
        snapshot();
        safeSetCapture(e.pointerId);
        return;
      }
      // Lienzo vacío: sin Mayús se reemplaza la selección (se arma con lo que
      // toque el marco); con Mayús se conserva la que ya había y se le suma.
      marqueeBase = e.shiftKey ? new Set(selectedIds) : new Set();
      if (!e.shiftKey) selectElement(null);
      dragMode = 'marquee';
      marqueeStart = w;
      marqueeRect = { x0: w.x, y0: w.y, x1: w.x, y1: w.y };
      safeSetCapture(e.pointerId);
      return;
    }

    if (tool === 'text') {
      e.preventDefault();
      startTextInput(w);
      return;
    }

    if (tool === 'image') {
      pendingImagePos = w;
      fileInput.click();
      return;
    }

    if (tool === 'icon') {
      let el;
      if (pendingPlacement && pendingPlacement.kind === 'image') {
        // Icono de la biblioteca importada: un elemento 'image' normal (misma
        // ruta de dibujo/redimensión/miniatura que una imagen subida), sólo
        // que su src apunta a un PNG propio de la app, no a un dataURL.
        const maxDim = 72;
        const ar = pendingPlacement.w && pendingPlacement.h ? pendingPlacement.w / pendingPlacement.h : 1;
        const iw = ar >= 1 ? maxDim : maxDim * ar;
        const ih = ar >= 1 ? maxDim / ar : maxDim;
        el = { id: genId(), type: 'image', x: w.x - iw / 2, y: w.y - ih / 2, w: iw, h: ih, src: pendingPlacement.url };
      } else {
        const name = (pendingPlacement && pendingPlacement.name) || Object.keys(ICONS)[0];
        const size = 48;
        el = { id: genId(), type: 'icon', name, x: w.x - size / 2, y: w.y - size / 2, w: size, h: size, color };
      }
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
    safeSetCapture(e.pointerId);
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
    if (dragMode === 'move' && dragOrigMap) {
      const dx = w.x - dragStartWorld.x, dy = w.y - dragStartWorld.y;
      dragOrigMap.forEach((origEl, id) => {
        const el = elements.find((e2) => e2.id === id);
        if (el) applyMove(el, origEl, dx, dy);
      });
      render();
      return;
    }
    if (dragMode === 'resize' && dragOrig) {
      const el = singleSelected();
      applyResize(el, dragOrig, dragHandle, w);
      render();
      return;
    }
    if (dragMode === 'marquee') {
      marqueeRect = { x0: marqueeStart.x, y0: marqueeStart.y, x1: w.x, y1: w.y };
      const mx0 = Math.min(marqueeRect.x0, marqueeRect.x1), mx1 = Math.max(marqueeRect.x0, marqueeRect.x1);
      const my0 = Math.min(marqueeRect.y0, marqueeRect.y1), my1 = Math.max(marqueeRect.y0, marqueeRect.y1);
      const within = elements
        .filter((el) => {
          const b = bbox(el);
          return b.x < mx1 && b.x + b.w > mx0 && b.y < my1 && b.y + b.h > my0;
        })
        .map((el) => el.id);
      selectedIds = new Set([...marqueeBase, ...within]);
      syncSelectionUi();
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
    if (el.type === 'text') {
      applyTextResize(el, orig, handle, w);
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

  // El texto no tiene ancho/alto propios (los deriva su contenido + tamaño de
  // fuente), así que "redimensionar" reescala `fontSize` según la distancia
  // arrastrada respecto a la esquina opuesta a la que se agarró — esa esquina
  // opuesta se queda fija, igual que en un rectángulo normal.
  function applyTextResize(el, orig, handle, w) {
    const origSize = measureText(orig);
    const anchorX = handle.includes('w') ? orig.x + origSize.w : orig.x;
    const anchorY = handle.includes('n') ? orig.y + origSize.h : orig.y;
    const dist0 = Math.hypot(origSize.w, origSize.h) || 1;
    const dist1 = Math.hypot(w.x - anchorX, w.y - anchorY);
    const scale = Math.max(0.2, Math.min(8, dist1 / dist0));
    el.fontSize = Math.max(6, Math.round((orig.fontSize || 20) * scale));
    const newSize = measureText(el);
    el.x = handle.includes('w') ? anchorX - newSize.w : anchorX;
    el.y = handle.includes('n') ? anchorY - newSize.h : anchorY;
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
    } else if (dragMode === 'marquee') {
      marqueeRect = null; marqueeBase = null;
    }
    dragMode = null; dragOrig = null; dragOrigMap = null; dragHandle = null;
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
    // El propio clic que abre el cuadro de texto sigue su curso como mousedown
    // nativo DESPUÉS de este handler (pointerdown y mousedown son eventos
    // distintos para un ratón real, a diferencia de lo que simula un test) y
    // su acción por defecto puede devolver el foco a otro sitio justo después
    // de dársela aquí al textarea — history clásica de "no me deja escribir":
    // el cuadro se crea y pierde el foco (blur -> commit con texto vacío ->
    // se borra) antes de que dé tiempo a teclear nada. Aplazarlo a la
    // siguiente vuelta del bucle de eventos hace que gane el foco correcto.
    setTimeout(() => ta.focus(), 0);
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
    if (!selectedIds.size) return;
    snapshot();
    elements = elements.filter((e) => !selectedIds.has(e.id));
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
    const sels = elements.filter((e) => selectedIds.has(e.id));
    if (sels.length) clipboardEls = JSON.parse(JSON.stringify(sels));
  }

  function duplicateSelected() {
    const sels = elements.filter((e) => selectedIds.has(e.id));
    if (!sels.length || !CAN_WRITE) return;
    snapshot();
    const copies = sels.map((el) => cloneElementWithOffset(el, 20, 20));
    elements.push(...copies);
    selectMany(copies.map((c) => c.id));
    scheduleSave();
  }

  function pasteClipboard(worldPos) {
    if (!clipboardEls || !clipboardEls.length || !CAN_WRITE) return;
    snapshot();
    let dx = 20, dy = 20;
    if (worldPos) {
      // Ancla al centro del BLOQUE copiado (no de cada elemento por
      // separado), para que el grupo se pegue conservando su forma relativa.
      const boxes = clipboardEls.map(bbox);
      const gx0 = Math.min(...boxes.map((b) => b.x)), gy0 = Math.min(...boxes.map((b) => b.y));
      const gx1 = Math.max(...boxes.map((b) => b.x + b.w)), gy1 = Math.max(...boxes.map((b) => b.y + b.h));
      dx = worldPos.x - (gx0 + gx1) / 2;
      dy = worldPos.y - (gy0 + gy1) / 2;
    }
    const copies = clipboardEls.map((el) => cloneElementWithOffset(el, dx, dy));
    elements.push(...copies);
    selectMany(copies.map((c) => c.id));
    scheduleSave();
  }

  function reorderSelected(dir) {
    if (!selectedIds.size || !CAN_WRITE) return;
    snapshot();
    // El orden relativo DENTRO del grupo seleccionado se conserva (el filter
    // no reordena); sólo se mueve el bloque entero al principio o al final.
    const selected = elements.filter((e) => selectedIds.has(e.id));
    const rest = elements.filter((e) => !selectedIds.has(e.id));
    elements = dir > 0 ? [...rest, ...selected] : [...selected, ...rest];
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
    const sels = elements.filter((el) => selectedIds.has(el.id));
    if (sels.length) { sels.forEach((el) => { el.color = color; }); render(); scheduleSave(); }
  });
  document.getElementById('pz-stroke').addEventListener('change', (e) => {
    strokeWidth = parseFloat(e.target.value);
    const sels = elements.filter((el) => selectedIds.has(el.id) && 'strokeWidth' in el);
    if (sels.length) { sels.forEach((el) => { el.strokeWidth = strokeWidth; }); render(); scheduleSave(); }
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
      if (selectedIds.size) { copySelected(); }
      return;
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'v') {
      if (clipboardEls && clipboardEls.length) { e.preventDefault(); pasteClipboard(null); }
      return;
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'd') {
      if (selectedIds.size) { e.preventDefault(); duplicateSelected(); }
      return;
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'a') {
      if (tool === 'select' && elements.length) { e.preventDefault(); selectMany(elements.map((el) => el.id)); }
      return;
    }
    if ((e.key === 'Delete' || e.key === 'Backspace') && selectedIds.size) { e.preventDefault(); deleteSelected(); return; }
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
    const el = singleSelected();
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
    if (!CAN_WRITE) return Promise.resolve();
    const tw = 480, th = 360;
    const off = document.createElement('canvas');
    off.width = tw; off.height = th;
    const octx = off.getContext('2d');
    octx.fillStyle = bgColor;
    octx.fillRect(0, 0, tw, th);

    // Un lienzo vacío (se borró todo) también debe subir una miniatura —
    // si no, la galería se queda enseñando para siempre la última con
    // contenido en vez de reflejar que ahora está en blanco.
    if (elements.length) {
      const pad = 40;
      const boxes = elements.map(bbox);
      const minX = Math.min(...boxes.map((b) => b.x)) - pad;
      const minY = Math.min(...boxes.map((b) => b.y)) - pad;
      const maxX = Math.max(...boxes.map((b) => b.x + b.w)) + pad;
      const maxY = Math.max(...boxes.map((b) => b.y + b.h)) + pad;
      const cw = Math.max(1, maxX - minX), ch = Math.max(1, maxY - minY);
      const scale = Math.min(tw / cw, th / ch);
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
    }
    return fetch(BOOT.thumbUrl, {
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
        const p = new Path2D(ALL_ICONS[el.name] || '');
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
    // Clic derecho sobre un elemento que YA forma parte de una selección
    // múltiple: se conserva el grupo (para poder duplicar/eliminar todos a
    // la vez). Sobre uno nuevo, la selección se reemplaza por él solo.
    if (hit && !selectedIds.has(hit.id)) selectElement(hit.id);
    ctxMenu.querySelectorAll('[data-need-target]').forEach((el) => {
      el.style.display = hit ? '' : 'none';
    });
    document.getElementById('pz-ctx-paste').disabled = !clipboardEls || !clipboardEls.length;

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
  buildIconTabs();
  buildBgMenu();
  syncBgUi(bgColor);
  document.getElementById('pz-color').value = color;
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

  // El guardado de escena/miniatura va debounced (900ms/4s): si el usuario
  // borra algo y vuelve a la galería enseguida con "Volver", ese timer aún
  // no ha saltado y la galería enseña la miniatura vieja. Si hay algo
  // pendiente, lo forzamos ya y esperamos a que termine antes de navegar.
  const backLink = document.querySelector('.pz-back');
  if (backLink) {
    backLink.addEventListener('click', (e) => {
      if (!CAN_WRITE || (!saveTimer && !thumbTimer)) return;
      e.preventDefault();
      clearTimeout(saveTimer); saveTimer = null;
      clearTimeout(thumbTimer); thumbTimer = null;
      Promise.all([saveNow(), saveThumb()]).finally(() => {
        window.location.href = backLink.href;
      });
    });
  }

  resizeCanvas();
  render();
})();
