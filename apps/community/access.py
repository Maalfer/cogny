"""Quién puede entrar a `/comunidad` y cómo se le recuerda.

Dos formas de entrar, sin filtro de dominio (a diferencia de `apps.knowledge`,
aquí no hay lectura pública general: la única puerta es tener el enlace):

    1. Sesión del propietario (`request.user.is_owner`) — entra directo, sin
       enlace. Es el acceso que usa el icono de la cabecera.
    2. Un `CommunityLink` sin revocar, canjeado en `/comunidad/enlace/<uuid>/`.
       El permiso se firma en una cookie para no tener que llevar el UUID en
       cada URL; revocar el enlace invalida también la cookie ya emitida (ver
       `read_grant`), igual que hace `apps.knowledge`.

Quien entra por cualquiera de las dos vías tiene el MISMO acceso: lectura y
escritura completas sobre la bóveda comunitaria. No hay aquí distinción de
roles ni de "sólo lectura" — quien no deba escribir, simplemente no tiene el
enlace.
"""
import functools

from django.conf import settings
from django.core import signing
from django.db.models import F
from django.http import Http404, JsonResponse
from django.utils import timezone

from .models import CommunityLink

COOKIE_NAME = "cogny_comunidad"
SIGNING_SALT = "cogny.community.grant"
COOKIE_MAX_AGE = 3650 * 86400  # 10 años: un enlace de amigos no debe caducar solo


def _owner_session(request) -> bool:
    user = request.user
    return bool(user.is_authenticated and user.is_owner)


def read_grant(request):
    """El `CommunityLink` de la cookie si sigue sin revocar, o `None`."""
    raw = request.COOKIES.get(COOKIE_NAME)
    if not raw:
        return None
    try:
        data = signing.loads(raw, salt=SIGNING_SALT, max_age=COOKIE_MAX_AGE)
    except signing.BadSignature:
        return None
    if not isinstance(data, dict) or not data.get("t"):
        return None
    # Revocar un enlace tiene que echar también a quien ya entró con él; si no,
    # revocarlo no serviría de nada hasta que el navegador borrase la cookie.
    return CommunityLink.objects.filter(token=data["t"], revoked=False).first()


def set_grant(response, link: CommunityLink):
    response.set_cookie(
        COOKIE_NAME,
        signing.dumps({"t": str(link.token)}, salt=SIGNING_SALT),
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="Lax",
        secure=settings.SESSION_COOKIE_SECURE,
    )
    return response


def enter_with_link(token):
    """Canjea un enlace: `CommunityLink` válido, o levanta `Http404`."""
    link = CommunityLink.objects.filter(token=token, revoked=False).first()
    if not link:
        raise Http404
    # F("visits") + 1, no link.visits + 1: dos canjes casi simultáneos (dos
    # pestañas, o prefetch del enlace + navegación real) leerían el mismo
    # `link.visits` en Python y una de las dos escrituras se perdería.
    # F() hace el incremento en el propio UPDATE de la base de datos.
    CommunityLink.objects.filter(pk=link.pk).update(
        last_used_at=timezone.now(), visits=F("visits") + 1)
    return link


def check(request):
    """`True` si la visita puede entrar (sesión del dueño o enlace válido)."""
    return _owner_session(request) or read_grant(request) is not None


def community_view(view):
    """Vista de página de `/comunidad`: 404 si no hay sesión ni enlace válido."""
    @functools.wraps(view)
    def wrapper(request, *args, **kwargs):
        if not check(request):
            raise Http404
        return view(request, *args, **kwargs)
    return wrapper


def community_api(view):
    """Igual, pero para la API JSON del vault comunitario: 403 en vez de 404."""
    @functools.wraps(view)
    def wrapper(request, *args, **kwargs):
        if not check(request):
            return JsonResponse({"error": "Acceso no permitido"}, status=403)
        return view(request, *args, **kwargs)
    return wrapper
