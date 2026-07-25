"""Decoradores de permiso por rol.

Un único punto donde se decide quién puede escribir y quién puede administrar,
para que añadir una vista nueva sea recordar un decorador y no reimplementar la
regla. La comprobación es SIEMPRE de servidor: el frontend esconde los botones
que no tocan, pero eso es cosmética, no seguridad.
"""
import functools

from django.http import JsonResponse
from django.shortcuts import redirect


def _deny(request, msg: str, status: int):
    """JSON para las APIs, redirección a la raíz para las vistas de página."""
    if request.path.startswith("/api/") or request.headers.get(
            "X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"error": msg}, status=status)
    return redirect("/")


def require_write(view):
    """Rechaza a los accesos de sólo lectura."""
    @functools.wraps(view)
    def wrapper(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated or not user.can_write:
            return _deny(request, "Tu acceso es de sólo lectura", 403)
        return view(request, *args, **kwargs)
    return wrapper


def require_owner(view):
    """Restringe a la cuenta propietaria (gestión de accesos y claves de API)."""
    @functools.wraps(view)
    def wrapper(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated or not user.is_owner:
            return _deny(request, "Sólo el propietario puede hacer esto", 403)
        return view(request, *args, **kwargs)
    return wrapper
