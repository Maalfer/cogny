"""Vistas del vault (sesión + CSRF): las consume el frontend de la web.

Aquí sólo vive la capa HTTP —validar lo que llega, traducir el resultado a
JSON—. Todo lo que toca el disco está en `vault.py` y la exportación a PDF en
`pdf.py`.
"""
import json
import re
import secrets
import shutil
from pathlib import Path
from urllib.parse import quote

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import check_password, make_password
from django.core import signing
from django.http import FileResponse, Http404, HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.permissions import require_owner, require_write
from apps.core.api import as_int, as_text, error_response as _err, json_body

from . import pdf, themes, vault
from .models import PdfTheme, PdfThemeImage, SharedNote
from .vault import VaultError


def _resolve(root: Path, rel):
    """`(ruta, None)`, o `(None, respuesta de error)` si la ruta no es válida."""
    try:
        return vault.safe_path(root, rel), None
    except VaultError as exc:
        return None, _err(str(exc), exc.status)


# ════════════ Vault ════════════

@login_required
def index(request):
    vault.root()  # asegura que el directorio existe
    return render(request, "notes/notes.html", {})


@login_required
@require_GET
def tree(request):
    root = vault.root()
    return JsonResponse({"tree": vault.build_tree(root, root)})


@login_required
@require_GET
def file_get(request):
    root = vault.root()
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


@login_required
@require_write
@require_POST
@json_body
def file_save(request):
    root = vault.root()
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


@login_required
@require_write
@require_POST
@json_body
def create(request):
    root = vault.root()
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


@login_required
@require_write
@require_POST
@json_body
def rename(request):
    root = vault.root()
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
    old_rel, was_dir = vault.rel_of(root, src), src.is_dir()
    src.rename(dst)
    vault.rename_in_order(src.parent, src.name, dst.name)
    new_rel = vault.rel_of(root, dst)
    vault.move_shares(old_rel, new_rel, was_dir)
    vault.rename_private(root, old_rel, new_rel, was_dir)
    vault.rewrite_attachment_owners(root, old_rel, new_rel, was_dir)
    return JsonResponse({"success": True, "path": new_rel})


@login_required
@require_owner
@require_POST
@json_body
def set_private(request):
    """Marca/desmarca una nota —o una CARPETA entera— como privada: invisible
    en `/conocimiento`, igual que siempre dentro de Cogny con sesión. Sólo el
    propietario decide qué se enseña en la bóveda pública, igual que la
    configuración de esa bóveda (`apps.knowledge.views.config_save`) — de ahí
    `@require_owner` y no `@require_write`.

    Con una carpeta la marca la heredan todos sus descendientes (ver
    `vault.marked_private`), así que no hay que recorrer nada aquí ni volver a
    marcar las notas que se creen dentro más adelante.
    """
    root = vault.root()
    target, err = _resolve(root, as_text(request.data.get("path")).strip())
    if err:
        return err
    is_dir = target.is_dir()
    if not target.exists() or not (is_dir or target.suffix.lower() == ".md"):
        return _err("Nota o carpeta no encontrada", 404)
    if target == root:
        # Marcar la raíz escondería la bóveda entera, que es exactamente lo
        # que hace el interruptor de "Bóveda pública" en Ajustes — y encima
        # dejaría una marca con ruta vacía que no se ve en ningún sitio.
        return _err("Para ocultar la bóveda entera, desactívala en Ajustes")
    private = bool(request.data.get("private"))
    rel = vault.rel_of(root, target)
    vault.set_private(root, rel, private)
    return JsonResponse({"success": True, "path": rel, "private": private,
                         "is_dir": is_dir})


@login_required
@require_write
@require_POST
@json_body
def move(request):
    """Mueve una nota/carpeta/archivo a otra carpeta (drag & drop del árbol).

    Solo reubica en el filesystem; el orden dentro de la carpeta destino lo
    fija el frontend con una llamada aparte a `reorder` (conoce la posición
    exacta donde se soltó, cosa que este endpoint no necesita saber).
    """
    root = vault.root()
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
            pass  # dst_dir no es src ni un descendiente: ok
    if dst_dir == src.parent:
        return JsonResponse({"success": True, "path": vault.rel_of(root, src)})
    dst = dst_dir / src.name
    if dst.exists():
        return _err("Ya existe un elemento con ese nombre en el destino")
    old_rel, was_dir = vault.rel_of(root, src), src.is_dir()
    shutil.move(str(src), str(dst))
    vault.remove_from_order(src.parent, src.name)
    new_rel = vault.rel_of(root, dst)
    vault.move_shares(old_rel, new_rel, was_dir)
    vault.rename_private(root, old_rel, new_rel, was_dir)
    vault.rewrite_attachment_owners(root, old_rel, new_rel, was_dir)
    return JsonResponse({"success": True, "path": new_rel})


