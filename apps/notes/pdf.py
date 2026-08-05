"""Exportar una nota a PDF con Chromium headless.

El cliente manda el HTML YA renderizado (KaTeX, Mermaid y highlight.js corren
en el navegador, con las imágenes incrustadas como data-URI). Aquí lo saneamos,
lo envolvemos en un documento autónomo y lo imprimimos: sólo tiene que
maquetar e imprimir, sin JavaScript (CSP `script-src 'none'`, ver `render()`
para por qué no es un flag de arranque) ni acceso a red que no pase por el
proxy validador de `_egress_guard` (también en `render()`).

La nota puede maquetarse con un "tema" (`themes.py`): una plantilla HTML+CSS
escrita a mano que envuelve el contenido —cabecera con logo, portada, pie,
colores de empresa—. La plantilla se rellena y se sanea con el mismo
`sanitize_html` que el cuerpo de la nota: aunque la escriba el dueño de la
bóveda, aquí dentro un `file://` seguiría siendo lectura de ficheros del
servidor.
"""
import glob
import http.client
import http.server
import ipaddress
import os
import re
import shutil
import socket
import socketserver
import subprocess
import tempfile
import threading
from html import escape as html_escape
from html.parser import HTMLParser
from urllib.parse import urlsplit

from django.conf import settings

from . import themes


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
# (http/https/mailto/data:image) o fragmentos (#ancla). Nada de rutas relativas
# ni absolutas: el documento se carga con `file://`, así que cualquier valor sin
# esquema (`/etc/passwd`, `../../etc/passwd`, `secreto.png`) resuelve ahí mismo
# como lectura de fichero local — el cliente ya manda las imágenes como
# `data:` URI, no hay caso de uso legítimo para permitirlas aquí.
_URI_ATTRS = {"src", "href", "xlink:href", "action", "formaction"}
_SAFE_URI_RE = re.compile(r"^(https?:|mailto:|data:image/|#)", re.IGNORECASE)

# `srcset` es otro atributo de tipo URI en <img>, pero no es una URI suelta
# como `src`: es una lista "url descriptor, url descriptor, ..." (p.ej.
# `file:///etc/passwd 1x`), así que _URI_ATTRS/_SAFE_URI_RE no lo cubrían y
# Chromium resolvía el candidato `file://` igual que si hubiera sobrevivido
# en `src` — mismo hueco de lectura de fichero local, atributo distinto. Se
# valida cada candidato por separado y sólo sobreviven los que ya pasarían
# el chequeo de `src`/`href`. Sólo se separa en la coma seguida de espacio:
# una `data:` URI (el caso legítimo, imágenes ya embebidas por el cliente)
# lleva una coma interna sin espacio detrás (`data:image/png;base64,AAAA`)
# que no debe partir el candidato.
_SRCSET_SPLIT_RE = re.compile(r",\s+")

# url(...) en CSS (background-image, @import, @font-face src, cursor,
# content, list-style-image...) es otra vía hacia el mismo recurso que
# src/href, así que se valida con las mismas reglas — tanto si aparece en un
# atributo `style="..."` como dentro del texto de una etiqueta <style>.
# `@import "http://..."` sin `url()` es la otra sintaxis válida de @import.
_CSS_URL_RE = re.compile(r"""url\(\s*(['"]?)(.*?)\1\s*\)""", re.IGNORECASE)
_CSS_IMPORT_STR_RE = re.compile(r"""@import\s+(['"])(.*?)\1""", re.IGNORECASE)


_DNS_TIMEOUT_S = 3


def _resolve_host(hostname: str):
    """`getaddrinfo(hostname, None)` acotado por tiempo, o `None` si falla/tarda.

    `socket.getaddrinfo` no acepta un timeout — con DNS lento o un host que no
    responde puede colgarse decenas de segundos (confirmado: una nota con un
    `<a href="https://...">` normal tardó 30s en sanearse en un entorno con DNS
    inalcanzable), bloqueando el worker que exporta el PDF exactamente igual
    que el ReDoS del find/replace de la API. Se resuelve en un hilo aparte con
    `join(timeout)`; si no vuelve a tiempo, se trata como inseguro (igual que
    ya se hacía con `socket.gaierror`) y el hilo colgado se abandona — no hay
    forma de matar una llamada de red bloqueante desde fuera, pero tampoco
    consume CPU mientras espera, así que abandonarlo es inofensivo.
    """
    result = []

    def worker():
        try:
            result.append(socket.getaddrinfo(hostname, None))
        except socket.gaierror:
            pass

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join(_DNS_TIMEOUT_S)
    return result[0] if result else None


