"""Quién puede leer `/conocimiento`, y cómo se le recuerda.

Única puerta de entrada: el enlace maestro (`MasterLink`, token UUID4
revocable). No hay filtro por dominio de origen ni por `Referer` — esa
cabecera la manda el cliente y no es un control de acceso real, así que se
quitó: quien no tiene un enlace maestro, no entra.

Flujo de una visita:

    1. ¿la bóveda pública está activada?      no → 404 (ni existe)
    2. ¿trae ya un permiso firmado en cookie?  sí → pasa
    3. si no                                       → 403

El permiso de la cookie sólo se firma al canjear un enlace maestro
(`enter_with_master`): es lo que permite navegar, recargar y volver por un
marcador sin tener que repetir el enlace en cada petición.
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

# Cómo entró quien tiene el permiso: hoy sólo existe esta vía, pero se guarda
# en la cookie para que un enlace maestro revocado eche también a quien ya
# había entrado con él (ver `read_grant`).
GRANT_MASTER = "m"


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
    """Visita rechazada: no trae un permiso válido (ni enlace maestro)."""


def check(request):
    """`(cfg, grant)` o levanta `Http404` / `Denied`."""
    cfg = PublicVault.get()
    if not cfg.enabled:
        # 404 y no 403: si está apagada, la bóveda pública no existe. Un 403
        # confirmaría que la URL es la buena y que sólo falta el permiso.
        raise Http404

    grant = read_grant(request)
    if grant:
        return cfg, grant

    raise Denied


def public_view(view):
    """Vista de página de la bóveda pública: 404 si está apagada, 403 si no
    hay permiso (sólo se consigue canjeando un enlace maestro)."""
    @functools.wraps(view)
    def wrapper(request, *args, **kwargs):
        try:
            cfg, grant = check(request)
        except Denied:
            return render(request, "knowledge/blocked.html", {}, status=403)
        request.public_grant = grant
        return view(request, *args, **kwargs)
    return wrapper


def public_api(view):
    """Igual, pero para los endpoints JSON del lector: sin página de bloqueo."""
    @functools.wraps(view)
    def wrapper(request, *args, **kwargs):
        try:
            cfg, grant = check(request)
        except Denied:
            return JsonResponse({"error": "Acceso no permitido"}, status=403)
        request.public_grant = grant
        return view(request, *args, **kwargs)
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
