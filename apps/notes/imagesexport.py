"""Exportar todas las imágenes de una nota a un `.zip`, cada una como `.png`.

Mismo HTML ya renderizado que consumen `notes_pdf`/`notes_doc`
(`prepareExportHtml` en el cliente: imágenes del vault ya incrustadas como
`src="data:image/...;base64,..."`, cookies de sesión aparte) — así que no
hace falta ir al vault ni resolver wikilinks aquí, basta con barrer el HTML
en busca de `<img>` con `data:` URI.

A diferencia de `worddoc.py` (que conserva PNG/JPEG/GIF/BMP/TIFF tal cual y
sólo reconvierte lo demás, porque esos formatos ya los soporta cualquier
versión de Word), aquí se reconvierte SIEMPRE a PNG: no hay un documento
anfitrión cuyo soporte de formato obligue a ir caso por caso, y un único
formato de salida es más predecible para quien abre el zip — que es
exactamente lo que se pidió. Pillow decodifica el formato real a partir de
los bytes, no hace falta fiarse del mimetype que declare el `data:` URI.
"""
import base64
import io
import re
import zipfile

from PIL import Image

_IMG_SRC_RE = re.compile(
    r'<img\b[^>]*\bsrc="(data:image/[a-zA-Z0-9.+-]+;base64,[^"]*)"',
    re.IGNORECASE,
)
_DATA_URI_RE = re.compile(r"^data:image/[a-zA-Z0-9.+-]+;base64,(.+)$", re.DOTALL)


class ImagesExportError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def _decode_png(data_uri):
    """Bytes PNG a partir de un `data:` URI, o `None` si no es una imagen
    decodificable (URI roto, base64 corrupto, bytes que Pillow no reconoce)."""
    m = _DATA_URI_RE.match(data_uri or "")
    if not m:
        return None
    try:
        raw = base64.b64decode(m.group(1), validate=False)
    except Exception:
        return None
    try:
        im = Image.open(io.BytesIO(raw))
        im.load()
    except Exception:
        return None
    if (im.format or "").upper() == "PNG":
        return raw
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        im = im.convert("RGBA")
    else:
        im = im.convert("RGB")
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def extract_images(body_html):
    """Bytes PNG de cada `<img src="data:image/...">` en `body_html`, en el
    orden en que aparecen. Una imagen que no se pueda decodificar se omite
    sin más: no hay nada razonable que hacer con un `data:` URI corrupto
    salvo saltárselo."""
    out = []
    for m in _IMG_SRC_RE.finditer(body_html or ""):
        png = _decode_png(m.group(1))
        if png is not None:
            out.append(png)
    return out


def render_zip(body_html):
    """Bytes de un `.zip` con todas las imágenes de `body_html`, cada una
    como `imagen-NN.png`. Lanza `ImagesExportError` si la nota no tiene
    ninguna."""
    images = extract_images(body_html)
    if not images:
        raise ImagesExportError("La nota no tiene imágenes")
    width = max(2, len(str(len(images))))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, data in enumerate(images, 1):
            zf.writestr(f"imagen-{i:0{width}d}.png", data)
    return buf.getvalue()
