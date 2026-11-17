"""Temas de exportación a PDF: plantillas HTML+CSS, sus imágenes y su relleno.

Un tema es una plantilla escrita a mano (ver `theme_starter.html`) con un
marcador `{{ contenido }}` donde entra la nota. Aquí vive todo lo que toca
disco y todo lo que valida; `pdf.py` sólo imprime y las vistas sólo traducen
a HTTP.

**El HTML del tema no es de fiar aunque lo escriba el dueño de la bóveda.**
Se rellena aquí y lo sanea `pdf.sanitize_html` igual que el cuerpo de la nota:
Chromium imprime desde `file://`, así que un `<img src="file:///etc/passwd">`
o un `background:url(http://interno/...)` colado en un tema sería lectura de
ficheros del servidor o una petición desde dentro de la red. El orden importa
—primero rellenar, luego sanear— porque los marcadores no son URIs válidas y
el saneador tiraría el atributo entero antes de que llegaran a serlo.
"""
import re
import shutil
from base64 import b64encode
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from .models import PdfTheme, PdfThemeImage

MAX_IMAGE_BYTES = 2 * 1024 * 1024
MAX_HTML_CHARS = 120_000
MAX_THEMES = 30
MAX_IMAGES_PER_THEME = 12

IMAGE_MIME = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "webp": "image/webp",
    "gif": "image/gif",
    "svg": "image/svg+xml",
}

CONTENT_TAG = "contenido"
# `{{ contenido }}`, `{{ titulo }}`, `{{ fecha }}`, `{{ img:logo }}`
#
# A propósito NO hay marcador para la carpeta o la ruta de la nota dentro de la
# bóveda (existió un `{{ carpeta }}` y se quitó): los PDF se reparten a gente
# de fuera —alumnos, clientes— que no tiene por qué ver cómo está organizada
# la bóveda por dentro. El cliente ni siquiera manda la ruta al exportar.
_PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-zA-Z]+)\s*(?::\s*([^}]*?)\s*)?\}\}")
_HAS_CONTENT_RE = re.compile(r"\{\{\s*%s\s*\}\}" % CONTENT_TAG)
_SVG_RE = re.compile(rb"<(\?xml|svg)\b", re.IGNORECASE)
_IMAGE_NAME_RE = re.compile(r"^[a-zA-Z0-9._-]{1,60}$")

_MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
          "agosto", "septiembre", "octubre", "noviembre", "diciembre")

# Colores de acento para la miniatura del selector de temas: los primeros
# `#hex` que declara el propio `:root{...}` del tema, en el orden en que los
# escribió quien lo redactó. Funciona porque los tres temas de fábrica (y el
# starter) ya siguen esa convención a propósito — el primer color del `:root`
# es siempre el de marca, no un fondo o un gris. No hay forma de saber esto
# con certeza para un tema ajeno, pero es la mejor aproximación sin renderizar
# de verdad la plantilla (que sería carísimo sólo para pintar una miniatura).
_ROOT_BLOCK_RE = re.compile(r":root\s*\{(.*?)\}", re.S)
_HEX_COLOR_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")
_BODY_BG_RE = re.compile(r"(?:html\s*,\s*)?\bbody\s*\{[^}]*\bbackground\s*:\s*(#[0-9a-fA-F]{3,8})", re.S)
MAX_ACCENT_COLORS = 3


def accent_colors(theme_html: str) -> list[str]:
    """Los colores de marca del tema, para colorear su miniatura. Ver arriba."""
    match = _ROOT_BLOCK_RE.search(theme_html)
    if not match:
        return []
    colors = []
    for hexcolor in _HEX_COLOR_RE.findall(match.group(1)):
        if hexcolor.lower() not in (c.lower() for c in colors):
            colors.append(hexcolor)
        if len(colors) >= MAX_ACCENT_COLORS:
            break
    return colors


