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
# todo (títulos, tabla, código, cita, lista) para que se vea de un vistazo qué
# le hace el tema a cada cosa, y texto suficiente para pasar de una página y
# comprobar que la cabecera y el pie se repiten.
SAMPLE_NOTE_HTML = """
<h1>Nota de muestra</h1>
<p>Este PDF sirve para ver cómo queda el tema que estás escribiendo. El texto no
es de ninguna nota real: es un ejemplo con un poco de cada cosa.</p>
<p>Un párrafo con <strong>negrita</strong>, <em>cursiva</em>, un
<a href="https://example.com">enlace</a> y <code>código en línea</code>.</p>
<h2>Una tabla</h2>
<table><thead><tr><th>Concepto</th><th>Importe</th><th>Estado</th></tr></thead>
<tbody><tr><td>Primera fila</td><td>120,00 €</td><td>Pagado</td></tr>
<tr><td>Segunda fila</td><td>148,50 €</td><td>Pendiente</td></tr>
<tr><td>Tercera fila</td><td>96,30 €</td><td>Pagado</td></tr></tbody></table>
<blockquote>Una cita destacada, para ver el filete lateral y el color.</blockquote>
<h3>Un bloque de código</h3>
<pre><code>def saludar(nombre):
    return f"Hola, {nombre}"</code></pre>
<h2>Una lista</h2>
<ul><li>Primer punto de la lista</li><li>Segundo punto de la lista</li>
<li>Tercer punto de la lista</li></ul>
""" + "<p>Texto de relleno para que la muestra pase de una página y se vea que la cabecera y el pie se repiten en todas.</p>" * 14


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
