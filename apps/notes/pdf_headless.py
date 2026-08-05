"""Render de una nota a HTML "como la vería el navegador", para la API v1.

`pdf.py` imprime HTML que YA le llega renderizado (KaTeX/Mermaid/highlight.js
corren en el cliente — ver su docstring). La web cumple ese contrato porque
hay un navegador de verdad delante; una clave de API no lo tiene, así que
necesita que ALGUIEN haga ese render por ella antes de imprimir.

En vez de reimplementar marked/KaTeX/Mermaid/highlight.js en Python (y
arriesgarse a que diverja de lo que se ve en la web), este módulo hace que un
Chromium headless CON JavaScript navegue a la app real, con una sesión de un
solo uso, y deje que `notes.js` haga exactamente el mismo trabajo que hace al
exportar desde el editor (`runHeadlessPdfExport`, en notes.js).

La sincronización va por Playwright (Chromium vía CDP) escuchando un
`console.log`, no por `--virtual-time-budget` + `--dump-dom` ni por
`page.evaluate()`/`wait_for_function()`. Se probaron las dos y ninguna vale:
- `--dump-dom` con presupuesto de tiempo virtual volcaba el DOM antes de que
  terminara la cadena de `fetch()` encadenados de `postProcess`/`resolveEmbed`
  (comprobado: el mismo HTML se renderizaba bien en un navegador normal, pero
  el volcado lo pillaba a medias).
- `page.evaluate()`/`wait_for_function()` de Playwright compilan y corren
  código NUEVO dentro de la página para leer el resultado o comprobar la
  condición — y la CSP de la app (`script-src` sin `unsafe-eval`, ver
  `ContentSecurityPolicyMiddleware`) lo bloquea con un error de CSP
  (comprobado). Escuchar un `console.log` que ya hace código YA cargado y
  confiable (`runHeadlessPdfExport`, en notes.js) no ejecuta nada nuevo en la
  página, así que la CSP no lo toca.

Nada de esto toca el Chromium que IMPRIME (`pdf.render`): ese sigue con
`--disable-javascript`, sin sesión y sin red, exactamente igual que antes.
El HTML que sale de aquí pasa por el mismo `pdf.sanitize_html()` que ya
usaba la web antes de llegar a imprimirse — lo aplica el llamante (la vista
de la API), igual que `notes_pdf` hace con el HTML que manda el navegador.
El único riesgo NUEVO de verdad es que este Chromium sí ejecuta JavaScript
sobre HTML derivado del contenido de la nota (vía `marked` + `DOMPurify`,
las mismas librerías que ya se ejecutan hoy en el navegador del propio
dueño de la bóveda). Se apoya en dos defensas que la app YA tenía puestas
para el navegador normal y que aquí siguen aplicando intactas: el saneado
con DOMPurify de `renderMarkdown()` (notes.js) y la CSP con nonce por
petición (`ContentSecurityPolicyMiddleware`) — sin `unsafe-inline` en
`script-src`, así que un `<script>` que se colara pese al saneado no se
ejecutaría ni aquí ni en un navegador real.
"""
import logging
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import login
from django.core import signing
from django.http import Http404, HttpResponseRedirect
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from . import pdf

log = logging.getLogger(__name__)

_TOKEN_SALT = "notes.pdf_headless_render"

# El token vive lo justo para que el Chromium que acabamos de lanzar lo use una
# vez: nunca sale de este proceso (va directo a la URL que le pasamos), así que
# una ventana corta no molesta a nadie salvo a un atacante que lo intercepte.
# 30s da margen al arranque del propio Chromium (typ. 1-2s) sin ser generoso.
_TOKEN_MAX_AGE_S = 30

# La sesión que abre el login de un solo uso se cierra sola enseguida — no hay
# motivo para dejar viva una sesión completa (1 año, ver SESSION_COOKIE_AGE)
# por un render que dura segundos.
_SESSION_AGE_S = 60

# Sólo Chromium (lanzado por ESTE proceso, apuntando a INTERNAL_ORIGIN) puede
# llegar aquí: nginx nunca expone /internal/ hacia fuera, pero además de esa
# capa de red comprobamos la IP — defensa en profundidad si algún día cambia
# la topología de red delante de gunicorn.
_LOOPBACK_IPS = {"127.0.0.1", "::1"}


class HeadlessRenderError(Exception):
    """Fallo generando el HTML de la nota vía Chromium con JS."""


def _mint_token(user_id: int, note_path: str, landscape: bool) -> str:
    return signing.dumps({"u": user_id, "p": note_path, "l": bool(landscape)}, salt=_TOKEN_SALT)