def _is_safe_http_host(hostname: str) -> bool:
    """Descarta hosts loopback/privados/link-local (incluye el endpoint de
    metadata de nube 169.254.169.254) para esquemas http(s).

    Defensa en profundidad, NO la barrera real: esto resuelve y valida la URL
    UNA VEZ, aquí en Python, antes de que el HTML se escriba a disco. Chromium
    hace su propia resolución DNS y su propia conexión, en un proceso aparte,
    segundos después — un host público que redirija a una dirección interna,
    o un dominio con TTL bajo que cambie de IP entre este chequeo y esa
    petición, pasan de largo sin que este código vuelva a mirarlos. La
    barrera real es el proxy validador de `_start_egress_guard()` (usado en
    `render()`), que obliga a Chromium a pasar por él y valida el destino de
    CADA conexión que abre, incluidas las de una redirección o un rebinding
    de DNS — `--host-resolver-rules` no basta, ver el comentario de más abajo
    junto a `_validated_target()`. Resuelve el host (soporta también IPs en
    hex/octal/decimal, que `ipaddress` por sí solo no reconoce pero el
    resolver del sistema sí normaliza) y rechaza si el fallo de DNS o
    cualquier IP resuelta cae en un rango no público.
    """
    try:
        candidates = [ipaddress.ip_address(hostname)]
    except ValueError:
        infos = _resolve_host(hostname)
        if infos is None:
            return False
        candidates = [ipaddress.ip_address(info[4][0]) for info in infos]
    return not any(
        ip.is_private or ip.is_loopback or ip.is_link_local
        or ip.is_multicast or ip.is_reserved or ip.is_unspecified
        for ip in candidates
    )


def _is_safe_uri(value: str) -> bool:
    value = value.strip()
    if not _SAFE_URI_RE.match(value):
        return False
    split = urlsplit(value)
    if split.scheme.lower() in ("http", "https"):
        return bool(split.hostname) and _is_safe_http_host(split.hostname)
    return True


# ── Proxy validador de salida para el Chromium que imprime ──────────────────
#
# `_is_safe_http_host()` de arriba resuelve y valida la URL UNA VEZ, en
# Python, antes de escribir el HTML a disco. Chromium hace su PROPIA
# resolución DNS y su PROPIA conexión, en un proceso aparte, segundos después
# — así que ese chequeo no ve ni redirecciones (un host público que sanea
# bien puede responder con un 302 a 127.0.0.1/RFC1918/169.254.169.254) ni DNS
# rebinding (un dominio con TTL bajo que cambie de IP entre el chequeo y la
# petición real). Confirmado en vivo: con sólo el chequeo de arriba, un
# `<img src>` a un host público que redirige a un "servidor interno" en
# 127.0.0.1 hace que Chromium llegue a ese servidor interno igualmente, y su
# respuesta queda incrustada en el PDF.
#
# `--host-resolver-rules` NO basta como solución: sólo remapea resoluciones
# por NOMBRE, no intercepta conexiones a una IP ya literal (que es
# exactamente lo que hay en una `Location: http://127.0.0.1:.../` o en
# `169.254.169.254`) — confirmado también en vivo, con ese flag puesto el
# mismo PoC seguía llegando al servidor interno.
#
# La única forma de validar el destino REAL de cada conexión, incluidas las
# que Chromium abre por su cuenta al seguir una redirección, es obligarlo a
# pasar por un proxy que decida — no adivine — a qué IP se conecta cada
# petición. Este proxy corre en el mismo proceso, sólo mientras dura un
# `render()`, y por cada CONNECT (https) o GET (http) resuelve el host UNA
# vez y se conecta a esa IP concreta (nunca vuelve a resolver el hostname),
# así que tampoco queda margen para DNS rebinding aquí dentro.
def _validated_target(host: str, port: int):
    """IP pública validada para conectar a `host:port`, o `None` si no es segura.

    Resuelve una única vez: el llamante debe conectar a la IP que devuelve,
    no volver a resolver `host` — ver el comentario de más arriba.
    """
    try:
        candidates = [ipaddress.ip_address(host)]
    except ValueError:
        infos = _resolve_host(host)
        if infos is None:
            return None
        candidates = [ipaddress.ip_address(info[4][0]) for info in infos]
    for ip in candidates:
        if not (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_multicast or ip.is_reserved or ip.is_unspecified):
            return str(ip)
    return None


