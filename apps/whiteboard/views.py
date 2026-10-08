"""Vistas de pizarra (sesión + CSRF): páginas y API que consume el frontend.

Mismo reparto que `apps.notes`: aquí sólo la capa HTTP, el disco lo toca
`storage.py`. Las pizarras se editan desde el navegador, no existe API
pública sin sesión.
"""
import json
import re
import uuid

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.permissions import require_write
from apps.core.api import as_text, error_response as _err, json_body

from . import storage
from .models import Board


def _board_or_404(raw_id):
    try:
        board_id = uuid.UUID(as_text(raw_id) or str(raw_id))
    except (ValueError, AttributeError, TypeError):
        raise Http404
    return get_object_or_404(Board, pk=board_id)


# ════════════ Páginas ════════════

@login_required
def gallery(request):
    return render(request, "whiteboard/gallery.html", {})


@login_required
def editor(request, board_id):
    board = get_object_or_404(Board, pk=board_id)
    scene = storage.read_scene(board.id)
    boot_json = json.dumps({
        "id": str(board.id),
        "name": board.name,
        "scene": scene,
    }, ensure_ascii=False)
    # El contenido de la escena lo escribe el usuario (texto de formas, nombres
    # de ficheros incrustados...) y viaja embebido dentro de un <script>: un
    # "</script>" ahí dentro cerraría la etiqueta antes de tiempo y el resto se
    # parsearía como HTML. `\/` es un escape válido en JSON (equivale a `/`),
    # así que esto no cambia el JSON, sólo impide que el parser de HTML lo lea
    # como cierre de la etiqueta.
    boot_json = boot_json.replace("</", "<\\/")
    return render(request, "whiteboard/editor.html", {
        "board": board,
        "boot_json": boot_json,
    })


# ════════════ API ════════════

@login_required
@require_GET
def list_boards(request):
    return JsonResponse({"boards": [
        {
            "id": str(b.id),
            "name": b.name,
            "updated_at": int(b.updated_at.timestamp()),
            "thumb_url": f"/api/pizarra/thumb?id={b.id}" if b.has_thumb else None,
        }
        for b in Board.objects.all()
    ]})


@login_required
@require_write
@require_POST
@json_body
def create(request):
    name = as_text(request.data.get("name")).strip()[:120] or "Sin título"
    board = Board.objects.create(name=name, created_by=request.user)
    storage.write_scene(board.id, [], {}, {})
    return JsonResponse({"success": True, "id": str(board.id)})


@login_required
@require_write
@require_POST
@json_body
def rename(request):
    board = _board_or_404(request.data.get("id"))
    name = as_text(request.data.get("name")).strip()[:120]
    if not name:
        return _err("Nombre inválido")
    board.name = name
    board.save(update_fields=["name", "updated_at"])
    return JsonResponse({"success": True, "name": board.name})


@login_required
@require_write
@require_POST
@json_body
def duplicate(request):
    src = _board_or_404(request.data.get("id"))
    copy = Board.objects.create(name=f"{src.name} (copia)", created_by=request.user)
    scene = storage.read_scene(src.id)
    storage.write_scene(copy.id, scene["elements"], scene["appState"], scene["files"])
    if src.has_thumb:
        try:
            storage.thumb_path(copy.id).write_bytes(storage.thumb_path(src.id).read_bytes())
            copy.has_thumb = True
            copy.save(update_fields=["has_thumb"])
        except OSError:
            pass
    return JsonResponse({"success": True, "id": str(copy.id)})


@login_required
@require_write
@require_POST
@json_body
def delete(request):
    board = _board_or_404(request.data.get("id"))
    storage.delete_board_files(board.id)
    board.delete()
    return JsonResponse({"success": True})


@login_required
@require_write
@require_POST
@json_body
def scene_save(request):
    board = _board_or_404(request.data.get("id"))
    elements = request.data.get("elements")
    app_state = request.data.get("appState")
    files = request.data.get("files")
    if not isinstance(elements, list) or not isinstance(app_state, dict) or not isinstance(files, dict):
        return _err("Datos de escena inválidos")
    try:
        storage.write_scene(board.id, elements, app_state, files)
    except ValueError as exc:
        return _err(str(exc))
    board.save(update_fields=["updated_at"])  # bump `updated_at` sin tocar el nombre
    return JsonResponse({"success": True, "updated_at": int(board.updated_at.timestamp())})


