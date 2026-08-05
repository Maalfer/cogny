"""URL routing principal — cogny (vault de notas Markdown)."""
from django.urls import include, path

from apps.core import views as core_views
from apps.notes import pdf_headless, views as notes_views


urlpatterns = [
    # Página raíz: el vault (autenticado) o el login (anónimo).
    path("", core_views.root, name="root"),

    # Login de un solo uso para el Chromium interno de exportación a PDF vía
    # API (ver `apps.notes.pdf_headless`) — sólo responde a peticiones desde
    # loopback, nunca expuesto por nginx hacia fuera.
    path("internal/pdf-headless/<str:token>/", pdf_headless.headless_login,
         name="pdf_headless_login"),

    # Cuentas (login, perfil, ajustes).
    path("", include("apps.accounts.urls")),

    # Nota compartida públicamente (sin login; contraseña opcional por nota).
    path("s/<str:token>/", notes_views.shared_note_view, name="shared_note"),
    path("s/<str:token>/asset", notes_views.shared_note_asset, name="shared_note_asset"),

    # Bóveda pública de sólo lectura (sin login; filtrada por dominio de origen).
    path("", include("apps.knowledge.urls")),

    # APIs JSON internas (sesión + CSRF) — las consume el frontend.
    path("api/notes/", include("apps.notes.api_urls")),
    path("api/knowledge/", include("apps.knowledge.api_urls")),

    # API pública v1 (clave de API) + Swagger en /api/docs/.
    path("api/", include("apps.api.urls")),

    # Service worker + manifest a nivel raíz (necesario para PWA scope).
    path("sw.js", core_views.service_worker, name="sw"),
    path("manifest.json", core_views.manifest, name="manifest"),
]
