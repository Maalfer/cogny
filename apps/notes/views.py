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
from django.core.cache import cache
from django.http import FileResponse, Http404, HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.permissions import require_owner, require_write
from apps.core.api import as_int, as_text, error_response as _err, json_body

from . import imagesexport, pdf, themes, vault, worddoc
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
def graph(request):
    return JsonResponse(vault.build_graph(vault.root()))


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


# ════════════ Exportar nota a DOC ════════════

@login_required
@require_POST
@json_body
def notes_doc(request):
    """Documento `.docx` de la nota que el cliente manda ya renderizada.

    Sin tema ni Chromium de por medio (a diferencia de `notes_pdf`): el mismo
    HTML que ya prepara `prepareExportHtml` en el cliente (saneado con el
    mismo saneador que el PDF) se convierte aquí a OOXML nativo — ver el
    docstring de `worddoc.py` para por qué no es un HTML/MHTML con extensión
    `.doc` (las imágenes no sobrevivían). Sin plantilla ni picker de estilos
    antes de descargar: la nota sale con el aspecto por defecto.
    """
    body_html = pdf.sanitize_html(request.data.get("html") or "")
    if not body_html.strip():
        return _err("Nada que exportar")
    display_title = as_text(request.data.get("title")).strip()[:120]
    filename = vault.sanitize_name(display_title or "nota") or "nota"
    doc_bytes = worddoc.render(body_html, title=display_title)
    resp = HttpResponse(
        doc_bytes,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    resp["Content-Disposition"] = f'attachment; filename="{filename}.docx"'
    resp["Content-Length"] = str(len(doc_bytes))
    return resp


# ════════════ Exportar imágenes de la nota a ZIP ════════════

@login_required
@require_POST
@json_body
def notes_images(request):
    """Zip con todas las imágenes de la nota, cada una convertida a `.png`.

    Mismo HTML ya renderizado que `notes_pdf`/`notes_doc` (imágenes del vault
    ya incrustadas como `data:` URI por `prepareExportHtml` en el cliente) —
    ver `imagesexport.py` para por qué se reconvierte todo a PNG en vez de
    conservar el formato original.
    """
    body_html = pdf.sanitize_html(request.data.get("html") or "")
    if not body_html.strip():
        return _err("Nada que exportar")
    display_title = as_text(request.data.get("title")).strip()[:120]
    filename = vault.sanitize_name(display_title or "nota") or "nota"
    try:
        zip_bytes = imagesexport.render_zip(body_html)
    except imagesexport.ImagesExportError as exc:
        return _err(str(exc), exc.status)
    resp = HttpResponse(zip_bytes, content_type="application/zip")
    resp["Content-Disposition"] = f'attachment; filename="{filename}-imagenes.zip"'
    resp["Content-Length"] = str(len(zip_bytes))
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
_SHARE_ASSET_SALT = "cogny.notes.share_asset"

# La extracción de referencias (`![[nombre]]`, `![alt](ruta)`, `<img src>`)
# vive en `vault.extract_asset_refs` — no es nada específico de la vista
# pública, lo reutiliza también el comando de mantenimiento
# `backfill_attachment_owners`.


def _attachment_candidates(attachments_dir: Path) -> list:
    """Ficheros válidos de `Adjuntos/` (filtrados por extensión), en el mismo
    orden de recorrido que `rglob` — construidos en una única pasada por
    disco.

    `_resolve_asset_ref` resolvía el fallback por nombre recorriendo la
    carpeta entera (`rglob`, con su `is_file`/`suffix` por archivo) una vez
    POR REFERENCIA de la nota; con una nota de varias imágenes eso repetía el
    mismo recorrido de miles de ficheros —el coste real son las llamadas a
    disco, no la comparación— varias veces en la misma petición. Quien
    necesite resolver más de una referencia construye esta lista una sola vez
    y la reutiliza.

    Es una lista, no un `dict` indexado por nombre/stem: los nombres de
    adjunto NO son únicos en la bóveda (es una carpeta plana, compartida por
    todas las notas — `1.webp`, `2.webp`... se repiten entre notas distintas
    con total normalidad), así que indexar por nombre forzaría a decidir qué
    archivo "gana" cuando dos coinciden. `_resolve_asset_ref` recorre esta
    lista en orden y se queda con el primero que calce, exactamente el mismo
    desempate que hacía el `rglob` original — importa, porque el siguiente
    paso es comprobar el DUEÑO registrado: si el primer homónimo en orden de
    disco no es de esta nota, no se resuelve, aunque haya otro más abajo en
    la lista que sí lo sea (ese límite ya existía antes de este cambio)."""
    candidates = []
    if not attachments_dir.is_dir():
        return candidates
    for p in attachments_dir.rglob("*"):
        try:
            if p.is_file() and p.suffix.lower() in _SHARE_ASSET_EXTS:
                candidates.append(p)
        except OSError:
            continue
    return candidates


def _resolve_asset_ref(root: Path, ref: str, note_path: str, owners: dict, candidates: list):
    """Resuelve una referencia de embed a un archivo del vault (o None) para
    el enlace PÚBLICO de `note_path`.

    A diferencia de `findFileByName` del cliente (ruta exacta primero, si no
    por nombre en CUALQUIER parte del vault — correcto para un usuario ya
    autenticado, que ya ve la bóveda entera), aquí ni la ruta directa ni el
    fallback por nombre bastan por sí solos: los dos se restringen a
    `Adjuntos/` (fuera de ahí no hay ningún adjunto legítimo, sólo hace falta
    escribir a mano `![alt](OtraCarpeta/archivo.pdf)` para apuntar a
    cualquier cosa) Y, dentro de `Adjuntos/`, el archivo tiene que estar
    registrado como subido para ESTA nota exacta.
    Sin la segunda condición, cualquier adjunto ya existente en la bóveda
    compartida —de cualquier nota, de cualquier usuario— se publicaría con
    sólo nombrarlo desde una nota sin relación real con él; con ella, el
    editor sólo puede compartir públicamente lo que él mismo subió para esta
    nota. Adjuntos anteriores a este control quedan sin dueño registrado a
    propósito: no se resuelven en el enlace público (fail-closed), aunque la
    bóveda autenticada los sigue viendo sin restricción.

    `owners` (mapa completo de `.owners.json`, vía `vault.read_attachment_owners`)
    y `candidates` (vía `_attachment_candidates`) se piden ya construidos —
    y no se recalculan aquí — para que resolver varias referencias en la
    misma petición no releea el disco ni reparsee el JSON una vez por
    referencia (ver el aviso de `vault.attachment_owner` sobre ese mismo
    coste).
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

    if candidate is None:
        base = cleaned.rsplit("/", 1)[-1].lower()
        base_noext = re.sub(r"\.[^.]+$", "", base)
        for p in candidates:
            if p.name.lower() == base or p.stem.lower() == base_noext:
                candidate = p
                break

    if candidate is None:
        return None
    try:
        rel = candidate.relative_to(attachments_dir)
    except ValueError:
        return None
    if owners.get(str(rel).replace("\\", "/")) != note_path:
        return None
    return candidate


def _build_share_assets(root: Path, token: str, content: str, note_path: str):
    """`{ref_original: url_firmada}` sólo para las imágenes/PDFs referenciados
    por ESTA nota — nunca la bóveda entera. El segundo valor devuelto dice si
    hay al menos una IMAGEN entre ellos (a diferencia de un PDF suelto) — lo
    usa la plantilla para mostrar u ocultar el botón de "descargar en .zip"."""
    attachments_dir = root / vault.ATTACHMENTS_DIR
    owners = vault.read_attachment_owners(root)
    candidates = _attachment_candidates(attachments_dir)
    out = {}
    has_images = False
    for ref in vault.extract_asset_refs(content):
        hit = _resolve_asset_ref(root, ref, note_path, owners, candidates)
        if hit:
            rel = vault.rel_of(root, hit)
            sig = quote(signing.dumps({"t": token, "p": rel}, salt=_SHARE_ASSET_SALT), safe="")
            out[ref] = f"/s/{token}/asset?p={sig}"
            if hit.suffix.lower() in vault.IMAGE_EXTS:
                has_images = True
    return out, has_images


def _share_gate_key(token: str) -> str:
    return f"shared_verified_{token}"


# Mismo criterio que `GlobalContextMiddleware._owner_theme` (apps.core.middleware):
# una caché corta evita repetir trabajo de disco en cada petición anónima.
# Aquí el trabajo es la lectura de la nota + resolución de sus adjuntos
# (`_build_share_assets`, que a su vez lee `.owners.json` y recorre
# `Adjuntos/`) — si varias personas abren el mismo enlace a la vez, o la
# misma persona recarga, sólo la primera paga ese coste; el resto, dentro de
# la ventana, se sirve de memoria. El mtime del fichero forma parte de la
# clave: si la nota cambia (enlace editable), la entrada vieja deja de
# encontrarse sola, sin tener que invalidarla a mano.
_SHARE_PAGE_CACHE_TTL = 30


def _shared_page_data(root: Path, token: str, target: Path, note_path: str):
    key = f"cogny:shared_note:{token}:{target.stat().st_mtime_ns}"
    data = cache.get(key)
    if data is None:
        content = target.read_text(encoding="utf-8")
        assets, has_images = _build_share_assets(root, token, content, note_path)
        data = (content, assets, has_images)
        cache.set(key, data, _SHARE_PAGE_CACHE_TTL)
    return data


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

    content, assets, has_images = _shared_page_data(root, token, target, share.path)
    response = render(request, "notes/shared.html", {
        "token": token,
        "note_name": target.stem,
        "content": content,
        # `can_edit`, no `can_write`: ese nombre ya lo pone el contexto global
        # para el rol de la SESIÓN (lo lee `base.html`), y pisarlo aquí haría
        # que la página compartida mintiera sobre quién es quien la mira.
        "can_edit": share.can_write,
        "assets": assets,
        "has_images": has_images,
    })
    if share.can_write:
        # Misma guía que el `<link rel="alternate">` de `shared.html` y el
        # aviso visible del banner, pero como cabecera HTTP: la vía que
        # encuentra una herramienta que inspecciona `curl -I`/headers de la
        # respuesta en vez de parsear el HTML (o en vez de parsear el body,
        # que en este SPA llega vacío sin ejecutar JS).
        llms_url = request.build_absolute_uri(
            reverse("shared_note_llms_txt", args=[token])
        )
        response["Link"] = f'<{llms_url}>; rel="alternate"; type="text/plain"; title="Guia de API para IA"'
    return response


# ── Guía del API en texto plano, pensada para que la lea una IA ─────────────
# Convención `llms.txt`: un fichero de texto plano, pensado para agentes, que
# describe cómo usar el sitio. Aquí va scopeado al token: cada enlace
# editable tiene el suyo, con sus propias URLs ya resueltas (nada de
# plantillas que la IA tenga que rellenar a mano).
#
# A propósito NO exige la contraseña de la nota (a diferencia de
# `_shared_api_target`, que sí la exige para leer o escribir contenido real):
# si no, un enlace con contraseña sería una guía inútil, porque la IA
# necesita leer ESTA guía para enterarse de que primero tiene que autenticarse
# posteando la contraseña. Es el mismo criterio que ya usa
# `shared_gate.html`: la existencia del enlace (y que es editable) no es
# secreta, el CONTENIDO de la nota sí. Por eso tampoco se incluye el nombre
# real de la nota cuando hay contraseña de por medio.
def shared_note_llms_txt(request, token):
    share = SharedNote.objects.filter(token=token, can_write=True).first()
    if not share:
        raise Http404
    root, target = _shared_target(share)

    base = request.build_absolute_uri(f"/s/{token}/")
    gated = bool(share.password_hash) and not request.session.get(_share_gate_key(token))
    note_name = "(nombre oculto hasta introducir la contraseña)" if gated else target.stem

    lines = [
        f"# Guía de API — nota compartida en Cogny",
        f"",
        f"Nota: {note_name}",
        f"Enlace: {base}",
        f"",
        "Si has llegado aquí con sólo este enlace (o el enlace base",
        f"{base}) para leer o editar la nota: usa el API de más abajo con",
        "peticiones HTTP normales (curl, fetch, requests...). NO abras un",
        "navegador, no uses Playwright/Puppeteer/automatización de UI, ni",
        "intentes averiguar a base de prueba y error cómo funciona la",
        "página — todo lo que hace esa interfaz (leer el contenido, guardar",
        "cambios, subir o listar adjuntos) está aquí documentado como texto",
        "plano y es más fiable por API: no depende de JavaScript, de que la",
        "página termine de cargar, ni de clicar en el sitio correcto.",
        "",
        "Este enlace es un token de edición: quien lo tiene puede leer y",
        "reescribir ESTA nota (y sólo esta nota) por HTTP, sin cuenta ni",
        "sesión previa. El token de la URL ES la credencial — no hace falta",
        "ninguna cabecera de autenticación aparte.",
        "",
        "No hay forma de listar la bóveda, ver otras notas, ni renombrar o",
        "borrar esta nota desde este API: sólo leer/escribir su contenido y",
        "gestionar los adjuntos (imágenes, PDFs...) que ESTA nota use o suba.",
        "",
        "## Cómo debe quedar una nota mejorada en este vault",
        "",
        "Lee esto ANTES de reescribir nada, sobre todo si lo que te han pedido",
        "es \"mejorar\"/\"reescribir mejor\" la nota: no es sobre el API, es el",
        "criterio editorial del vault — para que, sin haber visto ninguna otra",
        "nota, puedas dejar ésta al mismo nivel que las ya revisadas.",
        "",
        "Idioma y voz: español, narrado en primera persona del plural, como",
        "quien cuenta lo que \"hicimos\" paso a paso (\"desplegamos\", \"vemos\",",
        "\"interceptamos\", \"entramos\"). Nunca en imperativo de manual",
        "(\"despliega\", \"observa\"): es un cuaderno de quien hizo el laboratorio,",
        "escrito para que otra persona que no sabe nada del tema lo entienda",
        "sin salir de la nota.",
        "",
        "Estructura (es la FORMA a seguir, no una plantilla rígida de huecos —",
        "adapta el número y nombre de las secciones a lo que el contenido",
        "real sea: una cadena de pasos cronológica si es un laboratorio o un",
        "writeup, temática si es una nota conceptual):",
        "",
        "    # <emoji> <Título> — <de dónde viene: DockerLabs / PortSwigger / ...>",
        "",
        "    > [!info] Objetivo (de la práctica / del laboratorio / de la nota)",
        "    > Un párrafo: qué es esto, qué entorno es, qué hay que conseguir y",
        "    > por qué importa. Si hay una meta concreta (un flag, un usuario a",
        "    > borrar, un valor a encontrar), dilo aquí explícitamente.",
        "",
        "    > [!warning] Antes de empezar          (opcional, pero habitual)",
        "    > Que es un entorno de laboratorio/práctica, IPs o dominios",
        "    > ficticios, prerequisitos — lo que el lector deba saber antes de",
        "    > seguir.",
        "",
        "    ---",
        "",
        "    ## 1. <emoji> <Primera sección>",
        "    ## 2. <emoji> <Segunda sección>",
        "    ...",
        "",
        "    ## N. 📋 Resumen          (la última sección, casi siempre)",
        "    Tabla paso/pregunta → respuesta/resultado → por qué, y un",
        "    callout final [!tip] con la idea de fondo más allá de los pasos",
        "    (\"la vista de pájaro\"): qué es lo que de verdad hay que entender.",
        "",
        "    El emoji del título y de cada sección es libre pero relevante al",
        "    tema (💉 inyección, 📧 phishing, 🔌 API, ⏱️ condición de carrera...),",
        "    nunca decorativo porque sí.",
        "",
        "Callouts: úsalos para TODA explicación de un concepto, no sólo para",
        "narrar pasos — es lo que separa un \"log de lo que hice\" de una nota",
        "que enseña. Sintaxis exacta (bloque de cita, el tipo entre corchetes",
        "justo tras `[!` en la primera línea):",
        "",
        "    > [!tip] Título corto de la idea",
        "    > Cuerpo de la explicación, tantas líneas como haga falta, cada",
        "    > una empezando por `> `.",
        "",
        "Los tres que vertebran casi cualquier nota:",
        "  `[!info]`    — qué es esto / objetivo (casi siempre al principio)",
        "  `[!warning]` — avisos, prerequisitos, \"ojo con esto\"",
        "  `[!tip]`     — para parar a explicar UN concepto que el lector",
        "                 puede no conocer (un EventID, una cabecera HTTP, un",
        "                 término técnico...): qué es y, sobre todo, POR QUÉ",
        "                 importa aquí. Es el que más se usa.",
        "Otros tipos reconocidos (icono propio, no uno genérico de relleno):",
        "`note`, `todo`, `abstract`, `summary`, `success`, `check`, `done`,",
        "`question`, `caution`, `attention`, `failure`, `danger`, `error`,",
        "`bug`, `example`, `quote`. Usa sólo nombres de esta lista — uno que",
        "no esté aquí cae en el icono genérico de `info`, así que no inventes",
        "tipos nuevos.",
        "",
        "Reglas que no se negocian:",
        "  - No inventes nada: ni datos, ni resultados, ni capturas que no",
        "    estuvieran ya en el contenido original. El trabajo es reorganizar",
        "    y EXPLICAR mejor lo que ya hay, no añadir hechos nuevos.",
        "  - Conserva TODOS los `![[...]]` (capturas/adjuntos) que ya tenía la",
        "    nota, en el mismo orden relativo en que aparecían — se puede",
        "    mover el texto alrededor de cada una, nunca borrar una captura",
        "    existente ni inventarse una que no exista (ver `GET .../assets`",
        "    más abajo para saber qué adjuntos son de verdad de esta nota).",
        "  - No traduzcas comandos, payloads, URLs, cabeceras HTTP ni código:",
        "    van literales. Lo que se reescribe es la narración alrededor.",
        "  - Cualquier comando, petición o payload va en un bloque de código",
        "    (```bash, ```http, ```json...), nunca suelto en texto corrido.",
        "  - Si algo del original es ambiguo o falta un detalle técnico, no lo",
        "    rellenes a tu criterio: consérvalo tal cual antes que inventar",
        "    precisión que no tienes.",
        "",
        "Antes de hacer el POST final a `.../note`, repasa: ¿sigue estando",
        "cada `![[...]]` original? ¿el título lleva emoji + procedencia?",
        "¿hay un `[!info]` de objetivo? ¿cada concepto no obvio tiene su",
        "`[!tip]`? ¿termina en un resumen? Si todo eso es sí, está lista.",
        "",
    ]

    if share.password_hash:
        lines += [
            "## Paso 0 — esta nota lleva contraseña",
            "",
            "Antes de nada, hay que autenticarse UNA vez y reutilizar la",
            "cookie de sesión que devuelve la respuesta en todas las",
            "peticiones siguientes (igual que un navegador: guarda y reenvía",
            "las cookies con cada petición a partir de aquí).",
            "",
            f"    curl -i -c cookies.txt -b cookies.txt \\",
            f"      --data-urlencode 'password=LA_CONTRASEÑA' \\",
            f"      {base}",
            "",
            "Una respuesta 200 (en vez de volver a pedir la contraseña)",
            "confirma que la sesión quedó autenticada. A partir de aquí, toda",
            "petición de este documento debe mandar esa misma cookie",
            "(`-b cookies.txt` en curl, o el jar de cookies equivalente).",
            "",
        ]

    lines += [
        "## Leer y reescribir el contenido",
        "",
        f"GET  {base}note",
        "  → 200 JSON: {\"path\": ..., \"name\": ..., \"content\": \"...markdown...\"}",
        "",
        f"POST {base}note",
        "  Body JSON: {\"content\": \"...markdown completo...\"}",
        "  → 200 JSON: {\"success\": true, \"updated\": <epoch>}",
        "  Reescribe la nota ENTERA (no es un parche/diff): hay que mandar",
        "  siempre el contenido completo, incluido lo que no cambia. Límite:",
        f"  {vault.MAX_NOTE_BYTES // 1_000_000} MB en UTF-8.",
        "",
        "  Ejemplo:",
        f"    curl -X POST {base}note \\",
        "      -H 'Content-Type: application/json' \\",
        "      -d '{\"content\": \"# Título\\n\\nTexto...\"}'" + ("  -b cookies.txt" if share.password_hash else ""),
        "",
        "## Adjuntos (imágenes, PDFs...) de esta nota",
        "",
        f"GET  {base}assets",
        "  → 200 JSON: {\"assets\": [{\"name\":..., \"ref\": \"...\"|null, \"url\": \"/s/<token>/assets/<name>\"}]}",
        "  Lista los adjuntos que esta nota ya referencia en su markdown",
        "  (`ref` = la referencia tal cual aparece en el texto) MÁS los que",
        "  ya se subieron para esta nota pero aún no se mencionan en el",
        "  contenido (`ref: null`) — útil para no volver a subir uno que ya",
        "  existe.",
        "",
        f"POST {base}assets   (multipart/form-data, campo 'file')",
        "  → 201 JSON: {\"success\": true, \"name\": \"nombre-final.ext\"}",
        "  Sube un archivo nuevo. OJO: el nombre final puede NO ser el que",
        "  mandaste — las imágenes ráster (jpg/png/bmp/tiff) se recodifican",
        "  a .webp automáticamente, y si el nombre ya existe se le añade un",
        "  sufijo. Usa SIEMPRE el 'name' que devuelve la respuesta, no el",
        "  nombre del archivo original, al referenciarlo en el markdown.",
        "",
        "  Ejemplo:",
        f"    curl -X POST {base}assets -F 'file=@captura.png'" + ("  -b cookies.txt" if share.password_hash else ""),
        "",
        f"GET    {base}assets/<nombre>   → descarga ese adjunto",
        f"DELETE {base}assets/<nombre>   → lo borra",
        "  Sólo funciona sobre un adjunto que sea de ESTA nota (uno que ya",
        "  salga en el GET de arriba). Borrar el archivo NO quita sola la",
        "  referencia del markdown: si seguía habiendo un `![[nombre]]` en",
        "  el contenido, hay que quitarlo aparte con un POST a 'note'.",
        "",
        "## Cómo insertar un adjunto en el markdown",
        "",
        "Formato propio del vault (estilo Obsidian), el que ya verás usado",
        "en el contenido existente de la nota:",
        "",
        "    ![[nombre-del-adjunto.webp]]",
        "",
        "También se entienden el markdown estándar (`![alt](nombre.png)`) y",
        "un `<img src=\"nombre.png\">` suelto, pero usa `![[...]]` para ser",
        "coherente con el resto de la nota. El nombre basta (no hace falta",
        "ruta): se resuelve por nombre de archivo entre los adjuntos de esta",
        "nota. Un adjunto subido por otra nota, o que no conste como de esta",
        "nota, NO se resolverá aunque lo nombres bien.",
        "",
        "## Flujo recomendado para un cambio",
        "",
        "1. GET  .../note    — content actual",
        "2. GET  .../assets  — qué adjuntos ya hay (evita subir duplicados)",
        "3. POST .../assets  — sube cada imagen nueva, una por una; anota el",
        "   'name' que devuelva cada una",
        "4. POST .../note    — manda el markdown completo ya editado,",
        "   referenciando los adjuntos con `![[name]]`",
        "",
        "Cualquier endpoint de este documento responde 404 si el token no",
        "existe, si el enlace es de sólo lectura, o (salvo este propio",
        "documento) si la nota lleva contraseña y la sesión aún no la ha",
        "superado.",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")


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
    attachments_dir = root / vault.ATTACHMENTS_DIR
    owners = vault.read_attachment_owners(root)
    candidates = _attachment_candidates(attachments_dir)
    seen_paths = set()
    used_names = set()
    files = []
    for ref in vault.extract_asset_refs(content):
        hit = _resolve_asset_ref(root, ref, share.path, owners, candidates)
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
    attachments_dir = root / vault.ATTACHMENTS_DIR
    # Una sola lectura de `.owners.json` (y un único recorrido de la carpeta)
    # para toda esta vista, no una por archivo/referencia: con la bóveda en
    # varios miles de adjuntos, releer y reparsear el fichero entero dentro
    # de un bucle pasó de milisegundos a minutos (ver el aviso en
    # `vault.attachment_owner`).
    owners = vault.read_attachment_owners(root)
    candidates = _attachment_candidates(attachments_dir)
    assets = {}
    for ref in vault.extract_asset_refs(content):
        hit = _resolve_asset_ref(root, ref, share.path, owners, candidates)
        if hit:
            assets[hit.name] = ref
    if attachments_dir.is_dir():
        for p in attachments_dir.iterdir():
            if p.is_file() and p.name not in assets and owners.get(p.name) == share.path:
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