@login_required
@require_write
@require_POST
@json_body
def thumb_save(request):
    board = _board_or_404(request.data.get("id"))
    try:
        storage.write_thumb(board.id, request.data.get("dataUrl") or "")
    except ValueError as exc:
        return _err(str(exc))
    if not board.has_thumb:
        board.has_thumb = True
        board.save(update_fields=["has_thumb"])
    return JsonResponse({"success": True})


@login_required
@require_GET
def thumb(request):
    board = _board_or_404(request.GET.get("id"))
    path = storage.thumb_path(board.id)
    if not board.has_thumb or not path.exists():
        raise Http404
    # Sin validadores (ETag/Last-Modified) el archivo cambia bajo la misma
    # URL cada vez que se edita el lienzo — sin esto el navegador puede
    # servir de caché una miniatura vieja al volver a la galería.
    resp = FileResponse(open(path, "rb"), content_type="image/png")
    resp["Cache-Control"] = "no-store"
    return resp



@login_required
@require_write
@require_POST
@json_body
def pdf_export(request):
    """Exporta la pizarra actual a PDF.

    El cliente (board.js) ya pinta el lienzo en un canvas off-screen con el
    mismo codigo que la miniatura de la galeria (`drawElementOn`), exporta
    ese canvas como PNG dataURL con el `bgColor` ya horneado, y lo manda
    aqui con `{id, dataUrl, landscape?}`. Aqui se imprime a PDF via
    `pdf.render_image()`, que reutiliza la misma infraestructura headless
    que `pdf.render()` para notas (Chromium con CSP, proxy validador y
    workdir en `/var`).

    El nombre lo leemos del modelo, no del cuerpo: el cliente lo manda
    informativo pero la fuente de verdad es la BD (mismo patron que el
    `Content-Disposition` del export de notas: si el cliente miente sobre
    el nombre, gana la BD).
    """
    from apps.notes import pdf as notes_pdf

    # Validación ANTES de levantar Chromium: si falla algo del input, 400
    # (error del cliente), no 500 (error del servidor). `render_image()`
    # también valida por su cuenta, pero con status 500 por defecto — la
    # barrera útil para el cliente es esta, que distingue las dos cosas.
    raw_id = request.data.get("id")
    if not raw_id:
        return _err("Falta el id de la pizarra")
    board = _board_or_404(raw_id)
    data_url = request.data.get("dataUrl") or ""
    if not isinstance(data_url, str) or not data_url.startswith("data:image/png;base64,"):
        return _err("dataUrl no es un PNG valido")
    if len(data_url) > notes_pdf._IMG_MAX_PNG_BYTES:
        return _err("Imagen demasiado grande")
    # La validación de magic-bytes también la hace `render_image()`, pero
    # hacerla aquí separa "input inválido" (400) de "fallo del servidor"
    # (502) — sin esto, bytes que no son PNG cruzan la frontera como 502
    # cuando el cliente claramente nos ha mandado algo que no es una imagen.
    try:
        import base64 as _b64
        head = _b64.b64decode(data_url.split(",", 1)[1], validate=True)[:8]
    except (binascii.Error, ValueError):
        return _err("Imagen no valida")
    if head != b"\x89PNG\r\n\x1a\n":
        return _err("Imagen no valida")
    landscape = bool(request.data.get("landscape"))

    try:
        pdf_bytes = notes_pdf.render_image(data_url, title=board.name, landscape=landscape)
    except notes_pdf.PdfError as exc:
        # Cualquier PdfError que sobreviva a la validación previa es un
        # fallo del servidor (Chromium no disponible, timeout, etc.) — 500.
        return _err(str(exc), exc.status if exc.status != 500 else 502)
    except Exception:
        import traceback as _tb
        with open("/tmp/pdf_export_traceback.log", "a") as _f:
            _tb.print_exc(file=_f)
        raise

    filename = _sanitize_filename(board.name) or "pizarra"
    resp = HttpResponse(pdf_bytes, content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="{filename}.pdf"'
    resp["Content-Length"] = str(len(pdf_bytes))
    return resp


_FILENAME_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _sanitize_filename(name) -> str:
    """Nombre de fichero saneado para el Content-Disposition (pizarras).

    Mismo criterio que `vault.sanitize_name`: rechaza separadores y
    caracteres de control, recorta puntos/espacios al principio y al final
    (los navegadores y Windows se quejan de ".." o " .pdf") y limita a
    120 chars para que `<filename>.pdf` quepa en cualquier FS.
    """
    if not isinstance(name, str):
        return ""
    n = _FILENAME_RE.sub("", name).strip(". ")
    return n[:120]
