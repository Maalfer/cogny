"""Bóveda pública `/conocimiento` — lector anónimo de sólo lectura.

Dos capas bien separadas:

* Lo **público** (`reader`, `master_entry`, `api_*`) pasa por `access.py` y sólo
  sabe leer. No hay aquí ni un endpoint que escriba: la garantía de "sólo
  lectura" es que las operaciones de escritura no existen en esta superficie,
  no que el frontend esconda los botones.
* Lo **administrativo** (`config_*`, `links_*`) es del propietario con sesión, y
  es lo que consume la tarjeta de Ajustes.

El contenido sale de `apps.notes.vault`, el mismo módulo que usan la web con
sesión y la API v1: una sola implementación de las reglas del sistema de
ficheros.
"""
import mimetypes

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.permissions import require_owner
from apps.core.api import as_int, as_text, error_response as _err, json_body
from apps.notes import vault
from apps.notes.vault import VaultError

from . import access
from .models import MasterLink, PublicVault, normalize_domain

# Cuántos resultados devuelve el buscador público. Más bajo que el de la web
# con sesión: aquí cada búsqueda recorre la bóveda entera y la pide gente que
# no controlamos.
SEARCH_LIMIT = 30

# Extensiones que se pueden enseñar EMBEBIDAS sin riesgo. Todo lo demás se
# sirve como descarga: un `.html` o un `.svg` servido en línea corre JavaScript
# en nuestro propio origen, y esto lo abre cualquiera de internet.
INLINE_EXTS = {
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".avif", ".ico",
    ".pdf", ".mp4", ".webm", ".ogg", ".mp3", ".wav", ".m4a",
}


# ════════════ Público ════════════

@access.public_view
@require_GET
def reader(request):
    """La bóveda navegable. El contenido lo pide el cliente a `api_*`."""
    vault.root()
    return render(request, "knowledge/reader.html", {
        "open_path": request.GET.get("n", ""),
        "grant_kind": request.public_grant.get("k", ""),
    })


@require_GET
def master_entry(request, token):
    """Canjea un enlace maestro y deja al visitante dentro."""
    cfg, link = access.enter_with_master(request, token)
    response = redirect(access.reader_url(request.GET.get("n", "")))
    access.set_grant(response, cfg, access.GRANT_MASTER, master_token=link.token)
    return response


@access.public_api
@require_GET
def api_tree(request):
    root = vault.root()
    return JsonResponse({"tree": vault.build_tree(root, root)})


@access.public_api
@require_GET
def api_note(request):
    root = vault.root()
    try:
        target = vault.safe_path(root, request.GET.get("path", ""))
    except VaultError as exc:
        return _err(str(exc), exc.status)
    if not target.is_file() or target.suffix.lower() != ".md":
        return _err("Nota no encontrada", 404)
    return JsonResponse({
        "path": vault.rel_of(root, target),
        "name": target.stem,
        "content": target.read_text(encoding="utf-8"),
        "updated": int(target.stat().st_mtime),
    })


@access.public_api
@require_GET
def api_search(request):
    root = vault.root()
    terms = [t.lower() for t in (request.GET.get("q") or "").split() if t]
    if not terms:
        return JsonResponse({"results": []})
    return JsonResponse({"results": [
        {"path": vault.rel_of(root, f), "name": f.stem, "snippet": snippet}
        for f, snippet in vault.search_notes(root, terms, limit=SEARCH_LIMIT,
                                             snippet_before=40, snippet_after=80)
    ]})


@access.public_view
@require_GET
def api_asset(request):
    """Sirve un adjunto de la bóveda, endurecido para ojos ajenos.

    Va con `public_view` y no con `public_api` porque un `<img>` que caduque
    debe fallar como imagen rota, no pintar un JSON.
    """
    root = vault.root()
    try:
        target = vault.safe_path(root, request.GET.get("path", ""))
    except VaultError:
        raise Http404
    if not target.is_file():
        raise Http404
    ext = target.suffix.lower()
    if ext == ".md":
        # Las notas se leen por `api_note`, que es quien las renderiza.
        raise Http404

    content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    response = FileResponse(open(target, "rb"), content_type=content_type)
    if ext not in INLINE_EXTS:
        response["Content-Disposition"] = f'attachment; filename="{target.name}"'
    # Aunque sólo sirvamos tipos de la lista en línea, el cinturón y los
    # tirantes: nada de adivinar el tipo y nada de ejecutar nada.
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "default-src 'none'; sandbox"
    return response


# ════════════ Administración (propietario, con sesión) ════════════

def _config_json(request, cfg: PublicVault) -> dict:
    return {
        "enabled": cfg.enabled,
        "allowed_domains": cfg.allowed_domains,
        "domains": cfg.domain_list(),
        "grant_days": cfg.grant_days,
        "url": request.build_absolute_uri("/conocimiento/"),
    }


def _link_json(request, link: MasterLink) -> dict:
    return {
        "id": link.id,
        "name": link.name,
        "url": request.build_absolute_uri(link.path()),
        "visits": link.visits,
        "created_at": link.created_at.isoformat(),
        "last_used_at": link.last_used_at.isoformat() if link.last_used_at else None,
    }


@login_required
@require_owner
@require_GET
def config_get(request):
    return JsonResponse(_config_json(request, PublicVault.get()))


@login_required
@require_owner
@require_POST
@json_body
def config_save(request):
    cfg = PublicVault.get()

    if "enabled" in request.data:
        cfg.enabled = bool(request.data.get("enabled"))

    if "allowed_domains" in request.data:
        raw = as_text(request.data.get("allowed_domains"))
        # Se guarda ya normalizado: lo que el propietario vuelva a ver en el
        # cuadro es exactamente lo que el filtro va a comparar, sin sorpresas
        # del tipo "pegué la URL entera y no filtraba".
        cleaned = [normalize_domain(line) for line in raw.splitlines()]
        cfg.allowed_domains = "\n".join(d for d in cleaned if d)

    if "grant_days" in request.data:
        days = as_int(request.data.get("grant_days"))
        if days is None or not 1 <= days <= 365:
            return _err("El permiso debe durar entre 1 y 365 días")
        cfg.grant_days = days

    cfg.save()
    return JsonResponse({"success": True, **_config_json(request, cfg)})


@login_required
@require_owner
@require_GET
def links_list(request):
    return JsonResponse({"links": [
        _link_json(request, link)
        for link in MasterLink.objects.filter(revoked=False)
    ]})


@login_required
@require_owner
@require_POST
@json_body
def links_create(request):
    link = MasterLink.objects.create(name=as_text(request.data.get("name")).strip()[:80])
    return JsonResponse({"success": True, "link": _link_json(request, link)}, status=201)


@login_required
@require_owner
@require_POST
@json_body
def links_revoke(request):
    link = MasterLink.objects.filter(pk=as_int(request.data.get("id")),
                                     revoked=False).first()
    if not link:
        return _err("Enlace no encontrado", 404)
    # Se marca en vez de borrarse: `access.read_grant` mira esta fila para echar
    # también a quien ya había entrado con ese enlace.
    link.revoked = True
    link.save(update_fields=["revoked"])
    return JsonResponse({"success": True})
