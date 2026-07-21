"""Utilidades compartidas para las APIs JSON.

Cada app las importa con su alias habitual para no romper la legibilidad:

    from apps.core.api import error_response as _err
    from apps.core.api import parse_json_body as _parse_json
    from apps.core.api import safe_filename as _safe_name
"""
import json
import re

from django.http import JsonResponse


def error_response(msg: str, status: int = 400) -> JsonResponse:
    """JsonResponse uniforme `{"error": msg}` con el status indicado."""
    return JsonResponse({"error": msg}, status=status)


def parse_json_body(request, default=None):
    """Devuelve `dict` con el cuerpo JSON del request, o `default` (`{}`) si está vacío/malformado."""
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return default if default is not None else {}


_FILENAME_RE = re.compile(r"[\x00-\x1f/\\]+")


def safe_filename(name: str, max_length: int = 200) -> str:
    """Sanitiza un nombre de archivo: elimina chars de control y separadores.

    Devuelve `"Sin nombre"` si el resultado queda vacío.
    """
    name = (name or "").strip()
    name = _FILENAME_RE.sub("", name)
    return name[:max_length] or "Sin nombre"
