"""Variables globales para todas las plantillas."""
from django.conf import settings


def global_context(request):
    user = getattr(request, "user", None)
    return {
        "ASSET_VERSION": getattr(settings, "ASSET_VERSION", "v1"),
        "APP_VERSION": getattr(settings, "VERSION", "0.0.0"),
        "bh_theme": getattr(request, "bh_theme", "dark"),
        # Aliases convenientes en las plantillas (acceso directo sin request.user).
        "username": user.username if user and user.is_authenticated else "",
        "user_id": user.id if user and user.is_authenticated else None,
        # Rol del acceso en curso: la plantilla esconde lo que no toca (el
        # permiso de verdad lo aplican los decoradores del servidor).
        "user_role": user.role if user and user.is_authenticated else "",
        "can_write": bool(user and user.is_authenticated and user.can_write),
        "is_owner": bool(user and user.is_authenticated and user.is_owner),
        # Host DNS-only para subidas grandes (import de bóvedas > 100 MB).
        "UPLOAD_HOST": getattr(settings, "UPLOAD_HOST", ""),
    }
