"""Bóveda comunitaria `/comunidad` — lectura y escritura sin cuenta, por enlace.

Dos capas, mismo criterio que `apps.knowledge`:

* La del **vault** (`vault_page`, `link_entry`, `api_*`) pasa por `access.py` y
  la usa cualquiera que tenga sesión de propietario o un enlace válido. El
  contenido sale de `apps.notes.vault` —el mismo módulo que usan la bóveda
  privada y la API v1— apuntando a `community_root()` en vez de
  `vault.root()`, así que es una implementación completamente separada de
  ficheros en disco: nunca toca `settings.VAULT_ROOT`.
* La de **administración** (`links_*`) es sólo del propietario con sesión, y
  es lo que consume la tarjeta "Bóveda comunitaria" de `/settings/`.

Ojo con `rename`/`move`/`delete`: a propósito NO llaman a
`vault.move_shares`/`vault.drop_shares` (a diferencia de sus equivalentes en
`apps.notes.views`). Esas funciones tocan el modelo `SharedNote`, que indexa
por `path` SIN distinguir de qué bóveda es — llamarlas aquí podría reapuntar o
borrar sin querer el enlace público de una nota de la bóveda PRIVADA que
tuviera la misma ruta relativa. Como la bóveda comunitaria no tiene la
función de "compartir nota" (no encaja en un vault ya compartido por enlace),
simplemente no hay nada que mover ni revocar en `SharedNote` para ella.
"""
import shutil
from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.permissions import require_owner
from apps.core.api import as_int, as_text, error_response as _err, json_body
from apps.notes import pdf, vault
from apps.notes.vault import VaultError

from . import access
from .models import CommunityLink


def community_root() -> Path:
    """Raíz de la bóveda comunitaria, creada si aún no existe.

    Deliberadamente NO es `apps.notes.vault.root()`: esa función está atada a
    `settings.VAULT_ROOT` (la bóveda privada). Aquí se lee la variable propia
    `COMMUNITY_VAULT_ROOT` para que las dos bóvedas vivan en directorios
    distintos y no puedan pisarse aunque compartan la misma capa de acceso a
    disco (`apps.notes.vault`, cuyas funciones ya reciben la raíz como
    parámetro para justo este tipo de reutilización).
    """
    root = Path(settings.COMMUNITY_VAULT_ROOT)
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def _resolve(root: Path, rel):
    try:
        return vault.safe_path(root, rel), None
    except VaultError as exc:
        return None, _err(str(exc), exc.status)


# ════════════ Vault (sesión del dueño o enlace válido) ════════════

@access.community_view
@require_GET
def vault_page(request):
    community_root()
    return render(request, "community/vault.html", {})


@require_GET
def link_entry(request, token):
    """Canjea un enlace comunitario y deja al visitante dentro."""
    link = access.enter_with_link(token)
    response = redirect("/comunidad/")
    access.set_grant(response, link)
    return response


@access.community_api
@require_GET
def api_tree(request):
    root = community_root()
    return JsonResponse({"tree": vault.build_tree(root, root)})


@access.community_api
@require_GET
def api_file_get(request):
    root = community_root()
    target, err = _resolve(root, request.GET.get("path", ""))
    if err:
        return err
    if not target.exists() or target.suffix.lower() != ".md":
        return _err("Nota no encontrada", 404)
    return JsonResponse({
        "path": vault.rel_of(root, target),
        "name": target.stem,
        "content": target.read_text(encoding="utf-8"),
    })


@access.community_api
@require_POST
@json_body
def api_file_save(request):
    root = community_root()
    content = request.data.get("content")
    if content is None:
        content = ""
    if not isinstance(content, str):
        return _err("'content' debe ser texto")
    if len(content.encode("utf-8")) > vault.MAX_NOTE_BYTES:
        return _err("Nota demasiado grande (máx. 5 MB)")
    target, err = _resolve(root, as_text(request.data.get("path")).strip())
    if err:
        return err
    if target.suffix.lower() != ".md":
        return _err("Solo se permiten archivos .md")
    target.parent.mkdir(parents=True, exist_ok=True)
    vault.write_text_atomic(target, content)
    return JsonResponse({"success": True, "path": vault.rel_of(root, target),
                         "updated": int(target.stat().st_mtime)})