class _EgressGuardHandler(http.server.BaseHTTPRequestHandler):
    """Proxy HTTP/HTTPS mínimo: sólo dejar pasar destinos públicos.

    Sin caché de "ya validé este host": cada petición —incluida la que
    Chromium reissues al seguir una redirección o al reconectar tras un
    rebinding de DNS— pasa por `_validated_target()` desde cero.
    """

    protocol_version = "HTTP/1.1"
    timeout = 15

    def log_message(self, *a):
        pass  # Corre en cada export a PDF: silencioso, no es tráfico de la app.

    def do_CONNECT(self):
        host, _, port_s = self.path.partition(":")
        ip = _validated_target(host, int(port_s or 443))
        if ip is None:
            self.send_error(403, "Destino no permitido")
            return
        try:
            upstream = socket.create_connection((ip, int(port_s or 443)), timeout=10)
        except OSError:
            self.send_error(502, "No se pudo conectar")
            return
        self.send_response(200, "Connection Established")
        self.end_headers()
        self._relay_both_ways(upstream)

    def do_GET(self):
        split = urlsplit(self.path)
        if not split.hostname:
            self.send_error(400)
            return
        port = split.port or 80
        ip = _validated_target(split.hostname, port)
        if ip is None:
            self.send_error(403, "Destino no permitido")
            return
        path = split.path or "/"
        if split.query:
            path += "?" + split.query
        try:
            conn = http.client.HTTPConnection(ip, port, timeout=10)
            headers = {k: v for k, v in self.headers.items()
                      if k.lower() not in ("proxy-connection", "connection", "host")}
            headers["Host"] = split.hostname if port == 80 else f"{split.hostname}:{port}"
            conn.request("GET", path, headers=headers)
            resp = conn.getresponse()
            body = resp.read()
        except OSError:
            self.send_error(502, "No se pudo conectar")
            return
        self.send_response(resp.status)
        for k, v in resp.getheaders():
            if k.lower() in ("connection", "transfer-encoding", "proxy-connection"):
                continue
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _relay_both_ways(self, upstream):
        client = self.connection
        client.settimeout(30)
        upstream.settimeout(30)

        def relay(src, dst):
            try:
                while True:
                    data = src.recv(65536)
                    if not data:
                        break
                    dst.sendall(data)
            except OSError:
                pass
            finally:
                try:
                    dst.shutdown(socket.SHUT_WR)
                except OSError:
                    pass

        t = threading.Thread(target=relay, args=(client, upstream), daemon=True)
        t.start()
        relay(upstream, client)
        t.join(2)
        upstream.close()


