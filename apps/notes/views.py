"""Vistas del vault (sesión + CSRF): las consume el frontend de la web.

Aquí sólo vive la capa HTTP —validar lo que llega, traducir el resultado a
JSON—. Todo lo que toca el disco está en `vault.py` y la exportación a PDF en
`pdf.py`, para que la API v1 (`apps.api.views`) pueda reutilizar exactamente la
misma implementación sin pasar por estas vistas.
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
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.permissions import require_write
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
    return JsonResponse({"success": True, "path": new_rel})


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
    if src == root / vault.ATTACHMENTS_DIR:
        # Los adjuntos cuelgan SIEMPRE de esta ruta fija: moverla no rompe nada
        # (los embeds resuelven por nombre en todo el vault), pero la próxima
        # subida crearía una "Adjuntos" nueva y vacía en la raíz, duplicando la
        # carpeta. El frontend ya no deja arrastrarla; esto cierra el endpoint.
        return _err("La carpeta de adjuntos no se puede mover")
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
    target = vault.save_upload(root, f)
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
    share.save(update_fields=["password_hash", "updated_at"])
    return JsonResponse({
        "success": True, "token": share.token,
        "url": request.build_absolute_uri(f"/s/{share.token}/"),
        "has_password": bool(share.password_hash),
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
    })


@login_required
@require_GET
def share_list(request):
    """Todos los enlaces públicos activos (panel "Enlaces compartidos")."""
    return JsonResponse({"shares": [
        {
            "path": s.path,
            "name": Path(s.path).stem,
            "token": s.token,
            "url": request.build_absolute_uri(f"/s/{s.token}/"),
            "has_password": bool(s.password_hash),
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


def _resolve_asset_ref(root: Path, ref: str):
    """Resuelve una referencia de embed a un archivo del vault (o None).

    A diferencia de `findFileByName` del cliente (ruta exacta primero, si no
    por nombre en CUALQUIER parte del vault — correcto para un usuario ya
    autenticado, que ya ve la bóveda entera), aquí el fallback por nombre se
    restringe a `Adjuntos/`: sin esto, un `![[nombre]]` sin ruta —la sintaxis
    normal de los embeds— filtraría cualquier imagen/PDF de la bóveda con ese
    nombre, viva donde viva, a través del enlace público de una nota sin
    relación real con ella (justo lo que el comentario de `_SHARE_ASSET_EXTS`
    dice evitar). `Adjuntos/` es donde aterrizan todos los adjuntos subidos
    por la vía normal (`vault.save_upload`), así que el caso legítimo sigue
    funcionando; sólo deja de "adivinarse" un adjunto colocado a propósito
    fuera de ahí (p. ej. con `folder` en la API).
    """
    cleaned = ref.replace("\\", "/").split("#")[0].strip().lstrip("./")
    if not cleaned:
        return None
    try:
        direct = vault.safe_path(root, cleaned)
        if direct.is_file() and direct.suffix.lower() in _SHARE_ASSET_EXTS:
            return direct
    except VaultError:
        pass
    base = cleaned.rsplit("/", 1)[-1].lower()
    base_noext = re.sub(r"\.[^.]+$", "", base)
    attachments_dir = root / vault.ATTACHMENTS_DIR
    if not attachments_dir.is_dir():
        return None
    for p in attachments_dir.rglob("*"):
        try:
            if not p.is_file() or p.suffix.lower() not in _SHARE_ASSET_EXTS:
                continue
        except OSError:
            continue
        if p.name.lower() == base or p.stem.lower() == base_noext:
            return p
    return None


def _build_share_assets(root: Path, token: str, content: str) -> dict:
    """`{ref_original: url_firmada}` sólo para las imágenes/PDFs referenciados
    por ESTA nota — nunca la bóveda entera."""
    out = {}
    for ref in _extract_asset_refs(content):
        hit = _resolve_asset_ref(root, ref)
        if hit:
            rel = vault.rel_of(root, hit)
            sig = quote(signing.dumps({"t": token, "p": rel}, salt=_SHARE_ASSET_SALT), safe="")
            out[ref] = f"/s/{token}/asset?p={sig}"
    return out


def _share_gate_key(token: str) -> str:
    return f"shared_verified_{token}"


def shared_note_view(request, token):
    share = SharedNote.objects.filter(token=token).first()
    if not share:
        raise Http404
    root = settings.VAULT_ROOT.resolve()
    try:
        target = vault.safe_path(root, share.path)
    except VaultError:
        raise Http404
    if not target.exists() or target.suffix.lower() != ".md":
        raise Http404

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
    return render(request, "notes/shared.html", {
        "note_name": target.stem,
        "content": content,
        "assets": _build_share_assets(root, token, content),
    })


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