@login_required
@require_write
@require_POST
@json_body
def reorder(request):
    """Fija el orden manual de los hijos directos de una carpeta."""
    root = vault.root()
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


@login_required
@require_write
@require_POST
@json_body
def delete(request):
    root = vault.root()
    target, err = _resolve(root, as_text(request.data.get("path")).strip())
    if err:
        return err
    if not target.exists() or target == root:
        return _err("No existe", 404)
    parent, name = target.parent, target.name
    rel_path, was_dir = vault.rel_of(root, target), target.is_dir()
    if was_dir:
        shutil.rmtree(target)
    else:
        target.unlink()
    vault.remove_from_order(parent, name)
    vault.drop_shares(rel_path, was_dir)
    vault.drop_private(root, rel_path, was_dir)
    return JsonResponse({"success": True})


@login_required
@require_GET
def search(request):
    root = vault.root()
    terms = [t.lower() for t in (request.GET.get("q") or "").split() if t]
    if not terms:
        return JsonResponse({"results": []})
    return JsonResponse({"results": [
        {"path": vault.rel_of(root, f), "name": f.stem, "snippet": snippet,
         "updated": int(f.stat().st_mtime)}
        for f, snippet in vault.search_notes(root, terms, limit=50,
                                             snippet_before=40, snippet_after=80)
    ]})


@login_required
@require_GET
def storage(request):
    """Estadísticas de la bóveda: total, desglose por tipo y conteos."""
    return JsonResponse({"success": True, **vault.stats(vault.root())})


