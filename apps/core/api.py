"""Utilidades compartidas por las dos capas HTTP (web con sesión y API v1).

    from apps.core.api import error_response as _err
    from apps.core.api import json_body

Aquí viven también los tres coercionadores de tipos (`as_int`, `as_text`,
`as_optional_text`). El cuerpo JSON lo escribe el cliente, así que un número
donde se espera texto reventaría el `.strip()` de turno con un 500: en vez de
repetir la comprobación en cada vista —y que se olvide en alguna—, la API v1 y
los endpoints de sesión usan estos mismos.
"""
import functools
import json

from django.http import JsonResponse


def error_response(msg: str, status: int = 400, **extra) -> JsonResponse:
    """JsonResponse uniforme `{"error": msg}` con el status indicado."""
    return JsonResponse({"error": msg, **extra}, status=status)


def json_body(view):
    """Deja el cuerpo JSON de la petición en `request.data` (un dict).

    Un cuerpo vacío es `{}`; uno malformado corta con un 400 en vez de dejar que
    la vista se queje de un campo que "falta". Antes cada vista repetía este
    `try/except json.JSONDecodeError` a mano, y bastaba olvidarlo una vez para
    convertir un cliente torpe en un 500.
    """
    @functools.wraps(view)
    def wrapper(request, *args, **kwargs):
        try:
            data = json.loads(request.body or "{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            return error_response("JSON inválido")
        request.data = data if isinstance(data, dict) else {}
        return view(request, *args, **kwargs)
    return wrapper


def as_int(value):
    """`int`, o `None` si no lo es.

    Un id no numérico en un `filter(pk=…)` levanta `ValueError` y acaba en un
    500; con `None` el filtro no casa y sale el 404 que corresponde.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def as_text(value, default: str = "") -> str:
    """El valor sólo si es texto; si no, `default`."""
    return value if isinstance(value, str) else default


def as_optional_text(value, default):
    """El valor tal cual vino (recortado si es texto), o `default` si no vino.

    A diferencia de `as_text`, NO normaliza los tipos raros: los deja pasar para
    que el validador de destino los rechace con un 400. Es lo que quieres en un
    campo como el rol, donde degradar en silencio al valor por defecto le daría
    al usuario un permiso distinto del que pidió sin decírselo.
    """
    if value is None:
        return default
    return value.strip() if isinstance(value, str) else value