class _EgressGuardServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def _start_egress_guard():
    """Arranca el proxy validador en un puerto efímero de loopback.

    Devuelve `(servidor, puerto)`; el llamante debe llamar a
    `servidor.shutdown()` cuando termine el render.
    """
    srv = _EgressGuardServer(("127.0.0.1", 0), _EgressGuardHandler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    return srv, srv.server_address[1]


def _sanitize_srcset(value: str) -> str:
    safe = []
    for candidate in _SRCSET_SPLIT_RE.split(value.strip()):
        if not candidate:
            continue
        url = candidate.split(None, 1)[0]
        if _is_safe_uri(url):
            safe.append(candidate)
    return ", ".join(safe)


def _sanitize_css(value: str) -> str:
    value = _CSS_URL_RE.sub(lambda m: m.group(0) if _is_safe_uri(m.group(2)) else "", value)
    return _CSS_IMPORT_STR_RE.sub(lambda m: m.group(0) if _is_safe_uri(m.group(2)) else "", value)


def _escape_style_text(value: str) -> str:
    """Neutraliza `<`/`>` sin tocar comillas ni `&` — ver el docstring de
    `_NoteHTMLSanitizer` sobre por qué escapar de más rompe CSS legítima."""
    return value.replace("<", "&lt;").replace(">", "&gt;")


class _NoteHTMLSanitizer(HTMLParser):
    """Sanitiza el HTML de una nota antes de imprimirlo a PDF.

    Es una lista de bloqueo (no de permiso): el contenido renderizado incluye
    demasiadas etiquetas/atributos legítimos (KaTeX, Mermaid-SVG, highlight.js)
    como para enumerarlos todos sin arriesgarse a romper el renderizado. En su
    lugar neutralizamos los vectores concretos: handlers on*, iframes/objects/
    scripts, y cualquier URI que no sea http(s)/mailto/data:image/#ancla
    (bloquea en particular `file://` y cualquier ruta sin esquema, que con
    Chromium en modo headless podrían leer notas de otros usuarios o el .env
    del servidor). `<style>` sobrevive (Mermaid lo usa para el tema del SVG)
    pero su contenido pasa por el mismo saneado de CSS que el atributo
    `style=`: html.parser lo entrega tal cual por `handle_data` (modo CDATA).

    mXSS vía `<style>` (corregido): html.parser cree que todo lo que sigue a
    `<style>` es CSS literal hasta un `</style>` real — igual que Blink, EXCEPTO
    dentro de un punto de integración de texto MathML (`<math><mtext><mglyph>`).
    Ahí Blink sale del contenido foráneo en `</math>` y parsea lo que venga
    después como HTML normal, mientras que `html.parser` sigue creyendo que
    sigue "dentro" del `<style>` y entrega ese HTML tal cual por `handle_data`
    (`<img onerror=...>` intacto, sin pasar por `_clean_attrs`). Por eso el
    texto de `<style>` no basta con sanearlo como CSS: hay que escaparlo como
    HTML también, para que ningún byte que salga de aquí pueda interpretarse
    como una etiqueta nueva pase lo que pase con cómo Blink decida trocear el
    documento alrededor. `_sanitize_css` sigue aplicándose antes de escapar,
    para seguir recortando `url()`/`@import` de la CSS legítima.

    Ese escapado sólo toca `<`/`>` (ver `_escape_style_text`), no comillas ni
    `&`: un `<style>` real nunca decodifica entidades (es "raw text" en el
    HTML5 real, igual que `<script>`), así que escapar comillas rompía CSS
    legítima de Mermaid con valores entre comillas (`font-family:"trebuchet
    ms"` salía como `font-family:&quot;trebuchet ms&quot;`, letra literal
    para el motor de CSS). `<`/`>` sí son seguros de tocar siempre: son los
    únicos bytes que un tokenizador HTML usa para abrir una etiqueta nueva —
    su forma escapada nunca se re-interpreta como marcado, entre en el modo
    de parseo que entre.
    """

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.out = []
        self._skip_depth = 0
        self._in_style = False

    def _clean_attrs(self, attrs):
        cleaned = []
        for name, value in attrs:
            lname = name.lower()
            if lname.startswith("on"):
                continue
            if lname in _URI_ATTRS and value and not _is_safe_uri(value):
                continue
            if lname == "srcset" and value:
                value = _sanitize_srcset(value)
                if not value:
                    continue
            if lname == "style" and value:
                value = _sanitize_css(value)
            cleaned.append((_SVG_ATTR_CASE.get(lname, name), value))
        return cleaned

    def _emit_start(self, tag, attrs, self_closing):
        if tag in _UNSAFE_TAGS:
            # Autocerrado (`<script/>`): no hay contenido que saltar ni un
            # `handle_endtag` que vaya a llegar nunca a bajar el contador —
            # subirlo aquí lo dejaba atascado en 1 y silenciaba TODO el resto
            # del documento. Sin cuerpo que ocultar, basta con no emitir la
            # etiqueta (ya lo hace el `return` de más abajo).
            if not self_closing:
                self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "style" and not self_closing:
            self._in_style = True
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
        if tag == "style":
            self._in_style = False
        self.out.append(f"</{_SVG_TAG_CASE.get(tag, tag)}>")

    def handle_data(self, data):
        if not self._skip_depth:
            # Ver el docstring de la clase: escapar DESPUÉS de sanear como CSS,
            # nunca al revés — así `_sanitize_css` sigue viendo `url(...)`/
            # `@import` sin escapar (su regex los necesita tal cual) y lo que
            # sale de aquí no puede convertirse en una etiqueta nueva ni
            # aunque Blink decida que ya no está "dentro" de este `<style>`.
            self.out.append(_escape_style_text(_sanitize_css(data)) if self._in_style else data)

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


# ── Hoja y temas ─────────────────────────────────────────────────────────────

# Nota para quien escriba un tema (y para el `theme_starter.html`): Chromium no
# implementa las cajas de margen de `@page`, que serían el sitio de una
# cabecera repetida. Lo que sí repite en cada página es el `<thead>`/`<tfoot>`
# de una tabla, y el contenido refluye entre ellos sin solaparse. Sacar un
# `position:fixed` al margen con desplazamientos negativos (`top:-17mm`) NO
# vale: este Chromium lo coloca en el lado contrario de la página.

_MARGIN_MM = 14           # margen por defecto; un tema lo cambia con su @page


def _page_rule(landscape: bool, margin: str) -> str:
    """La regla `@page` completa: sin `size` explícito Chromium usa Letter."""
    size = "A4 landscape" if landscape else "A4"
    return f"@page{{size:{size};margin:{margin}}}"


# ── Impresión ────────────────────────────────────────────────────────────────

def _document(body_html: str, dark: bool = False, theme=None, title: str = "",
              landscape: bool = False, theme_html: str | None = None) -> str:
    """El HTML autónomo que se le da a imprimir a Chromium.

    Separado de `render` para poder comprobarlo en los tests sin arrancar un
    navegador: aquí es donde se decide la hoja (tamaño, clases, plantilla), y
    una equivocación no se ve hasta abrir el PDF.

    `theme_html` permite imprimir una plantilla que aún no está guardada (la
    vista previa del editor de temas) sin tener que crear un tema de mentira.
    """
    body = '<main class="markdown-body">' + body_html + '</main>'
    if theme is not None or theme_html is not None:
        template = theme_html if theme_html is not None else theme.html
        images = themes.image_map(theme) if theme is not None else {}
        # Rellenar ANTES de sanear: los marcadores no son URIs válidas, así que
        # un `src="{{ img:logo }}"` perdería el atributo entero si se saneara
        # primero. Y sanear DESPUÉS es obligatorio: la plantilla la escribe una
        # persona, pero el `file://` que se le cuele lo lee el servidor.
        body = sanitize_html(themes.fill(template, body, title, images))
    page_css = _page_rule(landscape, f"{_MARGIN_MM}mm")
    body_class = " ".join(c for c in ("print-dark" if dark else "",
                                      "landscape" if landscape else "") if c)
    # La clase va también en <html>: el fondo de `body` sólo pinta su caja, así
    # que en hoja oscura los márgenes de la página salían en blanco (un marco
    # blanco alrededor del texto, muy visible al abrir el PDF a página completa).
    return (
        '<!doctype html><html class="' + ("print-dark" if dark else "") +
        '"><head><meta charset="utf-8">'
        # El HTML ya viene renderizado: esta página nunca necesita ejecutar
        # nada. Es la red de seguridad real si algo se cuela pese a
        # `sanitize_html` — a diferencia de los flags de línea de comandos de
        # Chromium (ver `render`), una CSP en el propio documento no depende
        # de qué build de Chromium hay instalada ni rompe `--print-to-pdf`.
        '<meta http-equiv="Content-Security-Policy" content="script-src \'none\'">'
        '<style>'
        + _styles() + page_css +
        '</style></head><body class="' + body_class + '">'
        + body + '</body></html>'
    )


def render(body_html: str, dark: bool = False, theme=None, title: str = "",
           landscape: bool = False, theme_html: str | None = None) -> bytes:
    """Imprime a PDF el HTML (ya saneado) de una nota. Levanta `PdfError`.

    Con `theme` (un `PdfTheme`) la nota se maqueta dentro de la plantilla
    HTML+CSS de ese tema; sin él sale con la hoja de estilo base, clara o
    `dark`.

    En `landscape` la hoja no es la vertical estirada: el texto pasa a dos
    columnas (a lo ancho de un A4 apaisado una línea a página completa son
    ~26 cm, ilegibles) y los bloques que no caben en una columna —tablas,
    diagramas, código largo, imágenes grandes— los marca el cliente con
    `pdf-wide` para que ocupen el ancho completo. Ver `notes_print.css`.
    """
    doc = _document(body_html, dark, theme, title, landscape, theme_html)

    workdir = tempfile.mkdtemp(prefix="notepdf_")
    guard, guard_port = _start_egress_guard()
    try:
        in_html = os.path.join(workdir, "in.html")
        out_pdf = os.path.join(workdir, "out.pdf")
        with open(in_html, "w", encoding="utf-8") as fh:
            fh.write(doc)
        cmd = [
            CHROMIUM_BIN, "--headless", "--no-sandbox", "--disable-gpu",
            "--disable-dev-shm-usage", "--disable-crash-reporter", "--disable-breakpad",
            "--no-zygote", "--single-process",
            # La defensa real contra SSRF no es `_is_safe_http_host()`: ese
            # chequeo resuelve y valida la URL UNA VEZ, en Python, antes de
            # escribir el HTML a disco — pero Chromium hace su PROPIA
            # resolución DNS y su PROPIA conexión, segundos después, en un
            # proceso aparte. Una URL que apunte a un host público normal
            # (pasa el chequeo) pero responda con un 302 hacia
            # 127.0.0.1/RFC1918/169.254.169.254 se sirve igual: el saneador
            # nunca ve la URL de destino de la redirección, sólo la original.
            # Lo mismo con DNS rebinding (TTL bajo, la resolución cambia entre
            # el chequeo y la petición real). Confirmado en vivo: un
            # redirector en una IP pública hace que Chromium llegue igual a
            # un "servidor interno", con su respuesta incrustada en el PDF.
            #
            # `--host-resolver-rules=MAP * 0.0.0.0` NO sirve para esto: sólo
            # remapea resoluciones por NOMBRE, y una redirección a una IP ya
            # literal (127.0.0.1, 169.254.169.254...) no pasa por el
            # resolver — confirmado también en vivo, con ese flag puesto el
            # mismo PoC seguía llegando al servidor interno.
            #
            # `_start_egress_guard()` (arriba, en el módulo) es la barrera
            # real: un proxy que corre en este mismo proceso y por el que se
            # obliga a pasar TODA la red de Chromium, incluida la que abre
            # por su cuenta al seguir una redirección. Cada CONNECT/GET se
            # valida contra el destino de verdad, resuelto una única vez.
            # `<-loopback>` en la lista de exclusiones es necesario porque
            # Chromium, por defecto, NO manda a un proxy configurado las
            # peticiones a localhost/127.0.0.1 — justo el destino que hay que
            # poder interceptar aquí.
            f"--proxy-server=127.0.0.1:{guard_port}",
            "--proxy-bypass-list=<-loopback>",
            # El cliente legítimo (`prepareExportHtml` en notes.js) ya
            # incrusta todas las imágenes como `data:` URI antes de mandar el
            # HTML, así que Chromium no necesita red para ningún caso de uso
            # real — el proxy de arriba sólo entra en juego si algo se cuela
            # pese al saneado.
            #
            # Ya no hace falta `--allow-file-access-from-files`: sólo servía
            # para que el documento accediera a OTROS ficheros locales aparte
            # de sí mismo, y no hay ningún caso de uso legítimo para eso (las
            # imágenes de nota y de tema llegan como `data:` URI, nunca como
            # ruta). Era, además, la mitad que convertía el bypass mXSS
            # corregido en 17a9719 en lectura de fichero en vez de sólo XSS.
            #
            # El HTML ya viene renderizado, Chromium sólo maqueta e imprime.
            #
            # OJO: aquí NO va ningún flag de línea de comandos para apagar
            # JavaScript. `--disable-javascript` (el switch de content-settings)
            # fue retirado de Chromium hace años — un flag que Chromium no
            # reconoce se ignora en silencio, así que este comentario mentía:
            # el JS corría con normalidad (verificado). El reemplazo obvio,
            # `--blink-settings=scriptEnabled=false`, SÍ apaga el motor de
            # scripts, pero en el `chrome-headless-shell` que de verdad se usa
            # aquí (ver `_resolve_chromium`) también rompe `--print-to-pdf` por
            # completo: con ese flag Chromium termina con código 0 pero nunca
            # llega a escribir el PDF (verificado, build 1223). La defensa real
            # ahora es la CSP `script-src 'none'` que `_document()` mete en el
            # propio HTML: no depende de qué build de Chromium hay instalada,
            # y confirmado con el DevTools log que SÍ bloquea el `onerror` sin
            # romper la impresión.
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
        guard.shutdown()
        shutil.rmtree(workdir, ignore_errors=True)