@login_required
@require_write
@require_POST
def optimize_images(request):
    """Recodifica las imágenes de la bóveda a WebP, in-place.

    Responde NDJSON (una línea JSON por evento) para que el frontend pinte la
    barra de progreso en tiempo real. Los eventos los define `vault.optimize_images`.
    """
    def stream():
        for event in vault.optimize_images(vault.root()):
            yield (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8")

    resp = StreamingHttpResponse(stream(), content_type="application/x-ndjson")
    resp["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp["X-Accel-Buffering"] = "no"   # nginx: no bufferizar (flush inmediato)
    return resp


# ════════════ Adjuntos ════════════

@login_required
@require_write
@require_POST
def upload(request):
    """Sube un adjunto a la bóveda (imagen u otro archivo)."""
    f = request.FILES.get("file")
    if not f:
        return _err("Falta archivo")
    root = vault.root()
    note_path = as_text(request.POST.get("note")).strip()
    target = vault.save_upload(root, f, note_path=note_path)
    return JsonResponse({"success": True, "name": target.name,
                         "path": vault.rel_of(root, target)})


@login_required
@require_GET
def asset(request):
    root = vault.root()
    try:
        target = vault.safe_path(root, request.GET.get("path", ""))
    except VaultError:
        raise Http404
    if not target.exists() or target.is_dir():
        raise Http404
    content_type, as_attachment = vault.safe_content_type(target.name)
    return FileResponse(open(target, "rb"), content_type=content_type,
                        as_attachment=as_attachment, filename=target.name)


# ════════════ Export / import ════════════

@login_required
@require_GET
def export_vault(request):
    tmp, size = vault.export_zip(vault.root())
    resp = FileResponse(tmp, content_type="application/zip")
    fname = vault.sanitize_name(request.user.username) or "vault"
    resp["Content-Disposition"] = f'attachment; filename="vault-{fname}.zip"'
    resp["Content-Length"] = str(size)
    return resp


@login_required
@require_write
@require_POST
def import_vault(request):
    f = request.FILES.get("file")
    if not f:
        return _err("Falta archivo")
    try:
        vault.import_zip(vault.root(), f, request.POST.get("mode", "merge"))
    except VaultError as exc:
        return _err(str(exc), exc.status)
    return JsonResponse({"success": True})


# ════════════ Exportar nota a PDF ════════════

@login_required
@require_POST
@json_body
def notes_pdf(request):
    """PDF de la nota que el cliente manda ya renderizada (ver `pdf.py`).

    `theme` (opcional) es el id de un `PdfTheme`: maqueta la nota dentro de esa
    plantilla HTML+CSS. Un id que ya no existe es un 404 y no un export
    silenciosamente sin tema: si el usuario pidió el PDF con la identidad de
    una empresa, un PDF neutro es una respuesta equivocada, no una degradación
    aceptable. `landscape` saca la hoja apaisada (y a dos columnas).
    """
    body_html = pdf.sanitize_html(request.data.get("html") or "")
    if not body_html.strip():
        return _err("Nada que exportar")
    display_title = as_text(request.data.get("title")).strip()[:120]
    filename = vault.sanitize_name(display_title or "nota") or "nota"
    theme = None
    if request.data.get("theme") not in (None, "", 0):
        theme = PdfTheme.objects.filter(pk=as_int(request.data.get("theme"))).first()
        if theme is None:
            return _err("El tema ya no existe", 404)
    try:
        pdf_bytes = pdf.render(body_html, dark=bool(request.data.get("dark")),
                               theme=theme, title=display_title,
                               landscape=bool(request.data.get("landscape")))
    except pdf.PdfError as exc:
        return _err(str(exc), exc.status)
    except Exception:
        import traceback as _tb
        with open("/tmp/pdf_export_traceback.log", "w") as _f:
            _tb.print_exc(file=_f)
        raise
    resp = HttpResponse(pdf_bytes, content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="{filename}.pdf"'
    resp["Content-Length"] = str(len(pdf_bytes))
    return resp


# ════════════ Temas de exportación (plantillas HTML+CSS) ════════════

@login_required
@require_GET
def themes_list(request):
    """Los temas disponibles para exportar.

    También en sólo lectura: quien sólo puede leer sigue pudiendo exportar con
    un tema ya creado, aunque no pueda tocarlo. Con `?id=` devuelve además el
    HTML de la plantilla — en el listado no va, que son 120 KB por tema.
    """
    if request.GET.get("id"):
        theme = PdfTheme.objects.filter(pk=as_int(request.GET.get("id"))).first()
        if theme is None:
            raise Http404
        return JsonResponse({"theme": themes.theme_json(theme, with_html=True)})
    return JsonResponse({
        "themes": [themes.theme_json(t) for t in PdfTheme.objects.prefetch_related("images")],
        "starter": themes.starter_html(),
    })


@login_required
@require_write
@require_POST
@json_body
def theme_save(request):
    """Crea un tema, o actualiza el del `id` recibido."""
    theme = None
    if request.data.get("id"):
        theme = PdfTheme.objects.filter(pk=as_int(request.data.get("id"))).first()
        if theme is None:
            return _err("El tema ya no existe", 404)
    try:
        theme = themes.save_theme(request.data, theme)
    except themes.ThemeError as exc:
        return _err(str(exc), exc.status)
    return JsonResponse({"success": True, "theme": themes.theme_json(theme, with_html=True)})


@login_required
@require_write
@require_POST
@json_body
def theme_delete(request):
    theme = PdfTheme.objects.filter(pk=as_int(request.data.get("id"))).first()
    if theme is not None:
        themes.delete_theme(theme)
    return JsonResponse({"success": True})


@login_required
@require_write
@require_POST
def theme_image_upload(request):
    """Sube una imagen del tema — multipart, no JSON."""
    theme = PdfTheme.objects.filter(pk=as_int(request.POST.get("id"))).first()
    if theme is None:
        return _err("El tema ya no existe", 404)
    upload = request.FILES.get("file")
    if not upload:
        return _err("Falta archivo")
    try:
        themes.add_image(theme, request.POST.get("name", ""), upload)
    except themes.ThemeError as exc:
        return _err(str(exc), exc.status)
    return JsonResponse({"success": True, "theme": themes.theme_json(theme)})


@login_required
@require_write
@require_POST
@json_body
def theme_image_delete(request):
    image = PdfThemeImage.objects.filter(pk=as_int(request.data.get("image"))).first()
    if image is None:
        return _err("La imagen ya no existe", 404)
    theme = image.theme
    themes.remove_image(image)
    return JsonResponse({"success": True, "theme": themes.theme_json(theme)})


@login_required
@require_GET
def theme_image(request):
    """La imagen tal cual, para la lista del editor de temas."""
    image = PdfThemeImage.objects.filter(pk=as_int(request.GET.get("image"))).first()
    path = themes.image_path(image) if image else None
    if not path or not path.exists():
        raise Http404
    resp = FileResponse(open(path, "rb"),
                        content_type=themes.IMAGE_MIME.get(image.ext, "application/octet-stream"))
    # Un SVG es un documento con scripts en potencia, y servido desde el mismo
    # origen que la app sería XSS con sesión. En el editor se pinta dentro de un
    # <img> (donde nunca ejecuta), pero abrir esta URL a pelo sí lo haría: el
    # sandbox lo neutraliza y `nosniff` evita que el navegador reinterprete el
    # tipo por su cuenta.
    resp["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; sandbox"
    resp["X-Content-Type-Options"] = "nosniff"
    return resp


@login_required
@require_write
@require_POST
@json_body
def theme_preview(request):
    """PDF de una nota de muestra con la plantilla que se está editando.

    Va sin guardar a propósito: afinar un tema es prueba y error, y obligar a
    guardar cada tanteo llenaría la lista de versiones a medio hacer.
    """
    html = as_text(request.data.get("html"))
    if len(html) > themes.MAX_HTML_CHARS:
        return _err("La plantilla no puede pasar de 120.000 caracteres")
    theme = PdfTheme.objects.filter(pk=as_int(request.data.get("id"))).first()
    try:
        pdf_bytes = pdf.render(themes.SAMPLE_NOTE_HTML,
                               theme=theme, theme_html=html,
                               title="Nota de muestra",
                               landscape=bool(request.data.get("landscape")))
    except pdf.PdfError as exc:
        return _err(str(exc), exc.status)
    resp = HttpResponse(pdf_bytes, content_type="application/pdf")
    resp["Content-Disposition"] = 'inline; filename="vista-previa.pdf"'
    resp["Content-Length"] = str(len(pdf_bytes))
    return resp


# ════════════ Compartir nota (enlace público, con contraseña opcional) ════════

@login_required
@require_write
@require_POST
@json_body
def share_create(request):
    """Crea (o actualiza) el enlace público de una nota.

    Reutiliza el token existente si la nota ya se había compartido antes, para
    que el enlace no cambie cada vez que se reabre el modal de "Compartir".
    `password` vacío/ausente quita la contraseña; con valor, la (re)establece.
    `can_write` decide si el enlace es de sólo lectura o también deja escribir
    en la nota (ver `SharedNote`).
    """
    root = vault.root()
    password = request.data.get("password") or ""
    if not isinstance(password, str):
        return _err("'password' debe ser texto")
    target, err = _resolve(root, as_text(request.data.get("path")).strip())
    if err:
        return err
    if not target.exists() or target.suffix.lower() != ".md":
        return _err("Nota no encontrada", 404)
    share, _created = SharedNote.objects.get_or_create(
        path=vault.rel_of(root, target),
        defaults={"token": secrets.token_urlsafe(16)},
    )
    share.password_hash = make_password(password) if password else ""
    share.can_write = bool(request.data.get("can_write"))
    share.save(update_fields=["password_hash", "can_write", "updated_at"])
    return JsonResponse({
        "success": True, "token": share.token,
        "url": request.build_absolute_uri(f"/s/{share.token}/"),
        "has_password": bool(share.password_hash),
        "can_write": share.can_write,
    })


@login_required
@require_GET
def share_status(request):
    """Estado actual del enlace público de una nota (o `shared: false`)."""
    root = vault.root()
    target, err = _resolve(root, request.GET.get("path", ""))
    if err:
        return err
    share = SharedNote.objects.filter(path=vault.rel_of(root, target)).first()
    if not share:
        return JsonResponse({"shared": False})
    return JsonResponse({
        "shared": True, "token": share.token,
        "url": request.build_absolute_uri(f"/s/{share.token}/"),
        "has_password": bool(share.password_hash),
        "can_write": share.can_write,
    })


@login_required
@require_write
@require_GET
def share_list(request):
    """Todos los enlaces públicos activos (panel "Enlaces compartidos").

    El token es la credencial que abre la nota sin autenticar, así que esta
    vista necesita el mismo permiso que `share_create`/`share_revoke` — no
    basta con estar logueado. Antes sólo llevaba `@login_required`, así que
    un invitado de sólo lectura podía listar los tokens de toda la bóveda.
    """
    return JsonResponse({"shares": [
        {
            "path": s.path,
            "name": Path(s.path).stem,
            "token": s.token,
            "url": request.build_absolute_uri(f"/s/{s.token}/"),
            "has_password": bool(s.password_hash),
            "can_write": s.can_write,
        }
        for s in SharedNote.objects.all().order_by("-updated_at")
    ]})


@login_required
@require_write
@require_POST
@json_body
def share_revoke(request):
    """Deja de compartir una nota (borra el enlace público)."""
    root = vault.root()
    target, err = _resolve(root, as_text(request.data.get("path")).strip())
    if err:
        return err
    SharedNote.objects.filter(path=vault.rel_of(root, target)).delete()
    return JsonResponse({"success": True})


# ── Vista pública (sin login) de una nota compartida ─────────────────────────

# Sólo imágenes y PDFs se resuelven en la vista pública: los embeds a OTRAS
# notas (![[OtraNota]]) no se exponen (evita que compartir una nota filtre el
# resto de la bóveda por transclusión) y se muestran como "no disponible".
_SHARE_ASSET_EXTS = vault.IMAGE_EXTS | {".pdf"}
_EMBED_REF_RE = re.compile(
    r'!\[\[([^\]|#]+)(?:\|[^\]]*)?\]\]|!\[[^\]]*\]\(([^)\s]+)\)|<img\s[^>]*src=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_SHARE_ASSET_SALT = "cogny.notes.share_asset"


def _extract_asset_refs(content: str) -> set:
    refs = set()
    for m in _EMBED_REF_RE.finditer(content or ""):
        ref = (m.group(1) or m.group(2) or m.group(3) or "").strip()
        if ref and not re.match(r"^(https?:|data:|mailto:)", ref, re.IGNORECASE):
            refs.add(ref)
    return refs


def _resolve_asset_ref(root: Path, ref: str, note_path: str):
    """Resuelve una referencia de embed a un archivo del vault (o None) para
    el enlace PÚBLICO de `note_path`.

    A diferencia de `findFileByName` del cliente (ruta exacta primero, si no
    por nombre en CUALQUIER parte del vault — correcto para un usuario ya
    autenticado, que ya ve la bóveda entera), aquí ni la ruta directa ni el
    fallback por nombre bastan por sí solos: los dos se restringen a
    `Adjuntos/` (fuera de ahí no hay ningún adjunto legítimo, sólo hace falta
    escribir a mano `![alt](OtraCarpeta/archivo.pdf)` para apuntar a
    cualquier cosa) Y, dentro de `Adjuntos/`, el archivo tiene que estar
    registrado como subido para ESTA nota exacta (`vault.attachment_owner`).
    Sin la segunda condición, cualquier adjunto ya existente en la bóveda
    compartida —de cualquier nota, de cualquier usuario— se publicaría con
    sólo nombrarlo desde una nota sin relación real con él; con ella, el
    editor sólo puede compartir públicamente lo que él mismo subió para esta
    nota. Adjuntos anteriores a este control quedan sin dueño registrado a
    propósito: no se resuelven en el enlace público (fail-closed), aunque la
    bóveda autenticada los sigue viendo sin restricción.
    """
    cleaned = ref.replace("\\", "/").split("#")[0].strip().lstrip("./")
    if not cleaned:
        return None
    attachments_dir = root / vault.ATTACHMENTS_DIR

    candidate = None
    try:
        direct = vault.safe_path(root, cleaned)
        if direct.is_file() and direct.suffix.lower() in _SHARE_ASSET_EXTS:
            candidate = direct
    except VaultError:
        pass

    if candidate is None and attachments_dir.is_dir():
        base = cleaned.rsplit("/", 1)[-1].lower()
        base_noext = re.sub(r"\.[^.]+$", "", base)
        for p in attachments_dir.rglob("*"):
            try:
                if not p.is_file() or p.suffix.lower() not in _SHARE_ASSET_EXTS:
                    continue
            except OSError:
                continue
            if p.name.lower() == base or p.stem.lower() == base_noext:
                candidate = p
                break

    if candidate is None:
        return None
    try:
        candidate.relative_to(attachments_dir)
    except ValueError:
        return None
    if vault.attachment_owner(root, candidate) != note_path:
        return None
    return candidate


def _build_share_assets(root: Path, token: str, content: str, note_path: str):
    """`{ref_original: url_firmada}` sólo para las imágenes/PDFs referenciados
    por ESTA nota — nunca la bóveda entera. El segundo valor devuelto dice si
    hay al menos una IMAGEN entre ellos (a diferencia de un PDF suelto) — lo
    usa la plantilla para mostrar u ocultar el botón de "descargar en .zip"."""
    out = {}
    has_images = False
    for ref in _extract_asset_refs(content):
        hit = _resolve_asset_ref(root, ref, note_path)
        if hit:
            rel = vault.rel_of(root, hit)
            sig = quote(signing.dumps({"t": token, "p": rel}, salt=_SHARE_ASSET_SALT), safe="")
            out[ref] = f"/s/{token}/asset?p={sig}"
            if hit.suffix.lower() in vault.IMAGE_EXTS:
                has_images = True
    return out, has_images


def _share_gate_key(token: str) -> str:
    return f"shared_verified_{token}"


def _shared_target(share: SharedNote):
    """Nota de un enlace público, o 404 si el enlace apunta a algo que ya no
    está (o que nunca debió ser una nota)."""
    root = settings.VAULT_ROOT.resolve()
    try:
        target = vault.safe_path(root, share.path)
    except VaultError:
        raise Http404
    if not target.exists() or target.suffix.lower() != ".md":
        raise Http404
    return root, target


# `ensure_csrf_cookie` para que el guardado del enlace editable (POST a
# `/s/<token>/save`) no dependa de que `base.html` siga pintando
# `{{ csrf_token }}`: hoy eso ya provoca la cookie, pero es un detalle de otra
# plantilla y aquí el visitante no tiene sesión con la que recuperarse de un
# 403. Se emite también en los enlaces de sólo lectura: una cookie CSRF no
# abre ninguna puerta.
@ensure_csrf_cookie
def shared_note_view(request, token):
    share = SharedNote.objects.filter(token=token).first()
    if not share:
        raise Http404
    root, target = _shared_target(share)

    gate_key = _share_gate_key(token)
    error = ""
    if share.password_hash:
        if request.method == "POST":
            if check_password(request.POST.get("password", ""), share.password_hash):
                request.session[gate_key] = True
            else:
                error = "Contraseña incorrecta"
        if not request.session.get(gate_key):
            return render(request, "notes/shared_gate.html", {"error": error})

    content = target.read_text(encoding="utf-8")
    assets, has_images = _build_share_assets(root, token, content, share.path)
    return render(request, "notes/shared.html", {
        "note_name": target.stem,
        "content": content,
        # `can_edit`, no `can_write`: ese nombre ya lo pone el contexto global
        # para el rol de la SESIÓN (lo lee `base.html`), y pisarlo aquí haría
        # que la página compartida mintiera sobre quién es quien la mira.
        "can_edit": share.can_write,
        "assets": assets,
        "has_images": has_images,
    })


@require_POST
def shared_note_save(request, token):
    """Reescribe la nota desde el enlace público, si es editable.

    Mismas comprobaciones que la vista de lectura —enlace vivo, nota que
    sigue existiendo, contraseña ya superada en esta sesión— y una más: el
    enlace tiene que llevar `can_write`. Se responde 404 (no 403) cuando el
    enlace es de sólo lectura: por el mismo criterio que el resto de la
    superficie pública, un token que no puede escribir no debe enterarse de
    que este endpoint existe.

    Escribe con `write_text_atomic` igual que la web con sesión, así que un
    guardado a medias no puede dejar la nota truncada. Sólo cambia el
    contenido: ni renombra, ni borra, ni toca adjuntos.
    """
    share = SharedNote.objects.filter(token=token, can_write=True).first()
    if not share:
        raise Http404
    _root, target = _shared_target(share)
    if share.password_hash and not request.session.get(_share_gate_key(token)):
        raise Http404

    try:
        data = json.loads(request.body or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _err("JSON inválido")
    content = data.get("content") if isinstance(data, dict) else None
    if content is None:
        content = ""
    if not isinstance(content, str):
        return _err("'content' debe ser texto")
    if len(content.encode("utf-8")) > vault.MAX_NOTE_BYTES:
        return _err("Nota demasiado grande (máx. 5 MB)")
    vault.write_text_atomic(target, content)
    return JsonResponse({"success": True, "updated": int(target.stat().st_mtime)})


@require_GET
def shared_note_asset(request, token):
    share = SharedNote.objects.filter(token=token).first()
    if not share:
        raise Http404
    if share.password_hash and not request.session.get(_share_gate_key(token)):
        raise Http404
    try:
        data = signing.loads(request.GET.get("p", ""), salt=_SHARE_ASSET_SALT,
                             max_age=60 * 60 * 24 * 90)
    except signing.BadSignature:
        raise Http404
    if data.get("t") != token:
        raise Http404
    try:
        target = vault.safe_path(settings.VAULT_ROOT.resolve(), data.get("p", ""))
    except VaultError:
        raise Http404
    if not target.exists() or target.is_dir():
        raise Http404
    return FileResponse(open(target, "rb"))


@require_GET
def shared_note_images_zip(request, token):
    """Todas las imágenes de la nota de este enlace, en un único `.zip`.

    Disponible tanto en enlaces de sólo lectura como editables: a diferencia
    del API de más abajo (`shared_note_note`/`shared_note_assets`, que exige
    `can_write`), esto no da acceso a nada que el propio enlace de lectura no
    enseñe ya una por una en la página — es sólo una forma más cómoda de
    bajárselas todas juntas de una vez. Mismas comprobaciones que
    `shared_note_view`: enlace vivo, nota que sigue existiendo, contraseña ya
    superada en esta sesión si la nota la lleva.
    """
    share = SharedNote.objects.filter(token=token).first()
    if not share:
        raise Http404
    root, target = _shared_target(share)
    if share.password_hash and not request.session.get(_share_gate_key(token)):
        raise Http404

    content = target.read_text(encoding="utf-8")
    seen_paths = set()
    used_names = set()
    files = []
    for ref in _extract_asset_refs(content):
        hit = _resolve_asset_ref(root, ref, share.path)
        if not hit or hit.suffix.lower() not in vault.IMAGE_EXTS or hit in seen_paths:
            continue
        seen_paths.add(hit)
        name = hit.name
        if name in used_names:
            n = 2
            while f"{hit.stem} ({n}){hit.suffix}" in used_names:
                n += 1
            name = f"{hit.stem} ({n}){hit.suffix}"
        used_names.add(name)
        files.append((hit, name))
    if not files:
        raise Http404

    tmp, size = vault.export_files_zip(files)
    resp = FileResponse(tmp, content_type="application/zip")
    fname = vault.sanitize_name(target.stem) or "nota"
    resp["Content-Disposition"] = f'attachment; filename="{fname}-imagenes.zip"'
    resp["Content-Length"] = str(size)
    return resp


# ── API de la nota compartida en modo escritura (para una IA, sin sesión) ──
# Cuando el enlace se crea editable (`can_write`), la misma raíz `/s/<token>/`
# que sirve la página HTML para humanos expone además el API JSON de la nota
# y de sus adjuntos: leer/reescribir el contenido y listar, subir, descargar o
# borrar los adjuntos — todo por HTTP sin login. El token en la URL ES la
# credencial, igual que para leer la nota.
#
# Estos endpoints responden igual ante un enlace de sólo lectura que ante uno
# inexistente: 404. Un enlace que no puede escribir no debe enterarse de que
# el API existe (mismo criterio que `shared_note_save`).

def _shared_api_target(request, token):
    """Enlace editable vivo → `(root, target)` de su nota, o 404."""
    share = SharedNote.objects.filter(token=token, can_write=True).first()
    if not share:
        raise Http404
    root, target = _shared_target(share)
    if share.password_hash and not request.session.get(_share_gate_key(token)):
        raise Http404
    return root, target, share


@csrf_exempt
def shared_note_note(request, token):
    """`GET` lee la nota, `POST` la reescribe entera — como JSON, para que una
    IA pueda gestionarla sin sesión. Sólo esa nota: no hay forma de listar la
    bóveda ni de tocar otra (el token ya dice qué nota es)."""
    if request.method not in ("GET", "POST"):
        return _err("Método no permitido (usa GET o POST)", 405)
    root, target, share = _shared_api_target(request, token)

    if request.method == "GET":
        return JsonResponse({
            "path": share.path, "name": target.stem,
            "content": target.read_text(encoding="utf-8"),
        })

    try:
        data = json.loads(request.body or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _err("JSON inválido")
    content = data.get("content") if isinstance(data, dict) else None
    if content is None:
        content = ""
    if not isinstance(content, str):
        return _err("'content' debe ser texto")
    if len(content.encode("utf-8")) > vault.MAX_NOTE_BYTES:
        return _err("Nota demasiado grande (máx. 5 MB)")
    vault.write_text_atomic(target, content)
    return JsonResponse({"success": True, "updated": int(target.stat().st_mtime)})


@csrf_exempt
def shared_note_assets(request, token):
    """Adjuntos de la nota de este enlace editable. `GET` los lista — los que
    la nota referencia con `![[nombre]]` más los que ya se subieron para esta
    nota y aún no se mencionan en el texto. `POST` (multipart, campo `file`)
    sube uno nuevo, registrado como propiedad de ESTA nota
    (`vault.save_upload`). Nunca la bóveda entera, sólo lo que es de esta
    nota — el mismo criterio de dueño registrado (`vault.attachment_owner`)
    que usa el enlace público en `_resolve_asset_ref`."""
    if request.method not in ("GET", "POST"):
        return _err("Método no permitido (usa GET o POST)", 405)
    root, target, share = _shared_api_target(request, token)

    if request.method == "POST":
        f = request.FILES.get("file")
        if not f:
            return _err("Falta archivo")
        saved = vault.save_upload(root, f, note_path=share.path)
        return JsonResponse({"success": True, "name": saved.name}, status=201)

    content = target.read_text(encoding="utf-8")
    assets = {}
    for ref in _extract_asset_refs(content):
        hit = _resolve_asset_ref(root, ref, share.path)
        if hit:
            assets[hit.name] = ref
    attachments_dir = root / vault.ATTACHMENTS_DIR
    if attachments_dir.is_dir():
        for p in attachments_dir.iterdir():
            if (p.is_file() and p.name not in assets
                    and vault.attachment_owner(root, p) == share.path):
                assets[p.name] = None
    return JsonResponse({"assets": [
        {"name": name, "ref": ref, "url": f"/s/{token}/assets/{name}"}
        for name, ref in assets.items()
    ]})


@csrf_exempt
def shared_note_asset_detail(request, token, name):
    """UN adjunto de la nota de este enlace editable. `GET` descarga sus
    bytes, `DELETE` lo borra — sólo si esta nota es su dueña registrada
    (`vault.attachment_owner`), igual que en `shared_note_assets`. Nunca edita
    el contenido de la nota: si el adjunto seguía referenciado con
    `![[nombre]]`, ese embed se queda roto hasta que la IA lo quite con un
    POST a `shared_note_note`."""
    if request.method not in ("GET", "DELETE"):
        return _err("Método no permitido (usa GET o DELETE)", 405)
    root, _target, share = _shared_api_target(request, token)
    attachments_dir = root / vault.ATTACHMENTS_DIR
    try:
        asset_path = vault.safe_path(attachments_dir, name)
    except VaultError:
        raise Http404
    if not asset_path.is_file() or vault.attachment_owner(root, asset_path) != share.path:
        raise Http404

    if request.method == "DELETE":
        asset_path.unlink()
        return JsonResponse({"success": True})
    content_type, as_attachment = vault.safe_content_type(asset_path.name)
    return FileResponse(open(asset_path, "rb"), content_type=content_type,
                        as_attachment=as_attachment, filename=asset_path.name)
