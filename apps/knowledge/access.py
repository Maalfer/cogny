"""Quién puede leer `/conocimiento`, y cómo se le recuerda.

AVISO, y va en el código a propósito para que no se olvide: el filtro por
dominio de origen se apoya en la cabecera `Referer`, que **la manda el cliente**.
Un `curl -H "Referer: https://elrincondelhacker.es/"` entra igual. Esto sirve
para que el enlace no circule fuera de la comunidad —que es para lo que está—,
NO como control de acceso. Lo que hay detrás es de sólo lectura precisamente
porque la puerta es blanda.

Flujo de una visita:

    1. ¿la bóveda pública está activada?     no → 404 (ni existe)
    2. ¿trae ya un permiso firmado en cookie? sí → pasa
    3. ¿llega desde un dominio permitido?     sí → pasa y se le firma el permiso
    4. si no                                      → 403 con explicación

El paso 2 existe porque el `Referer` sólo viaja en el clic que trae al visitante
desde fuera: al navegar por la propia bóveda, recargar o volver por un marcador
ya no hay dominio de origen que mirar, y sin la cookie se quedaría fuera a la
segunda página.
"""
import functools

from django.conf import settings
from django.core import signing
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.http import urlencode

from .models import MasterLink, PublicVault

COOKIE_NAME = "cogny_conocimiento"
SIGNING_SALT = "cogny.knowledge.grant"

# Cómo entró quien tiene el permiso, sólo para poder explicárselo y para que un
# enlace maestro revocado no siga valiendo por la cookie que dejó.
GRANT_DOMAIN = "d"
GRANT_MASTER = "m"


# ── Dominios ─────────────────────────────────────────────────────────────────

def host_matches(host: str, pattern: str) -> bool:
    """¿`host` encaja con `pattern`?

    `*.dominio.tld` cubre el dominio **y** todos sus subdominios: quien escribe
    `*.elrincondelhacker.es` espera que valga también el enlace puesto en la
    portada, no sólo en `www.`.
    """
    if not host or not pattern:
        return False
    if pattern.startswith("*."):
        bare = pattern[2:]
        return host == bare or host.endswith("." + bare)
    return host == pattern


def request_origin_host(request) -> str:
    """Dominio del que viene la visita, según el navegador.

    Se mira `Referer` y, si no está, `Origin`: en una navegación normal el que
    llega es `Referer`, pero algunas políticas lo recortan a sólo el origen y
    ciertos clientes mandan `Origin` en su lugar.
    """
    from .models import normalize_domain
    for header in ("Referer", "Origin"):
        value = request.headers.get(header, "")
        if value and value.lower() != "null":
            host = normalize_domain(value)
            if host:
                return host
    return ""


def domain_allowed(cfg: PublicVault, host: str) -> bool:
    patterns = cfg.domain_list()
    if not patterns:
        # Sin lista, la bóveda queda abierta a cualquiera que tenga el enlace.
        # Es la lectura natural de "no he restringido nada", y la interfaz de
        # Ajustes lo dice con todas las letras.
        return True
    return any(host_matches(host, p) for p in patterns)


# ── Permiso firmado (cookie) ─────────────────────────────────────────────────

def read_grant(request) -> dict:
    """El permiso de la cookie si es válido y sigue vigente, o `{}`."""
    raw = request.COOKIES.get(COOKIE_NAME)
    if not raw:
        return {}
    cfg = PublicVault.get()
    try:
        data = signing.loads(raw, salt=SIGNING_SALT,
                             max_age=max(1, cfg.grant_days) * 86400)
    except signing.BadSignature:
        return {}
    if not isinstance(data, dict):
        return {}
    if data.get("k") == GRANT_MASTER:
        # Revocar un enlace maestro tiene que echar también a quien ya entró
        # con él; si no, revocarlo no serviría de nada hasta que caduque.
        if not MasterLink.objects.filter(token=data.get("m"), revoked=False).exists():
            return {}
    return data


def set_grant(response, cfg: PublicVault, kind: str, master_token=None):
    """Firma el permiso en una cookie para las visitas siguientes."""
    payload = {"k": kind}
    if master_token:
        payload["m"] = str(master_token)
    response.set_cookie(
        COOKIE_NAME,
        signing.dumps(payload, salt=SIGNING_SALT),
        max_age=max(1, cfg.grant_days) * 86400,
        httponly=True,
        # Lax y no Strict: con Strict la cookie NO viajaría en la navegación que
        # llega desde otro sitio, que es justo el caso que hay que soportar.
        samesite="Lax",
        secure=settings.SESSION_COOKIE_SECURE,
    )
    return response


def clear_grant(response):
    response.delete_cookie(COOKIE_NAME)
    return response


# ── Puerta ───────────────────────────────────────────────────────────────────

class Denied(Exception):
    """Visita rechazada: no venía de un dominio permitido."""

    def __init__(self, host: str):
        super().__init__(host)
        self.host = host


def check(request):
    """`(cfg, grant, nuevo_permiso)` o levanta `Http404` / `Denied`.

    `nuevo_permiso` es el tipo de permiso que hay que firmar en la respuesta
    (o `None` si ya venía con uno válido): quien llama es el que tiene la
    respuesta a mano para ponerle la cookie.
    """
    cfg = PublicVault.get()
    if not cfg.enabled:
        # 404 y no 403: si está apagada, la bóveda pública no existe. Un 403
        # confirmaría que la URL es la buena y que sólo falta el permiso.
        raise Http404

    grant = read_grant(request)
    if grant:
        return cfg, grant, None

    host = request_origin_host(request)
    if domain_allowed(cfg, host):
        return cfg, {"k": GRANT_DOMAIN}, GRANT_DOMAIN

    raise Denied(host)


def public_view(view):
    """Vista de página de la bóveda pública: 404 si está apagada, 403 si el
    dominio no vale, y permiso firmado en la respuesta si acaba de entrar."""
    @functools.wraps(view)
    def wrapper(request, *args, **kwargs):
        try:
            cfg, grant, fresh = check(request)
        except Denied as denied:
            return render(request, "knowledge/blocked.html",
                          {"origin_host": denied.host}, status=403)
        request.public_grant = grant
        response = view(request, *args, **kwargs)
        if fresh:
            set_grant(response, cfg, fresh)
        return response
    return wrapper


def public_api(view):
    """Igual, pero para los endpoints JSON del lector: sin página de bloqueo."""
    @functools.wraps(view)
    def wrapper(request, *args, **kwargs):
        try:
            cfg, grant, fresh = check(request)
        except Denied:
            return JsonResponse({"error": "Acceso no permitido desde este origen"},
                                status=403)
        request.public_grant = grant
        response = view(request, *args, **kwargs)
        if fresh:
            set_grant(response, cfg, fresh)
        return response
    return wrapper


def enter_with_master(request, token):
    """Canjea un enlace maestro. Devuelve `(cfg, link)` o levanta `Http404`."""
    cfg = PublicVault.get()
    if not cfg.enabled:
        raise Http404
    link = MasterLink.objects.filter(token=token, revoked=False).first()
    if not link:
        raise Http404
    MasterLink.objects.filter(pk=link.pk).update(
        last_used_at=timezone.now(), visits=link.visits + 1)
    return cfg, link


def reader_url(note_path: str = "") -> str:
    """URL del lector, opcionalmente abriendo una nota concreta."""
    if not note_path:
        return "/conocimiento/"
    return "/conocimiento/?" + urlencode({"n": note_path})
