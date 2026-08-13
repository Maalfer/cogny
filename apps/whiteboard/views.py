"""Vistas de pizarra (sesión + CSRF): páginas y API que consume el frontend.

Mismo reparto que `apps.notes`: aquí sólo la capa HTTP, el disco lo toca
`storage.py`. No hay API v1 (clave de API) para esto de momento — las
pizarras se editan desde el navegador, no tiene sentido de automatización
como sí lo tiene el vault de notas.
"""
import json
import uuid

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, JsonResponse
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
    return FileResponse(open(path, "rb"), content_type="image/png")
