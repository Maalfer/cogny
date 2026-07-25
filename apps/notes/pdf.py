"""Exportar una nota a PDF con Chromium headless.

El cliente manda el HTML YA renderizado (KaTeX, Mermaid y highlight.js corren
en el navegador, con las imágenes incrustadas como data-URI). Aquí lo saneamos,
lo envolvemos en un documento autónomo y lo imprimimos. Chromium arranca con
`--disable-javascript`: sólo tiene que maquetar e imprimir.
"""
import glob
import os
import re
import shutil
import subprocess
import tempfile
from html import escape as html_escape
from html.parser import HTMLParser

from django.conf import settings


class PdfError(Exception):
    """Fallo al generar el PDF, con el mensaje y el status ya decididos."""

    def __init__(self, message: str, status: int = 500):
        super().__init__(message)
        self.status = status


# ── Saneado del HTML de la nota ──────────────────────────────────────────────

# Etiquetas sin uso legítimo en el HTML ya renderizado de una nota (no las
# genera marked/KaTeX/Mermaid/highlight.js): se eliminan junto a su contenido.
_UNSAFE_TAGS = {"script", "iframe", "object", "embed", "link", "meta", "base", "applet", "form"}

# html.parser pone en minúsculas todo nombre de etiqueta/atributo, pero SVG
# (que Mermaid genera embebido en el HTML de la nota) es sensible a
# mayúsculas en varios nombres — sin restaurarlos, cosas como viewBox o
# foreignObject dejan de surtir efecto y el diagrama se renderiza mal.
# Tablas de "ajuste" de SVG del propio estándar HTML5 (recortadas a los
# nombres que sí tienen mayúsculas; el resto ya sobrevive intacto).
_SVG_TAG_CASE = {t.lower(): t for t in (
    "altGlyph", "altGlyphDef", "altGlyphItem", "animateColor", "animateMotion",
    "animateTransform", "clipPath", "feBlend", "feColorMatrix",
    "feComponentTransfer", "feComposite", "feConvolveMatrix", "feDiffuseLighting",
    "feDisplacementMap", "feDistantLight", "feDropShadow", "feFlood", "feFuncA",
    "feFuncB", "feFuncG", "feFuncR", "feGaussianBlur", "feImage", "feMerge",
    "feMergeNode", "feMorphology", "feOffset", "fePointLight", "feSpecularLighting",
    "feSpotLight", "feTile", "feTurbulence", "foreignObject", "glyphRef",
    "linearGradient", "radialGradient", "textPath",
)}
_SVG_ATTR_CASE = {a.lower(): a for a in (
    "attributeName", "attributeType", "baseFrequency", "calcMode", "clipPath",
    "clipPathUnits", "diffuseConstant", "edgeMode", "filterUnits", "glyphRef",
    "gradientTransform", "gradientUnits", "kernelMatrix", "kernelUnitLength",
    "keyPoints", "keySplines", "keyTimes", "lengthAdjust", "limitingConeAngle",
    "markerHeight", "markerUnits", "markerWidth", "maskContentUnits", "maskUnits",
    "numOctaves", "pathLength", "patternContentUnits", "patternTransform",
    "patternUnits", "pointsAtX", "pointsAtY", "pointsAtZ", "preserveAlpha",
    "preserveAspectRatio", "primitiveUnits", "refX", "refY", "repeatCount",
    "repeatDur", "requiredExtensions", "requiredFeatures", "specularConstant",
    "specularExponent", "spreadMethod", "startOffset", "stdDeviation",
    "stitchTiles", "surfaceScale", "systemLanguage", "tableValues", "targetX",
    "targetY", "textLength", "viewBox", "viewTarget", "xChannelSelector",
    "yChannelSelector", "zoomAndPan",
)}
# Atributos que pueden apuntar a un recurso: sólo se permiten esquemas inofensivos
# (http/https/mailto/data:image), rutas relativas o fragmentos (#ancla).
_URI_ATTRS = {"src", "href", "xlink:href", "action", "formaction"}
_SAFE_URI_RE = re.compile(r"^(https?:|mailto:|data:image/|#|/|[^:]*$)", re.IGNORECASE)


class _NoteHTMLSanitizer(HTMLParser):
    """Sanitiza el HTML de una nota antes de imprimirlo a PDF.

    Es una lista de bloqueo (no de permiso): el contenido renderizado incluye
    demasiadas etiquetas/atributos legítimos (KaTeX, Mermaid-SVG, highlight.js)
    como para enumerarlos todos sin arriesgarse a romper el renderizado. En su
    lugar neutralizamos los vectores concretos: handlers on*, iframes/objects/
    scripts, y cualquier URI que no sea http(s)/mailto/data:image/relativa
    (bloquea en particular `file://`, que con Chromium en modo headless podría
    leer notas de otros usuarios o el .env del servidor).
    """

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.out = []
        self._skip_depth = 0

    def _clean_attrs(self, attrs):
        cleaned = []
        for name, value in attrs:
            lname = name.lower()
            if lname.startswith("on"):
                continue
            if lname in _URI_ATTRS and value and not _SAFE_URI_RE.match(value.strip()):
                continue
            cleaned.append((_SVG_ATTR_CASE.get(lname, name), value))
        return cleaned

    def _emit_start(self, tag, attrs, self_closing):
        if tag in _UNSAFE_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        tag = _SVG_TAG_CASE.get(tag, tag)
        attr_str = "".join(
            f' {n}="{html_escape(v, quote=True)}"' if v is not None else f" {n}"
            for n, v in self._clean_attrs(attrs)
        )
        self.out.append(f"<{tag}{attr_str}{' /' if self_closing else ''}>")

    def handle_starttag(self, tag, attrs):
        self._emit_start(tag, attrs, self_closing=False)

    def handle_startendtag(self, tag, attrs):
        self._emit_start(tag, attrs, self_closing=True)

    def handle_endtag(self, tag):
        if tag in _UNSAFE_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth:
            return
        self.out.append(f"</{_SVG_TAG_CASE.get(tag, tag)}>")

    def handle_data(self, data):
        if not self._skip_depth:
            self.out.append(data)

    def handle_entityref(self, name):
        if not self._skip_depth:
            self.out.append(f"&{name};")

    def handle_charref(self, name):
        if not self._skip_depth:
            self.out.append(f"&#{name};")

    # Comentarios, doctype y processing instructions se descartan sin más
    # (no aportan nada al HTML ya renderizado de una nota).


