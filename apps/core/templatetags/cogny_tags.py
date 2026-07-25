"""Filtros custom para plantillas."""
from django import template
from django.conf import settings

register = template.Library()


@register.simple_tag(takes_context=True)
def avatar_url(context, user=None):
    """`/static/avatars/avatar-<id>.jpg?v=<mtime>` si existe; "" si no.

    Sin argumento devuelve el avatar de quien está en sesión; con un usuario
    concreto, el de ese usuario (lista de accesos del perfil).

    El cache-buster por mtime garantiza que al actualizar el avatar el browser
    refresque la imagen aunque nginx la sirva con cache largo.
    """
    if user is None:
        request = context.get("request")
        user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return ""
    name = f"avatar-{user.pk}.jpg"
    try:
        mtime = int((settings.AVATARS_ROOT / name).stat().st_mtime)
    except OSError:
        return ""
    return f"/static/avatars/{name}?v={mtime}"