def headless_login(request, token):
    """Login de un solo uso para el Chromium interno — nunca pensado para humanos.

    Firma corta y sólo-loopback: el token no autoriza nada por sí mismo salvo
    abrir sesión como el usuario que lo pidió, y sólo si llega desde el propio
    servidor dentro de los primeros `_TOKEN_MAX_AGE_S` segundos.
    """
    if request.META.get("REMOTE_ADDR") not in _LOOPBACK_IPS:
        raise Http404
    try:
        data = signing.loads(token, salt=_TOKEN_SALT, max_age=_TOKEN_MAX_AGE_S)
    except signing.BadSignature:
        raise Http404
    from apps.accounts.models import User

    user = User.objects.filter(pk=data.get("u"), is_active=True).first()
    if user is None:
        raise Http404
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    request.session.set_expiry(_SESSION_AGE_S)
    qs = urlencode({
        "open": data.get("p", ""),
        "headless_pdf": "1",
        "landscape": "1" if data.get("l") else "0",
    })
    return HttpResponseRedirect(f"/?{qs}")


# Flags mínimos para correr Chromium sin sandbox de kernel bajo www-data en el
# VPS — los mismos que ya usa `pdf.render()` para el Chromium que imprime,
# menos `--disable-javascript` (aquí es justo lo que necesitamos) y menos
# `--single-process`/`--no-zygote` (Playwright ya gestiona el ciclo de vida
# del proceso por su cuenta; forzar single-process le estorbaría).
_LAUNCH_ARGS = [
    "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
    "--disable-crash-reporter", "--disable-breakpad",
]

# Prefijo del console.log de `runHeadlessPdfExport` (notes.js): todo lo que
# venga después es el HTML final, tal cual.
_READY_PREFIX = "PDF_EXPORT_READY:"

# Tiempo máximo esperando ese mensaje. Cubre: cargar el árbol, abrir la nota,
# KaTeX/Mermaid, resolver embeds recursivos (hasta profundidad 3, cada uno una
# petición más) e incrustar imágenes como `data:` URI.
_READY_TIMEOUT_MS = 25_000


def render_note_to_html(user, note_path: str, landscape: bool = False) -> str:
    """HTML de `note_path` tal como lo renderiza la app (KaTeX/Mermaid/highlight.js
    ya ejecutados, imágenes ya embebidas como `data:` URI, columnas anchas ya
    marcadas si `landscape`). Sin sanear todavía — el llamante decide cuándo.

    Lanza `HeadlessRenderError` si Chromium no llega a la señal de fin a tiempo
    (nota no encontrada, JS con un error, o el render tardó más de lo previsto).
    """
    token = _mint_token(user.pk, note_path, landscape)
    url = f"{settings.INTERNAL_ORIGIN}/internal/pdf-headless/{token}/"
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                executable_path=pdf.CHROMIUM_BIN, headless=True, args=_LAUNCH_ARGS)
            try:
                page = browser.new_page()
                with page.expect_console_message(
                        lambda m: m.text.startswith(_READY_PREFIX),
                        timeout=_READY_TIMEOUT_MS) as msg_info:
                    page.goto(url, wait_until="load", timeout=_READY_TIMEOUT_MS)
                payload = msg_info.value.text[len(_READY_PREFIX):]
            finally:
                browser.close()
    except PlaywrightTimeoutError as exc:
        raise HeadlessRenderError("Tiempo agotado renderizando la nota") from exc
    except Exception as exc:
        # Deliberadamente amplio, no sólo `PlaywrightError`: si el propio driver
        # de Playwright no arranca (binario de Node ausente/roto — no el
        # Chromium, que ya se resuelve aparte en `pdf._resolve_chromium()`),
        # `sync_playwright().__enter__()` deja escapar la excepción original de
        # Python (típicamente `FileNotFoundError`) SIN envolverla en
        # `playwright.sync_api.Error`; sin este except quedaba sin capturar
        # aquí y acababa en el `except OSError` genérico de `api.auth.api_view`,
        # que sí mete `str(exc)` (una ruta de fichero del servidor) en la
        # respuesta JSON.
        #
        # Además: nunca interpolar `exc` en el mensaje que ve la API — Playwright
        # mete la URL navegada completa en el texto de sus excepciones de
        # conexión (a diferencia de las de timeout), y esa URL lleva el token
        # firmado de un solo uso. Un fallo de conexión (p.ej. INTERNAL_ORIGIN
        # mal configurado) filtraría ese token, con el que cualquiera con la
        # clave de API — aunque sea de sólo lectura — podría abrir una sesión
        # web completa como el dueño de la clave. Detalle sólo al log.
        log.warning("render_note_to_html: fallo de Chromium/Playwright: %s", exc)
        raise HeadlessRenderError("No se pudo renderizar la nota") from exc
    if not payload:
        raise HeadlessRenderError(
            "No se pudo renderizar la nota (¿existe la ruta indicada?)")
    return payload
