"""Vistas core: root (login / redirect al vault), service worker y manifest."""
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect


def root(request):
    """El vault en la raíz (autenticado) o el login (anónimo).

    El vault vive en `/`, no en `/notes/`. Como esta vista sólo delega a
    `notes.index` cuando hay sesión, el acceso anónimo nunca toca el vault.
    """
    if request.user.is_authenticated:
        from apps.notes.views import index
        return index(request)
    from apps.accounts.views import login_view
    return login_view(request)


def service_worker(request):
    """Sirve `sw.js` desde disco con las cabeceras correctas para Service Workers.

    El JS vive en `apps/core/static/core/sw.js` para que cualquiera pueda editarlo
    como código normal (con linter/formatter). El view sólo le añade los headers:

    - `Cache-Control: no-cache, no-store, must-revalidate` — los SW NUNCA se
      cachean; Cloudflare/proxies deben preguntar siempre al origen.
    - `Service-Worker-Allowed: /` — scope al raíz del sitio.

    Nota: no servimos directamente con nginx para asegurar estas cabeceras.
    """
    from pathlib import Path
    sw_path = Path(__file__).parent / "static" / "core" / "sw.js"
    body = sw_path.read_text(encoding="utf-8").replace(
        "__ASSET_VERSION__", settings.ASSET_VERSION
    )
    resp = HttpResponse(body, content_type="application/javascript")
    resp["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    resp["Service-Worker-Allowed"] = "/"
    return resp


def manifest(request):
    v = settings.ASSET_VERSION
    return JsonResponse({
        "name": "Cogny",
        "short_name": "Cogny",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#0a0a0f",
        "theme_color": "#0a0a0f",
        "icons": [
            {"src": f"/static/icons/icon-192.png?v={v}", "sizes": "192x192", "type": "image/png"},
            {"src": f"/static/icons/icon-512.png?v={v}", "sizes": "512x512", "type": "image/png"},
        ],
    })