def _hex_luma(hexcolor: str) -> float | None:
    hexcolor = hexcolor.lstrip("#")
    if len(hexcolor) == 3:
        hexcolor = "".join(c * 2 for c in hexcolor)
    if len(hexcolor) < 6:
        return None
    try:
        r, g, b = (int(hexcolor[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return None
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255


def is_dark_theme(theme_html: str) -> bool:
    """Si el tema pinta `body`/`html` de oscuro, la miniatura debe seguirle."""
    match = _BODY_BG_RE.search(theme_html)
    if not match:
        return False
    luma = _hex_luma(match.group(1))
    return luma is not None and luma < 0.5


class ThemeError(Exception):
    """Tema inválido, con el mensaje y el status ya decididos."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def starter_html() -> str:
    """La plantilla de ejemplo, comentada, con la que se estrena un tema."""
    return (Path(__file__).parent / "theme_starter.html").read_text(encoding="utf-8")


# Nota de mentira para la vista previa del editor: lleva a propósito un poco de
# TODO lo que puede salir en una nota, con el mismo marcado que genera el
# cliente (`postProcess` en notes.js: callouts con su icono, tablas en
# `.table-wrap`, código resaltado por highlight.js, propiedades, etiquetas,
# tareas, notas al pie, incrustaciones), para que se vea de un vistazo qué le
# hace el tema a cada cosa — y texto suficiente para pasar de una página y
# comprobar que la cabecera y el pie se repiten.
SAMPLE_NOTE_HTML = """
<div class="note-props"><table><tr><th>autor</th><td>Equipo de formación</td></tr><tr><th>tema</th><td>Ejemplo de tema PDF</td></tr><tr><th>tags</th><td>muestra, pdf</td></tr></table></div>
<h1>Nota de muestra</h1>
<p>Este PDF sirve para ver cómo queda el tema que estás escribiendo. El texto no
es de ninguna nota real: es un ejemplo con un poco de cada cosa que puede
aparecer en una nota. Etiquetas: <a class="tag-pill" data-tag="muestra">#muestra</a> <a class="tag-pill" data-tag="pdf">#pdf</a></p>
<p>Un párrafo con <strong>negrita</strong>, <em>cursiva</em>, un
<a href="https://example.com">enlace</a>, un <a class="wikilink" data-target="Otra nota">enlace interno</a>,
<mark>texto resaltado</mark> y <code>código en línea</code>.</p>
<div class="callout" data-cl="info"><div class="callout-title"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 11v5M12 8h.01"/></svg><span>Objetivo</span></div><div class="callout-content"><p>Un callout de tipo <code>info</code>. Los de Obsidian (<code>[!tip]</code>, <code>[!warning]</code>…) salen así en el PDF.</p></div></div>
<h2>1. Una tabla</h2>
<div class="table-wrap"><table><thead><tr><th>Concepto</th><th>Importe</th><th>Estado</th></tr></thead>
<tbody><tr><td>Primera fila</td><td>120,00 €</td><td>Pagado</td></tr>
<tr><td>Segunda fila</td><td>148,50 €</td><td>Pendiente</td></tr>
<tr><td>Tercera fila</td><td>96,30 €</td><td>Pagado</td></tr></tbody></table></div>
<div class="callout" data-cl="tip"><div class="callout-title"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v3M12 19v3M5 12H2M22 12h-3M19 5l-2 2M7 17l-2 2M19 19l-2-2M7 7 5 5"/><circle cx="12" cy="12" r="4"/></svg><span>Consejo</span></div><div class="callout-content"><p>Un callout de tipo <code>tip</code>.</p></div></div>
<blockquote><p>Una cita destacada, para ver el filete lateral y el color.</p></blockquote>
<h2>2. Código e imágenes</h2>
<h3>2.1 Un bloque de código</h3>
<pre><code class="hljs language-python"><span class="hljs-keyword">def</span> <span class="hljs-title function_">saludar</span>(<span class="hljs-params">nombre</span>):
    <span class="hljs-comment"># Devuelve un saludo</span>
    <span class="hljs-keyword">return</span> <span class="hljs-string">f"Hola, <span class="hljs-subst">{nombre}</span>"</span>

<span class="hljs-built_in">print</span>(saludar(<span class="hljs-string">"mundo"</span>), <span class="hljs-number">42</span>)</code><span class="lang-label">python</span></pre>
<h3>2.2 Una imagen</h3>
<p><img src="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NDAiIGhlaWdodD0iMjIwIiB2aWV3Qm94PSIwIDAgNjQwIDIyMCI+PGRlZnM+PGxpbmVhckdyYWRpZW50IGlkPSJnIiB4MT0iMCIgeTE9IjAiIHgyPSIxIiB5Mj0iMSI+PHN0b3Agb2Zmc2V0PSIwIiBzdG9wLWNvbG9yPSIjZTVlN2ViIi8+PHN0b3Agb2Zmc2V0PSIxIiBzdG9wLWNvbG9yPSIjY2JkNWUxIi8+PC9saW5lYXJHcmFkaWVudD48L2RlZnM+PHJlY3Qgd2lkdGg9IjY0MCIgaGVpZ2h0PSIyMjAiIGZpbGw9InVybCgjZykiLz48cmVjdCB3aWR0aD0iNjQwIiBoZWlnaHQ9IjI2IiBmaWxsPSIjMzM0MTU1Ii8+PGNpcmNsZSBjeD0iMTgiIGN5PSIxMyIgcj0iNSIgZmlsbD0iI2Y4NzE3MSIvPjxjaXJjbGUgY3g9IjM2IiBjeT0iMTMiIHI9IjUiIGZpbGw9IiNmYmJmMjQiLz48Y2lyY2xlIGN4PSI1NCIgY3k9IjEzIiByPSI1IiBmaWxsPSIjMzRkMzk5Ii8+PHJlY3QgeD0iNDAiIHk9IjYwIiB3aWR0aD0iMzAwIiBoZWlnaHQ9IjE2IiByeD0iNCIgZmlsbD0iIzk0YTNiOCIvPjxyZWN0IHg9IjQwIiB5PSI5MiIgd2lkdGg9IjQ2MCIgaGVpZ2h0PSIxMiIgcng9IjQiIGZpbGw9IiNhOGIzYzIiLz48cmVjdCB4PSI0MCIgeT0iMTE2IiB3aWR0aD0iNDAwIiBoZWlnaHQ9IjEyIiByeD0iNCIgZmlsbD0iI2E4YjNjMiIvPjxyZWN0IHg9IjQwIiB5PSIxNjAiIHdpZHRoPSIxNDAiIGhlaWdodD0iMzQiIHJ4PSI2IiBmaWxsPSIjNjQ3NDhiIi8+PC9zdmc+" alt="Captura de ejemplo"></p>
<div class="callout" data-cl="warning"><div class="callout-title"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3.5 2 21h20L12 3.5z"/><path d="M12 10v5M12 18h.01"/></svg><span>Cuidado</span></div><div class="callout-content"><p>Un callout de tipo <code>warning</code>.</p></div></div>
<div class="callout" data-cl="success"><div class="callout-title"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="m8 12 3 3 5-6"/></svg><span>Hecho</span></div><div class="callout-content"><p>Un callout de tipo <code>success</code>.</p></div></div>
<div class="callout" data-cl="danger"><div class="callout-title"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="m9 9 6 6M15 9l-6 6"/></svg><span>Peligro</span></div><div class="callout-content"><p>Un callout de tipo <code>danger</code>.</p></div></div>
<div class="callout" data-cl="question"><div class="callout-title"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.3 9.3a3 3 0 1 1 4.2 1.7c-.8.4-1 1-1 1.8v.3M12 17h.01"/></svg><span>Pregunta</span></div><div class="callout-content"><p>Un callout de tipo <code>question</code>.</p></div></div>
<div class="callout" data-cl="example"><div class="callout-title"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 9h6v6H9z"/></svg><span>Ejemplo</span></div><div class="callout-content"><p>Un callout de tipo <code>example</code>.</p></div></div>
<div class="callout" data-cl="quote"><div class="callout-title"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M7 7h4v4H8c0 2 1 3 3 3v2c-3 0-5-2-5-5V7zm10 0h4v4h-3c0 2 1 3 3 3v2c-3 0-5-2-5-5V7z"/></svg><span>Cita</span></div><div class="callout-content"><p>Un callout de tipo <code>quote</code>.</p></div></div>
<h2>3. Listas</h2>
<ol><li>Primer paso numerado</li><li>Segundo paso, con una sublista:<ul><li>Un punto</li><li>Otro punto<ul><li>Tercer nivel</li></ul></li></ul></li><li>Tercer paso</li></ol>
<ul><li class="task-list-item"><input type="checkbox" checked disabled> Tarea hecha</li><li class="task-list-item"><input type="checkbox" disabled> Tarea pendiente</li></ul>
<hr>
<h4>Un encabezado de cuarto nivel</h4>
<p>Un texto con nota al pie<sup class="fn-ref"><a href="#fn-1">1</a></sup>.</p>
<div class="internal-embed"><div class="embed-title">▣ Otra nota</div><div class="embed-body"><p>Contenido de una nota incrustada con <code>![[Otra nota]]</code>.</p></div></div>
""" + "<p>Texto de relleno para que la muestra pase de una página y se vea que la cabecera y el pie se repiten en todas.</p>" * 8 + """
<ol class="footnotes"><li id="fn-1">El texto de la nota al pie.</li></ol>
"""

# ── Imágenes en disco ────────────────────────────────────────────────────────

def themes_root() -> Path:
    root = Path(settings.DATA_ROOT) / "themes"
    root.mkdir(parents=True, exist_ok=True)
    return root


def image_path(image: PdfThemeImage) -> Path:
    return themes_root() / str(image.theme_id) / f"{image.pk}.{image.ext}"


def detect_image_kind(head: bytes) -> str | None:
    """Extensión canónica según los bytes mágicos, o `None` si no es imagen.

    Se mira el contenido, no la extensión ni el `Content-Type`: los dos los
    elige quien sube el fichero. El SVG no tiene bytes mágicos fijos (puede
    empezar por `<?xml` o por `<svg`, con espacios o BOM delante), así que se
    busca esa apertura en la cabecera ya sin BOM.
    """
    if head.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head.startswith(b"GIF87a") or head.startswith(b"GIF89a"):
        return "gif"
    if head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        return "webp"
    if _SVG_RE.match(head.lstrip(b"\xef\xbb\xbf").lstrip()):
        return "svg"
    return None


def add_image(theme: PdfTheme, name: str, upload) -> PdfThemeImage:
    """Guarda una imagen del tema. Levanta `ThemeError`."""
    name = (name or getattr(upload, "name", "") or "").strip()
    name = Path(name).stem or "imagen"
    if not _IMAGE_NAME_RE.match(name):
        raise ThemeError("El nombre sólo puede llevar letras, números, punto, guion y guion bajo")
    if upload.size > MAX_IMAGE_BYTES:
        raise ThemeError("La imagen no puede pasar de 2 MB")
    kind = detect_image_kind(upload.read(512))
    if not kind:
        raise ThemeError("Tiene que ser una imagen (PNG, JPG, WebP, GIF o SVG)")

    existing = theme.images.filter(name=name).first()
    if existing is None and theme.images.count() >= MAX_IMAGES_PER_THEME:
        raise ThemeError(f"Un tema no puede tener más de {MAX_IMAGES_PER_THEME} imágenes")
    if existing is not None:
        remove_image(existing, delete_row=False)
        existing.ext = kind
        existing.save(update_fields=["ext"])
        image = existing
    else:
        image = PdfThemeImage.objects.create(theme=theme, name=name, ext=kind)

    target = image_path(image)
    target.parent.mkdir(parents=True, exist_ok=True)
    # OJO: `upload.chunks()` hace seek(0) por dentro, así que NO se escriben
    # aparte los bytes ya leídos para detectar el tipo (duplicarlos rompería
    # la imagen).
    with open(target, "wb") as fh:
        for chunk in upload.chunks():
            fh.write(chunk)
    return image


def remove_image(image: PdfThemeImage, delete_row: bool = True) -> None:
    for ext in IMAGE_MIME:
        (themes_root() / str(image.theme_id) / f"{image.pk}.{ext}").unlink(missing_ok=True)
    if delete_row:
        image.delete()


def image_data_uri(image: PdfThemeImage) -> str:
    """La imagen como `data:` URI, o `""` si el fichero ya no está.

    Chromium imprime el documento desde `file://` y sin red, así que las
    imágenes tienen que viajar dentro del propio HTML.
    """
    path = image_path(image)
    try:
        raw = path.read_bytes()
    except OSError:
        return ""
    mime = IMAGE_MIME.get(image.ext, "application/octet-stream")
    return f"data:{mime};base64,{b64encode(raw).decode('ascii')}"


# ── Validación y persistencia ────────────────────────────────────────────────

def save_theme(data: dict, theme: PdfTheme | None = None) -> PdfTheme:
    """Crea o actualiza un tema a partir del cuerpo JSON. Levanta `ThemeError`."""
    if theme is None and PdfTheme.objects.count() >= MAX_THEMES:
        raise ThemeError(f"No puedes tener más de {MAX_THEMES} temas")
    name = data.get("name")
    name = name.strip() if isinstance(name, str) else ""
    if not name:
        raise ThemeError("Ponle un nombre al tema")
    if len(name) > 80:
        raise ThemeError("El nombre no puede pasar de 80 caracteres")
    html = data.get("html")
    html = html if isinstance(html, str) else ""
    if len(html) > MAX_HTML_CHARS:
        raise ThemeError("La plantilla no puede pasar de 120.000 caracteres")
    if not _HAS_CONTENT_RE.search(html):
        # Sin este marcador el PDF saldría con la cabecera y la portada pero
        # sin la nota: mejor no dejar guardar que exportar un documento vacío.
        raise ThemeError("La plantilla tiene que incluir {{ contenido }}, "
                         "que es donde se inserta la nota")
    theme = theme or PdfTheme()
    theme.name = name
    theme.html = html
    theme.save()
    return theme


def delete_theme(theme: PdfTheme) -> None:
    shutil.rmtree(themes_root() / str(theme.pk), ignore_errors=True)
    theme.delete()


def theme_json(theme: PdfTheme, with_html: bool = False) -> dict:
    data = {
        "id": theme.pk,
        "name": theme.name,
        "images": [{"id": i.pk, "name": i.name, "ext": i.ext} for i in theme.images.all()],
        "updated_at": theme.updated_at.isoformat() if theme.updated_at else None,
        # Se derivan del `html` en cada petición (no se guardan aparte) para
        # que la miniatura del selector nunca se quede desactualizada, sin
        # tener que mandar los ~120 KB de plantilla sólo para pintar un color.
        "accent": accent_colors(theme.html),
        "dark": is_dark_theme(theme.html),
    }
    if with_html:
        data["html"] = theme.html
    return data


# ── Relleno de la plantilla ──────────────────────────────────────────────────

def _fecha_larga() -> str:
    today = timezone.localdate()
    return f"{today.day} de {_MESES[today.month - 1]} de {today.year}"


def fill(template: str, content_html: str, title: str, images: dict) -> str:
    """Sustituye los marcadores del tema. El resultado hay que sanearlo.

    Una sola pasada de `re.sub`: `re.sub` no vuelve a mirar lo que inserta,
    así que un `{{ img:x }}` que viniera escrito dentro de la NOTA se queda
    como texto en vez de resolverse. Es lo que se quiere — los marcadores son
    del tema, no del contenido.
    """
    from html import escape as html_escape

    def repl(match):
        key = match.group(1).lower()
        arg = (match.group(2) or "").strip()
        if key == CONTENT_TAG:
            return content_html
        if key == "titulo":
            return html_escape(title or "")
        if key == "fecha":
            return _fecha_larga()
        if key == "img":
            return images.get(arg.lower(), "")
        return match.group(0)   # marcador desconocido: se deja tal cual, se ve

    return _PLACEHOLDER_RE.sub(repl, template)


def image_map(theme: PdfTheme) -> dict:
    """`{nombre en minúsculas: data URI}` de todas las imágenes del tema."""
    return {img.name.lower(): image_data_uri(img) for img in theme.images.all()}
