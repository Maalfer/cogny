"""Exportar una nota a un documento .docx nativo (OOXML), sin dependencias
nuevas y sin levantar ningún conversor externo.

Se probaron dos atajos antes de llegar aquí, y los dos fallaron:

1. Guardar el HTML ya renderizado (el mismo que usa el PDF, con imágenes
   como `data:` URI) tal cual con extensión `.doc`: Word reconoce el truco
   ("Guardar como página web" al revés), pero su filtro de importación de
   HTML NO renderiza imágenes `data:` URI — el texto sale bien, las imágenes
   no, que es justo el bug que se reportó.
2. Envolver ese mismo HTML como un documento MHTML (MIME multipart, imagen
   referenciada por `cid:` en vez de `data:`) y servirlo con extensión
   `.doc`/`.mht`: es el truco que de verdad usa Word para esto y debería
   funcionar ahí, pero no hay forma de probarlo en este entorno (no hay
   Word), y se confirmó en vivo que LibreOffice —headless y abierto de
   verdad— NO lo detecta por contenido y lo trata como texto plano. Validar
   a ciegas una ruta así para algo que se usa de verdad no es aceptable.
   Tampoco se instaló LibreOffice en el VPS para generarlo con su propio
   conversor: la máquina va con ~160 MB de RAM libres y 3 de 4 GB de swap ya
   en uso (ver `free -h`), y LibreOffice headless es pesado — no merece la
   pena el riesgo para los demás servicios que corren ahí (mail, academia,
   dockerlabs, el propio Cogny...).

La alternativa sin ambigüedad: un `.docx` de verdad. Es un zip con partes
XML bien definidas (OOXML) — nada que adivinar por contenido ni por
extensión. Aquí se parsea el HTML ya saneado (reutilizando `html.parser`,
igual que `pdf._NoteHTMLSanitizer`) a un árbol mínimo y se recorre para
emitir WordprocessingML: encabezados, párrafos, negrita/cursiva/código,
enlaces, listas, tablas y, lo importante, las imágenes como partes del
paquete (`word/media/imagenN.ext`) en vez de como `data:` URI — así no hay
nada que un importador de Word tenga que decidir "renderizar o no".

Las capturas del vault son casi todas `.webp`, y el soporte de `.webp`
dentro de un `.docx` es irregular según versión de Word/LibreOffice — así
que cualquier imagen que no sea uno de los formatos clásicos que Word
siempre ha soportado (PNG/JPEG/GIF/BMP/TIFF) se reconvierte a PNG con
Pillow, que ya es dependencia de la app (`requirements.txt`) y no hace
falta instalar nada para esto.

No hay tema ni plantilla: igual que se pidió, la nota sale "tal cual, sin
estilos" — sólo el formato mínimo imprescindible para que el documento se
lea (negrita/cursiva donde tocaba, el código en monoespaciada, la tabla con
bordes finos).

Fuera de alcance, documentado en vez de fingido: las fórmulas de KaTeX se
exportan como su fuente LaTeX en texto plano (se extrae de
`annotation[encoding="application/x-tex"]`, que KaTeX ya incluye en su
HTML) en vez de la fórmula renderizada — reconstruir esa tipografía en
WordprocessingML no tiene un beneficio claro para "sin estilos". Los
diagramas Mermaid (SVG embebido inline, no un `<img>`) se omiten sin más:
rasterizarlos aquí exigiría un motor de render que esta ruta
deliberadamente no tiene (es la razón de ser de este módulo frente a los
dos atajos de arriba).
"""
import base64
import hashlib
import io
import re
from html import escape as xml_escape
from html.parser import HTMLParser

from PIL import Image

# 1 pulgada = 914400 EMU, a 96 ppp (la resolución con la que el cliente ya
# captura/incrusta las imágenes) 1 px = 9525 EMU.
_EMU_PER_PX = 9525
# Ancho máximo dentro del área de texto de una página A4 con márgenes de
# 2.5cm (~6.3in ≈ 605px a 96ppp); una captura de pantalla normal se queda
# dentro, así que esto sólo entra en juego con imágenes muy anchas.
_MAX_IMG_WIDTH_PX = 580

# Formatos que Word ha soportado siempre dentro de un .docx sin depender de
# una versión reciente. Cualquier otra cosa (webp, avif...) se reconvierte.
_WORD_SAFE_FORMATS = {"PNG": "png", "JPEG": "jpeg", "GIF": "gif", "BMP": "bmp", "TIFF": "tiff"}

