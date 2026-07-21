"""URL routing principal — cogny (vault de notas Markdown)."""
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponseRedirect
from django.views.generic import RedirectView

from apps.core import views as core_views
from apps.notes import views as notes_views


class _Redirect307(HttpResponseRedirect):
    """Redirect que conserva método HTTP y body (a diferencia del 302 default)."""
    status_code = 307


def _vault_to_notes(request, rest):
    qs = ("?" + request.META["QUERY_STRING"]) if request.META.get("QUERY_STRING") else ""
    return _Redirect307(f"/api/notes/{rest}{qs}")


urlpatterns = [
    # Página raíz: el vault (autenticado) o el login (anónimo).
    path("", core_views.root, name="root"),

    # Cuentas (login, registro, perfil, ajustes).
    path("", include("apps.accounts.urls")),

    # `home` es el destino histórico tras el login en varias vistas de accounts;
    # aquí no hay dashboard multi-app, así que apunta al vault.
    path("home/", RedirectView.as_view(url="/", permanent=False), name="home"),

    # Compat: el vault se movió a la raíz; /notes/ (marcadores, PWA vieja) redirige.
    path("notes/", RedirectView.as_view(url="/", permanent=True)),

    # Nota compartida públicamente (sin login; contraseña opcional por nota).
    path("s/<str:token>/", notes_views.shared_note_view, name="shared_note"),
    path("s/<str:token>/asset", notes_views.shared_note_asset, name="shared_note_asset"),

    # APIs JSON.
    path("api/notes/", include("apps.notes.api_urls")),
    # Alias retro-compatible: /api/vault/<x> → /api/notes/<x> con 307
    # (conserva método y body para los POSTs cacheados por el SW antiguo).
    re_path(r"^api/vault/(?P<rest>.*)$", _vault_to_notes),
    path("api/profile/", include("apps.accounts.profile_urls")),

    # Service worker + manifest a nivel raíz (necesario para PWA scope).
    path("sw.js", core_views.service_worker, name="sw"),
    path("manifest.json", core_views.manifest, name="manifest"),

]

# Media files: en desarrollo con el helper de debug; en producción directamente con
# django.views.static.serve (válido en VPS personal con bajo tráfico).
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    from django.views.static import serve as _static_serve
    urlpatterns += [
        re_path(r"^media/(?P<path>.*)$", _static_serve, {"document_root": settings.MEDIA_ROOT}),
    ]
