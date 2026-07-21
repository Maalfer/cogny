"""Variables globales para todas las plantillas."""
from django.conf import settings


def global_context(request):
    user = getattr(request, "user", None)
    return {
        "ASSET_VERSION": getattr(settings, "ASSET_VERSION", "v1"),
        "bh_theme": getattr(request, "bh_theme", "dark"),
        # Aliases convenientes en las plantillas (acceso directo sin request.user).
        "username": user.username if user and user.is_authenticated else "",
        "user_id": user.id if user and user.is_authenticated else None,
        "user_role": getattr(user, "role", "user") if user and user.is_authenticated else "",
        # Host DNS-only para subidas grandes (import de bóvedas > 100 MB).
        "UPLOAD_HOST": getattr(settings, "UPLOAD_HOST", ""),
    }
