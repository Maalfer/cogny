"""URL routing principal — cogny (vault de notas Markdown)."""
from django.urls import include, path

from apps.core import views as core_views
from apps.notes import views as notes_views


urlpatterns = [
    # Página raíz: el vault (autenticado) o el login (anónimo).
    path("", core_views.root, name="root"),

    # Cuentas (login, perfil, ajustes).
    path("", include("apps.accounts.urls")),

    # Nota compartida públicamente (sin login; contraseña opcional por nota).
    path("s/<str:token>/", notes_views.shared_note_view, name="shared_note"),
    path("s/<str:token>/asset", notes_views.shared_note_asset, name="shared_note_asset"),

    # APIs JSON internas (sesión + CSRF) — las consume el frontend.
    path("api/notes/", include("apps.notes.api_urls")),

    # API pública v1 (clave de API) + Swagger en /api/docs/.
    path("api/", include("apps.api.urls")),

    # Service worker + manifest a nivel raíz (necesario para PWA scope).
    path("sw.js", core_views.service_worker, name="sw"),
    path("manifest.json", core_views.manifest, name="manifest"),
]
