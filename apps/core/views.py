"""Vistas core: root (login / redirect al vault), service worker y manifest."""
from django.conf import settings
from django.http import HttpResponse, JsonResponse


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


def llms_txt_root(request):
    """`GET /llms.txt` — convención raíz: cómo usar el API de una nota de ESTE
    vault si sólo se tiene un enlace `/s/<token>/`.

    Muchos agentes/IA comprueban `/llms.txt` en la raíz de un dominio por
    costumbre, antes incluso de que nadie les diga que existe esa guía. Este
    documento no sustituye a la guía real (`/s/<token>/llms.txt`, scopeada al
    enlace y con sus URLs ya resueltas) — sólo le dice a quien la encuentre
    por la raíz que, si tiene un enlace de nota compartida, la guía de verdad
    cuelga de ESE enlace, no de aquí. No lista notas ni enlaces: el vault en
    sí sigue sin ser público.
    """
    base = request.build_absolute_uri("/")
    lines = [
        "# Cogny — vault de notas Markdown, autoalojado",
        "",
        f"Sitio: {base}",
        "",
        "Este fichero de la raíz no describe un API propio: Cogny no expone",
        "ningún listado ni contenido público desde aquí. Lo único que importa",
        "para una IA es esto:",
        "",
        "Si alguien te ha dado un enlace de nota compartida de este vault —",
        f"con forma `{base}s/<token>/` (el token es una cadena propia de",
        "cada nota) — NO lo abras con un navegador ni intentes averiguar cómo",
        "funciona la página. Añade `llms.txt` al final de esa misma URL y",
        "pide esa dirección con un GET normal. Por ejemplo, para el enlace",
        f"`{base}s/abc123/` la guía está en:",
        "",
        f"    GET {base}s/abc123/llms.txt",
        "",
        "Esa respuesta es una guía en texto plano, generada para ESE enlace en",
        "concreto, con las URLs ya resueltas (nada que rellenar a mano) y con",
        "el criterio editorial del vault para dejar la nota bien escrita. Si el",
        "enlace es de sólo lectura, esa misma URL devuelve 404 — entonces sólo",
        "se puede leer la página tal cual, no hay API de edición que usar.",
        "",
        "No hay ninguna otra puerta de entrada: sin un enlace `/s/<token>/` no",
        "hay nada que una IA pueda listar o pedir desde este dominio.",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")


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
        "id": "/",
        "name": "Cogny",
        "short_name": "Cogny",
        "description": "Bóveda de notas en Markdown, autoalojada.",
        "lang": "es",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "orientation": "portrait-primary",
        "categories": ["productivity", "utilities"],
        "background_color": "#0a0a0f",
        "theme_color": "#0a0a0f",
        "icons": [
            {"src": f"/static/icons/icon-192.png?v={v}", "sizes": "192x192", "type": "image/png"},
            {"src": f"/static/icons/icon-512.png?v={v}", "sizes": "512x512", "type": "image/png"},
            {"src": f"/static/icons/icon-maskable-512.png?v={v}", "sizes": "512x512",
             "type": "image/png", "purpose": "maskable"},
        ],
        "shortcuts": [
            {"name": "Notas", "url": "/"},
            {"name": "Pizarra", "url": "/pizarra/"},
            {"name": "Conocimiento", "url": "/conocimiento/"},
            {"name": "Ajustes", "url": "/settings/"},
        ],
    })