_WS_RE = re.compile(r"\s+")
_DATA_IMG_RE = re.compile(r"^data:image/[a-zA-Z0-9.+-]+;base64,(.+)$", re.DOTALL)

_VOID_TAGS = {"img", "br", "hr", "input", "meta", "link", "area", "base",
              "col", "embed", "source", "track", "wbr"}
_BLOCK_PASSTHROUGH = {"div", "section", "article", "main", "span", "body",
                      "header", "footer", "aside", "nav"}


# ── Fase 1: HTML (ya saneado) → árbol mínimo ─────────────────────────────────

class _Node:
    __slots__ = ("tag", "attrs", "children")

    def __init__(self, tag, attrs=None):
        self.tag = tag
        self.attrs = dict(attrs or [])
        self.children = []


class _TreeBuilder(HTMLParser):
    """Árbol tolerante: si una etiqueta de cierre no empareja (puede pasar
    tras el saneado), se cierra hasta la más cercana que sí coincida en la
    pila, igual que hace un navegador de verdad — no hace falta un parser
    HTML5 completo para el HTML que ya generó el propio renderer de la app.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _Node("#root")
        self._stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = _Node(tag, attrs)
        self._stack[-1].children.append(node)
        if tag not in _VOID_TAGS:
            self._stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self._stack[-1].children.append(_Node(tag, attrs))

    def handle_endtag(self, tag):
        for i in range(len(self._stack) - 1, 0, -1):
            if self._stack[i].tag == tag:
                del self._stack[i:]
                return

    def handle_data(self, data):
        if data:
            self._stack[-1].children.append(data)


def _text_of(node):
    """Texto plano de un nodo, SIN colapsar espacios — para código (`<pre>`)
    y para la fuente LaTeX de KaTeX, donde el espaciado original importa."""
    out = []

    def walk(n):
        if isinstance(n, str):
            out.append(n)
        else:
            for c in n.children:
                walk(c)
    walk(node)
    return "".join(out)


def _find_katex_tex(node):
    """Busca `annotation[encoding="application/x-tex"]` dentro de un nodo
    `.katex` — KaTeX siempre incluye la fuente LaTeX original ahí (ver
    docstring del módulo). `None` si no hay."""
    if isinstance(node, str):
        return None
    if node.tag == "annotation" and node.attrs.get("encoding") == "application/x-tex":
        return _text_of(node)
    for c in node.children:
        found = _find_katex_tex(c)
        if found is not None:
            return found
    return None


def _decode_data_image(src):
    """`{data, ext, w, h}` a partir de un `src="data:image/...;base64,..."`,
    o `None` si no es una imagen válida. Reconvierte a PNG con Pillow
    cualquier formato que Word no soporte siempre dentro de un .docx (ver
    docstring del módulo) — el propio Pillow decodifica el formato real a
    partir de los bytes, no hace falta fiarse del mimetype declarado."""
    m = _DATA_IMG_RE.match(src or "")
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
    fmt = (im.format or "").upper()
    if fmt in _WORD_SAFE_FORMATS:
        return {"data": raw, "ext": _WORD_SAFE_FORMATS[fmt], "w": im.width, "h": im.height}
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        im = im.convert("RGBA")
    else:
        im = im.convert("RGB")
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return {"data": buf.getvalue(), "ext": "png", "w": im.width, "h": im.height}


# ── Fase 2: árbol → bloques (párrafo/lista/tabla/imagen) ────────────────────

def _collect_runs(node, runs, fmt):
    """Recorre contenido EN LÍNEA (texto, negrita/cursiva/código, enlaces,
    imágenes, saltos de línea) y va añadiendo "runs" — unidades mínimas de
    formato de WordprocessingML — a `runs`."""
    if isinstance(node, str):
        t = _WS_RE.sub(" ", node)
        if t:
            runs.append(dict(fmt, text=t))
        return
    tag = node.tag
    if tag == "br":
        runs.append({"break": True})
        return
    if tag == "img":
        img = _decode_data_image(node.attrs.get("src"))
        if img:
            runs.append({"image": img})
        return
    if tag in ("script", "style", "svg", "iframe", "object"):
        return
    cls = node.attrs.get("class") or ""
    if tag == "span" and "katex" in cls:
        tex = _find_katex_tex(node)
        if tex:
            runs.append(dict(fmt, text=tex, italic=True, code=True))
        return
    new_fmt = dict(fmt)
    if tag in ("b", "strong"):
        new_fmt["bold"] = True
    if tag in ("i", "em"):
        new_fmt["italic"] = True
    if tag == "code":
        new_fmt["code"] = True
    href = node.attrs.get("href") if tag == "a" else None
    if href:
        new_fmt["href"] = href
    for c in node.children:
        _collect_runs(c, runs, new_fmt)


def _build_list(node, out, depth):
    ordered = node.tag == "ol"
    idx = 0
    for li in node.children:
        if isinstance(li, str) or li.tag != "li":
            continue
        idx += 1
        runs, nested = [], []
        for c in li.children:
            if not isinstance(c, str) and c.tag in ("ul", "ol"):
                nested.append(c)
            else:
                _collect_runs(c, runs, {})
        out.append({"type": "li", "runs": runs, "ordered": ordered, "depth": depth, "num": idx})
        for sub in nested:
            _build_list(sub, out, depth + 1)


def _build_table(node):
    trs = []

    def collect(n):
        for c in n.children:
            if isinstance(c, str):
                continue
            if c.tag == "tr":
                trs.append(c)
            elif c.tag in ("thead", "tbody", "tfoot"):
                collect(c)
    collect(node)
    rows = []
    for tr in trs:
        cells = []
        for td in tr.children:
            if isinstance(td, str) or td.tag not in ("td", "th"):
                continue
            runs = []
            _collect_runs(td, runs, {})
            cells.append({"runs": runs, "header": td.tag == "th"})
        if cells:
            rows.append(cells)
    return {"type": "table", "rows": rows}


def _build_blocks(nodes, out):
    for node in nodes:
        if isinstance(node, str):
            t = node.strip()
            if t:
                out.append({"type": "p", "runs": [{"text": _WS_RE.sub(" ", t)}]})
            continue
        tag = node.tag
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            runs = []
            _collect_runs(node, runs, {})
            if runs:
                out.append({"type": "p", "runs": runs, "heading": int(tag[1])})
        elif tag in ("p", "figure", "figcaption"):
            runs = []
            _collect_runs(node, runs, {})
            if runs:
                out.append({"type": "p", "runs": runs})
        elif tag == "blockquote":
            sub = []
            _build_blocks(node.children, sub)
            for b in sub:
                b["quote"] = True
            out.extend(sub)
        elif tag == "pre":
            text = _text_of(node).rstrip("\n")
            lines = text.split("\n") if text else [""]
            runs = []
            for i, line in enumerate(lines):
                if i > 0:
                    runs.append({"break": True})
                if line:
                    runs.append({"text": line, "code": True})
            out.append({"type": "p", "runs": runs, "code": True})
        elif tag in ("ul", "ol"):
            _build_list(node, out, depth=0)
        elif tag == "table":
            tbl = _build_table(node)
            if tbl["rows"]:
                out.append(tbl)
        elif tag == "hr":
            out.append({"type": "hr"})
        elif tag == "img":
            # Normalmente una imagen llega envuelta en un <p> (markdown
            # estándar) o en el <span class="internal-embed"> de un embed
            # ![[archivo]] — ambos caben por el camino de `p`/passthrough de
            # más abajo. Esto es la red de seguridad para una <img> suelta a
            # nivel de bloque, que si no se perdería sin más.
            runs = []
            _collect_runs(node, runs, {})
            if runs:
                out.append({"type": "p", "runs": runs})
        elif tag in ("svg", "script", "style", "iframe", "object"):
            continue
        elif tag in _BLOCK_PASSTHROUGH:
            _build_blocks(node.children, out)
        else:
            # Cualquier otra etiqueta de bloque que no reconozcamos: se trata
            # como contenedor transparente en vez de perder su contenido.
            _build_blocks(node.children, out)


# ── Fase 3: bloques → WordprocessingML ───────────────────────────────────────

_HEADING_SIZES = {1: 32, 2: 28, 3: 26, 4: 24, 5: 22, 6: 22}  # en semipuntos (w:sz)


class _Ctx:
    """Acumula las imágenes y los enlaces de la nota mientras se serializa,
    para escribir sus relaciones (`word/_rels/document.xml.rels`) y sus
    partes (`word/media/...`) de una sola vez al final."""

    def __init__(self):
        self.media = []       # [(name, data, content_type), ...]
        self.rels = []        # [(rId, type, target, target_mode|None), ...]
        self._next_rid = 1
        self._next_docpr = 1
        self._image_rid_by_hash = {}

    def add_image(self, img):
        key = hashlib.sha1(img["data"]).hexdigest()
        cached = self._image_rid_by_hash.get(key)
        if cached:
            return cached
        rid = f"rId{self._next_rid}"
        self._next_rid += 1
        name = f"image{len(self.media) + 1}.{img['ext']}"
        self.media.append((name, img["data"], f"image/{img['ext']}"))
        self.rels.append((rid, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image",
                           f"media/{name}", None))
        result = (rid, name)
        self._image_rid_by_hash[key] = result
        return result

    def add_hyperlink(self, href):
        rid = f"rId{self._next_rid}"
        self._next_rid += 1
        self.rels.append((rid, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
                           href, "External"))
        return rid

    def next_docpr_id(self):
        v = self._next_docpr
        self._next_docpr += 1
        return v


def _image_run_xml(img, ctx):
    rid, name = ctx.add_image(img)
    w_emu, h_emu = img["w"] * _EMU_PER_PX, img["h"] * _EMU_PER_PX
    max_w_emu = _MAX_IMG_WIDTH_PX * _EMU_PER_PX
    if w_emu > max_w_emu and w_emu:
        scale = max_w_emu / w_emu
        w_emu, h_emu = int(w_emu * scale), int(h_emu * scale)
    docpr_id = ctx.next_docpr_id()
    safe_name = xml_escape(name, quote=True)
    return (
        '<w:r><w:drawing>'
        f'<wp:inline distT="0" distB="0" distL="0" distR="0">'
        f'<wp:extent cx="{w_emu}" cy="{h_emu}"/>'
        '<wp:effectExtent l="0" t="0" r="0" b="0"/>'
        f'<wp:docPr id="{docpr_id}" name="{safe_name}"/>'
        '<wp:cNvGraphicFramePr>'
        '<a:graphicFrameLocks xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" noChangeAspect="1"/>'
        '</wp:cNvGraphicFramePr>'
        '<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
        '<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        '<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        f'<pic:nvPicPr><pic:cNvPr id="{docpr_id}" name="{safe_name}"/><pic:cNvPicPr/></pic:nvPicPr>'
        f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
        f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{w_emu}" cy="{h_emu}"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
        '</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r>'
    )


def _run_xml(run, ctx):
    if run.get("break"):
        return "<w:r><w:br/></w:r>"
    if "image" in run:
        return _image_run_xml(run["image"], ctx)
    text = run.get("text", "")
    if not text:
        return ""
    props = []
    if run.get("bold"):
        props.append("<w:b/>")
    if run.get("italic"):
        props.append("<w:i/>")
    if run.get("code"):
        props.append('<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:cs="Consolas"/>')
        props.append('<w:shd w:val="clear" w:color="auto" w:fill="F3F3F3"/>')
    if run.get("href"):
        props.append('<w:color w:val="1155CC"/><w:u w:val="single"/>')
    if run.get("size"):
        props.append(f'<w:sz w:val="{run["size"]}"/><w:szCs w:val="{run["size"]}"/>')
    rpr = f"<w:rPr>{''.join(props)}</w:rPr>" if props else ""
    run_xml = f'<w:r>{rpr}<w:t xml:space="preserve">{xml_escape(text)}</w:t></w:r>'
    href = run.get("href")
    if href:
        rid = ctx.add_hyperlink(href)
        return f'<w:hyperlink r:id="{rid}">{run_xml}</w:hyperlink>'
    return run_xml


def _paragraph_xml(block, ctx):
    pprops = []
    heading = block.get("heading")
    if block.get("quote"):
        pprops.append('<w:ind w:left="720"/><w:pBdr><w:left w:val="single" w:sz="12" w:space="8" w:color="BFBFBF"/></w:pBdr>')
    if block.get("type") == "li":
        depth = block.get("depth", 0)
        pprops.append(f'<w:ind w:left="{420 + depth * 420}" w:hanging="420"/>')
    ppr = f"<w:pPr>{''.join(pprops)}</w:pPr>" if pprops else ""
    runs = list(block["runs"])
    if block.get("type") == "li":
        bullet = f'{block.get("num", 1)}.  ' if block.get("ordered") else "•  "
        runs = [{"text": bullet}] + runs
    runs_xml = []
    for run in runs:
        if heading and "image" not in run and not run.get("break"):
            run = dict(run, bold=True, size=_HEADING_SIZES.get(heading, 22))
        runs_xml.append(_run_xml(run, ctx))
    return f"<w:p>{ppr}{''.join(runs_xml)}</w:p>"


def _table_xml(block, ctx):
    ncols = max((len(r) for r in block["rows"]), default=1)
    colw = max(1, 9026 // max(ncols, 1))
    grid = "".join(f'<w:gridCol w:w="{colw}"/>' for _ in range(ncols))
    rows_xml = []
    for row in block["rows"]:
        cells_xml = []
        for cell in row:
            runs = cell["runs"]
            if cell.get("header"):
                runs = [dict(r, bold=True) if "image" not in r and not r.get("break") else r for r in runs]
            body = "".join(_run_xml(r, ctx) for r in runs) or "<w:r><w:t/></w:r>"
            cells_xml.append(f'<w:tc><w:tcPr><w:tcW w:w="{colw}" w:type="dxa"/></w:tcPr><w:p>{body}</w:p></w:tc>')
        rows_xml.append(f"<w:tr>{''.join(cells_xml)}</w:tr>")
    borders = "".join(
        f'<w:{side} w:val="single" w:sz="4" w:space="0" w:color="BFBFBF"/>'
        for side in ("top", "left", "bottom", "right", "insideH", "insideV")
    )
    tbl_pr = f'<w:tblPr><w:tblW w:w="0" w:type="auto"/><w:tblBorders>{borders}</w:tblBorders></w:tblPr>'
    return f"<w:tbl>{tbl_pr}<w:tblGrid>{grid}</w:tblGrid>{''.join(rows_xml)}</w:tbl>"


_HR_XML = '<w:p><w:pPr><w:pBdr><w:bottom w:val="single" w:sz="6" w:space="1" w:color="BFBFBF"/></w:pBdr></w:pPr></w:p>'


def render(body_html: str, title: str = "") -> bytes:
    """`.docx` nativo (zip OOXML) a partir del HTML ya saneado de una nota.

    `body_html` debe venir ya pasado por `pdf.sanitize_html` — este módulo no
    vuelve a sanearlo (mismo contrato que `pdf.render`, que tampoco resanea
    el cuerpo que recibe)."""
    tree = _TreeBuilder()
    tree.feed(body_html or "")
    tree.close()
    blocks = []
    _build_blocks(tree.root.children, blocks)

    ctx = _Ctx()
    body_parts = []
    for b in blocks:
        if b["type"] == "table":
            body_parts.append(_table_xml(b, ctx))
        elif b["type"] == "hr":
            body_parts.append(_HR_XML)
        else:
            body_parts.append(_paragraph_xml(b, ctx))
    if not body_parts:
        body_parts.append("<w:p/>")

    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document '
        'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing">'
        '<w:body>' + "".join(body_parts) +
        '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1417" w:right="1417" w:bottom="1417" w:left="1417" w:header="708" w:footer="708" w:gutter="0"/>'
        '</w:sectPr></w:body></w:document>'
    )

    document_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(
            f'<Relationship Id="{rid}" Type="{rtype}" Target="{xml_escape(target, quote=True)}"'
            + (f' TargetMode="{tmode}"' if tmode else '') + '/>'
            for rid, rtype, target, tmode in ctx.rels
        )
        + '</Relationships>'
    )

    img_extensions = sorted({ctype.split("/", 1)[1] for _, _, ctype in ctx.media})
    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        + "".join(f'<Default Extension="{ext}" ContentType="image/{ext}"/>' for ext in img_extensions)
        + '<Override PartName="/word/document.xml" '
          'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        '</Types>'
    )

    root_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/>'
        '<Relationship Id="rId2" '
        'Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" '
        'Target="docProps/core.xml"/>'
        '</Relationships>'
    )

    safe_title = xml_escape((title or "nota").strip()[:200] or "nota")
    core_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/">'
        f'<dc:title>{safe_title}</dc:title>'
        '</cp:coreProperties>'
    )

    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types_xml)
        z.writestr("_rels/.rels", root_rels_xml)
        z.writestr("docProps/core.xml", core_xml)
        z.writestr("word/document.xml", document_xml)
        z.writestr("word/_rels/document.xml.rels", document_rels_xml)
        for name, data, _ctype in ctx.media:
            z.writestr(f"word/media/{name}", data)
    return buf.getvalue()
