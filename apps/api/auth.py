"""Autenticación por clave de API para `/api/v1/`.

La API pública NO acepta la cookie de sesión: si lo hiciera, al ir exenta de
CSRF cualquier web podría hacer peticiones autenticadas desde el navegador del
usuario. Con clave obligatoria el vector desaparece — el navegador nunca añade
la cabecera `Authorization` por su cuenta.
"""
import functools
import json
from datetime import timedelta

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from apps.accounts.models import ApiKey
# Misma forma de error que la web (`{"error": …}`): una sola implementación.
from apps.core.api import error_response as json_error


def _extract_key(request) -> str:
    """`Authorization: Bearer <clave>`, `X-API-Key: <clave>` o `?api_key=`."""
    auth = request.headers.get("Authorization", "")
    if auth[:7].lower() == "bearer ":
        return auth[7:].strip()
    if auth[:8].lower() == "api-key ":
        return auth[8:].strip()
    header = request.headers.get("X-API-Key")  # `headers` ignora mayúsculas
    if header:
        return header.strip()
    # Último recurso para descargas directas desde el navegador (`<img src>`,
    # `wget`): cómodo, pero la clave acaba en los logs de nginx. Documentado.
    return (request.GET.get("api_key") or "").strip()


# Escribir `last_used_at` en cada petición serializaría escrituras en SQLite
# sin aportar nada: basta con la resolución de un minuto.
_LAST_USED_RESOLUTION = timedelta(minutes=1)


def api_view(methods=("GET",)):
    """Decorador de endpoint de la API v1.

    - Valida método y clave, y deja `request.api_key` / `request.user` listos.
    - Parsea el cuerpo JSON en `request.json`.
    - Aplica el permiso de sólo lectura por método: todo lo que no sea
      GET/HEAD se considera escritura. La regla funciona porque en esta API
      ningún GET modifica nada (exportar la bóveda lee; optimizar imágenes,
      que sí escribe, es POST).
    """
    allowed = {m.upper() for m in methods}
    if "GET" in allowed:
        allowed.add("HEAD")  # Django responde HEAD con el GET sin cuerpo.

    def decorator(fn):
        @csrf_exempt
        @functools.wraps(fn)
        def wrapper(request, *args, **kwargs):
            if request.method not in allowed:
                return json_error(
                    f"Método no permitido (usa {', '.join(sorted(allowed))})", 405)

            raw = _extract_key(request)
            if not raw:
                return json_error(
                    "Falta la clave de API. Envía la cabecera "
                    "'Authorization: Bearer cgny_...' o 'X-API-Key: cgny_...'.", 401)
            key = ApiKey.resolve(raw)
            if not key:
                return json_error("Clave de API inválida o revocada", 401)

            if request.method not in ("GET", "HEAD"):
                # El permiso efectivo es el menor de los dos: una clave no puede
                # dar más de lo que tiene la cuenta a la que pertenece.
                if key.read_only:
                    return json_error("Esta clave es de sólo lectura", 403)
                if not key.user.can_write:
                    return json_error("Tu acceso es de sólo lectura", 403)

            now = timezone.now()
            if not key.last_used_at or now - key.last_used_at > _LAST_USED_RESOLUTION:
                ApiKey.objects.filter(pk=key.pk).update(last_used_at=now)

            request.api_key = key
            request.user = key.user
            # Sólo se toca `request.body` si el cuerpo es JSON: leerlo en una
            # subida multipart lo cargaría entero en RAM (el import de una
            # bóveda puede pesar cientos de MB). En ese caso los parámetros
            # llegan por `request.POST`, que `body_or_query` ya consulta.
            ctype = (request.content_type or "").lower()
            if ctype.startswith("multipart/") or ctype.startswith("application/x-www-form-urlencoded"):
                request.json = {}
            else:
                raw_body = request.body
                if not raw_body.strip():
                    request.json = {}
                else:
                    try:
                        parsed = json.loads(raw_body)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        # Cuerpo presente pero ilegible: mejor decirlo que
                        # seguir con `{}` y quejarse de un campo que falta.
                        return json_error("El cuerpo no es JSON válido")
                    request.json = parsed if isinstance(parsed, dict) else {}

            try:
                return fn(request, *args, **kwargs)
            except OSError as exc:
                # Disco lleno, permisos, un fichero donde se esperaba una
                # carpeta… Sin esto Django devolvería su página HTML de error,
                # que un cliente de API no sabe leer.
                return json_error(f"Error de sistema de ficheros: {exc}", 500)

        return wrapper

    return decorator


def owner_only(fn):
    """Envoltorio para endpoints reservados a la cuenta propietaria."""
    @functools.wraps(fn)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_owner:
            return json_error("Sólo el propietario puede hacer esto", 403)
        return fn(request, *args, **kwargs)
    return wrapper


def body_or_query(request, name, default=None):
    """Lee un parámetro del cuerpo JSON, del querystring o de un POST de formulario."""
    if name in getattr(request, "json", {}):
        return request.json[name]
    if name in request.GET:
        return request.GET[name]
    if request.method == "POST" and name in request.POST:
        return request.POST[name]
    return default