@access.community_api
@require_POST
@json_body
def api_create(request):
    root = community_root()
    name = vault.sanitize_name(request.data.get("name"))
    if not name:
        return _err("Nombre inválido")
    parent_dir, err = _resolve(root, as_text(request.data.get("parent")).strip())
    if err:
        return err
    parent_dir.mkdir(parents=True, exist_ok=True)

    if request.data.get("type", "note") == "folder":
        target = parent_dir / name
        if target.exists():
            return _err("Ya existe una carpeta con ese nombre")
        target.mkdir()
        return JsonResponse({"success": True, "path": vault.rel_of(root, target),
                             "type": "folder"})

    fname = name if name.endswith(".md") else name + ".md"
    target = vault.free_path(parent_dir, Path(fname).stem, ".md")
    vault.write_text_atomic(target, "")
    return JsonResponse({"success": True, "path": vault.rel_of(root, target), "type": "note"})


@access.community_api
@require_POST
@json_body
def api_rename(request):
    root = community_root()
    new_name = vault.sanitize_name(request.data.get("name"))
    if not new_name:
        return _err("Nombre inválido")
    src, err = _resolve(root, as_text(request.data.get("path")).strip())
    if err:
        return err
    if not src.exists():
        return _err("No existe", 404)
    if src.is_file() and src.suffix.lower() == ".md" and not new_name.endswith(".md"):
        new_name += ".md"
    dst = src.parent / new_name
    if dst.exists() and dst != src:
        return _err("Ya existe con ese nombre")
    src.rename(dst)
    vault.rename_in_order(src.parent, src.name, dst.name)
    return JsonResponse({"success": True, "path": vault.rel_of(root, dst)})


@access.community_api
@require_POST
@json_body
def api_move(request):
    root = community_root()
    src, err = _resolve(root, as_text(request.data.get("path")).strip())
    if err:
        return err
    dst_dir, err = _resolve(root, as_text(request.data.get("target")).strip())
    if err:
        return err
    if not src.exists() or src == root:
        return _err("No existe", 404)
    try:
        vault.reject_attachments_root(root, src, "mover")
    except VaultError as exc:
        return _err(str(exc), exc.status)
    if not dst_dir.exists() or not dst_dir.is_dir():
        return _err("Carpeta destino no encontrada", 404)
    if src.is_dir():
        try:
            dst_dir.relative_to(src)
            return _err("No se puede mover una carpeta dentro de sí misma")
        except ValueError:
            pass
    if dst_dir == src.parent:
        return JsonResponse({"success": True, "path": vault.rel_of(root, src)})
    dst = dst_dir / src.name
    if dst.exists():
        return _err("Ya existe un elemento con ese nombre en el destino")
    shutil.move(str(src), str(dst))
    vault.remove_from_order(src.parent, src.name)
    return JsonResponse({"success": True, "path": vault.rel_of(root, dst)})


@access.community_api
@require_POST
@json_body
def api_reorder(request):
    root = community_root()
    order = request.data.get("order")
    if not isinstance(order, list) or not all(isinstance(n, str) for n in order):
        return _err("Orden inválido")
    folder, err = _resolve(root, as_text(request.data.get("folder")).strip())
    if err:
        return err
    if not folder.exists() or not folder.is_dir():
        return _err("Carpeta no encontrada", 404)
    vault.set_order(folder, order)
    return JsonResponse({"success": True})


@access.community_api
@require_POST
@json_body
def api_delete(request):
    root = community_root()
    target, err = _resolve(root, as_text(request.data.get("path")).strip())
    if err:
        return err
    if not target.exists() or target == root:
        return _err("No existe", 404)
    parent, name = target.parent, target.name
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()
    vault.remove_from_order(parent, name)
    return JsonResponse({"success": True})


@access.community_api
@require_GET
def api_search(request):
    root = community_root()
    terms = [t.lower() for t in (request.GET.get("q") or "").split() if t]
    if not terms:
        return JsonResponse({"results": []})
    return JsonResponse({"results": [
        {"path": vault.rel_of(root, f), "name": f.stem, "snippet": snippet,
         "updated": int(f.stat().st_mtime)}
        for f, snippet in vault.search_notes(root, terms, limit=50,
                                             snippet_before=40, snippet_after=80)
    ]})


