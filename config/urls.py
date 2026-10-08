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
    # `save` y el API de la nota/adjuntos (`note`, `assets`) sólo responden si
    # el enlace se creó como editable (`can_write`) — el API está pensado para
    # dárselo a una IA que gestione la nota por HTTP sin sesión.
    path("s/<str:token>/", notes_views.shared_note_view, name="shared_note"),
    path("s/<str:token>/asset", notes_views.shared_note_asset, name="shared_note_asset"),
    path("s/<str:token>/images.zip", notes_views.shared_note_images_zip, name="shared_note_images_zip"),
    path("s/<str:token>/save", notes_views.shared_note_save, name="shared_note_save"),
    path("s/<str:token>/note", notes_views.shared_note_note, name="shared_note_note"),
    path("s/<str:token>/assets", notes_views.shared_note_assets, name="shared_note_assets"),
    path("s/<str:token>/assets/<str:name>", notes_views.shared_note_asset_detail,
         name="shared_note_asset_detail"),

    # Bóveda pública de sólo lectura (sin login; filtrada por dominio de origen).
    path("", include("apps.knowledge.urls")),

    # Pizarra: galería + lienzo tipo Excalidraw (con sesión).
    path("", include("apps.whiteboard.urls")),

    # APIs JSON internas (sesión + CSRF) — las consume el frontend.
    path("api/notes/", include("apps.notes.api_urls")),
    path("api/knowledge/", include("apps.knowledge.api_urls")),
    path("api/pizarra/", include("apps.whiteboard.api_urls")),

    # Service worker + manifest a nivel raíz (necesario para PWA scope).
    path("sw.js", core_views.service_worker, name="sw"),
    path("manifest.json", core_views.manifest, name="manifest"),
]
