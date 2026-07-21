"""Filtros custom para plantillas."""
from django import template
from django.conf import settings

register = template.Library()


@register.filter
def avatar_url(user_id):
    """Devuelve `/static/avatars/<id>.jpg?v=<mtime>` si existe el avatar; "" si no.

    El cache-buster por mtime garantiza que al actualizar el avatar el browser
    refresque la imagen aunque nginx la sirva con cache largo.
    """
    if not user_id:
        return ""
    try:
        path = settings.AVATARS_ROOT / f"{int(user_id)}.jpg"
    except (TypeError, ValueError):
        return ""
    try:
        mtime = int(path.stat().st_mtime)
    except OSError:
        return ""
    return f"/static/avatars/{int(user_id)}.jpg?v={mtime}"