@access.community_api
@require_POST
def api_upload(request):
    f = request.FILES.get("file")
    if not f:
        return _err("Falta archivo")
    root = community_root()
    note_path = as_text(request.POST.get("note")).strip()
    target = vault.save_upload(root, f, note_path=note_path)
    return JsonResponse({"success": True, "name": target.name,
                         "path": vault.rel_of(root, target)})


@access.community_view
@require_GET
def api_asset(request):
    """Sirve un adjunto. Va con `community_view` (404, no JSON) por la misma
    razón que en `apps.knowledge`: un `<img>` roto debe fallar como imagen,
    no pintar un cuerpo JSON."""
    root = community_root()
    try:
        target = vault.safe_path(root, request.GET.get("path", ""))
    except VaultError:
        raise Http404
    if not target.exists() or target.is_dir():
        raise Http404
    content_type, as_attachment = vault.safe_content_type(target.name)
    return FileResponse(open(target, "rb"), content_type=content_type,
                        as_attachment=as_attachment, filename=target.name)


@access.community_api
@require_POST
@json_body
def api_pdf(request):
    """PDF de la nota que el cliente manda ya renderizada — igual que
    `apps.notes.views.notes_pdf`, pero SIN temas personalizados.

    `PdfTheme` es una tabla global compartida con la bóveda privada: dejar
    que cualquiera con un enlace comunitario cree/edite/borre esas plantillas
    podría cargarse un tema que el dueño usa de verdad en su bóveda privada.
    Así que aquí sólo se exportan los dos estilos integrados (claro/oscuro) +
    orientación, sin más — no hay `theme`, ni endpoints para gestionarlos.
    """
    body_html = pdf.sanitize_html(request.data.get("html") or "")
    if not body_html.strip():
        return _err("Nada que exportar")
    display_title = as_text(request.data.get("title")).strip()[:120]
    filename = vault.sanitize_name(display_title or "nota") or "nota"
    try:
        pdf_bytes = pdf.render(body_html, dark=bool(request.data.get("dark")), theme=None,
                               title=display_title, landscape=bool(request.data.get("landscape")))
    except pdf.PdfError as exc:
        return _err(str(exc), exc.status)
    resp = HttpResponse(pdf_bytes, content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="{filename}.pdf"'
    resp["Content-Length"] = str(len(pdf_bytes))
    return resp


# ════════════ Copiar a la bóveda privada (propietario, con sesión) ═══════════

@login_required
@require_owner
@require_POST
@json_body
def api_copy_to_private(request):
    """Duplica una nota o carpeta de la bóveda comunitaria a la privada.

    A propósito exige sesión de PROPIETARIO (no basta un enlace comunitario
    válido): escribir en la bóveda privada tiene que seguir siendo cosa
    exclusiva del dueño, nunca de quien sólo tenga un enlace de amigos.
    """
    try:
        new_rel = vault.copy_across(community_root(),
                                    as_text(request.data.get("path")).strip(),
                                    vault.root())
    except VaultError as exc:
        return _err(str(exc), exc.status)
    return JsonResponse({"success": True, "path": new_rel})


# ════════════ Administración de enlaces (propietario, con sesión) ════════════

def _link_json(request, link: CommunityLink) -> dict:
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
def links_list(request):
    return JsonResponse({"links": [
        _link_json(request, link)
        for link in CommunityLink.objects.filter(revoked=False)
    ]})


@login_required
@require_owner
@require_POST
@json_body
def links_create(request):
    link = CommunityLink.objects.create(name=as_text(request.data.get("name")).strip()[:80])
    return JsonResponse({"success": True, "link": _link_json(request, link)}, status=201)


@login_required
@require_owner
@require_POST
@json_body
def links_revoke(request):
    link = CommunityLink.objects.filter(pk=as_int(request.data.get("id")),
                                        revoked=False).first()
    if not link:
        return _err("Enlace no encontrado", 404)
    link.revoked = True
    link.save(update_fields=["revoked"])
    return JsonResponse({"success": True})