def sanitize_html(raw: str) -> str:
    parser = _NoteHTMLSanitizer()
    parser.feed(raw or "")
    parser.close()
    return "".join(parser.out)


# ── Chromium ─────────────────────────────────────────────────────────────────

def _resolve_chromium() -> str:
    """Resuelve un binario Chromium que funcione para imprimir a PDF.

    El paquete `chromium` de Debian (v150, actualizado 2026-07-06) crashea
    en modo headless en este servidor (SIGTRAP / `trap int3` al arrancar,
    independientemente de los flags), lo que rompía la exportación a PDF.
    Preferimos el `chrome-headless-shell` que Playwright deja cacheado: es
    self-contained, está fijado a una versión y funciona de forma fiable.
    Si no hay ninguno, caemos al chromium del sistema como último recurso.
    """
    patterns = [
        "/home/mario/.cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-linux*/chrome-headless-shell",
        "/root/.cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-linux*/chrome-headless-shell",
    ]
    for pat in patterns:
        # Versión más alta primero (orden lexicográfico inverso sobre el nº de build).
        for hit in sorted(glob.glob(pat), reverse=True):
            if os.access(hit, os.X_OK):
                return hit
    return shutil.which("chromium") or shutil.which("chromium-browser") or "/usr/bin/chromium"


CHROMIUM_BIN = _resolve_chromium()

_CSS_CACHE = None


def _styles() -> str:
    """Hojas de estilo del PDF, combinadas y cacheadas.

    `notes_print.css` + highlight + KaTeX (con las fuentes reescritas a
    `file://`). Así el documento es 100% local, sin red, que es lo único fiable
    con Chromium headless `--single-process` ejecutado por www-data.
    """
    global _CSS_CACHE
    if _CSS_CACHE is not None:
        return _CSS_CACHE
    sroot = str(settings.STATIC_ROOT)

    def read(rel):
        try:
            with open(os.path.join(sroot, rel), encoding="utf-8") as fh:
                return fh.read()
        except OSError:
            return ""

    parts = [read("notes/notes_print.css"), read("vendor/highlight-github-dark.min.css")]
    katex = read("vendor/katex/katex.min.css")
    if katex:
        fonts_dir = os.path.join(sroot, "vendor", "katex", "fonts") + "/"
        parts.append(katex.replace("url(fonts/", "url(file://" + fonts_dir))
    _CSS_CACHE = "\n".join(p for p in parts if p)
    return _CSS_CACHE


def render(body_html: str, dark: bool = False) -> bytes:
    """Imprime a PDF el HTML (ya saneado) de una nota. Levanta `PdfError`."""
    body_class = "markdown-body print-dark" if dark else "markdown-body"
    doc = (
        '<!doctype html><html><head><meta charset="utf-8"><style>'
        + _styles() +
        '</style></head><body class="' + body_class + '">' + body_html + '</body></html>'
    )

    workdir = tempfile.mkdtemp(prefix="notepdf_")
    try:
        in_html = os.path.join(workdir, "in.html")
        out_pdf = os.path.join(workdir, "out.pdf")
        with open(in_html, "w", encoding="utf-8") as fh:
            fh.write(doc)
        cmd = [
            CHROMIUM_BIN, "--headless", "--no-sandbox", "--disable-gpu",
            "--disable-dev-shm-usage", "--disable-crash-reporter", "--disable-breakpad",
            "--no-zygote", "--single-process", "--allow-file-access-from-files",
            # El HTML ya viene renderizado, Chromium sólo maqueta e imprime. Esto
            # neutraliza cualquier handler on*/script que se hubiera colado pese
            # al saneado de `sanitize_html`.
            "--disable-javascript",
            "--user-data-dir=" + os.path.join(workdir, "ud"),
            "--no-pdf-header-footer", "--virtual-time-budget=8000",
            "--print-to-pdf=" + out_pdf, "file://" + in_html,
        ]
        env = dict(os.environ, HOME=workdir)
        try:
            subprocess.run(cmd, env=env, timeout=60,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.TimeoutExpired as exc:
            raise PdfError("Tiempo agotado generando el PDF", 504) from exc
        except FileNotFoundError as exc:
            raise PdfError("Chromium no disponible en el servidor") from exc
        if not os.path.exists(out_pdf) or os.path.getsize(out_pdf) == 0:
            raise PdfError("No se pudo generar el PDF")
        with open(out_pdf, "rb") as fh:
            return fh.read()
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
