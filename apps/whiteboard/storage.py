"""Todo lo que toca disco para las pizarras: escena JSON (elementos + estado +
ficheros incrustados de Excalidraw) y miniatura PNG. El `Board` en `models.py`
es sólo el índice; el contenido pesado vive aquí, igual que las notas cuelgan
de ficheros `.md` en `apps.notes.vault` y no de la BD.
"""
import base64
import binascii
import json
import os
import re
from pathlib import Path

from django.conf import settings

# Tope generoso: una pizarra con muchas imágenes incrustadas (guardadas como
# dataURL dentro de la propia escena) puede pesar varios MB, pero un límite
# evita que un cliente manipulado llene el disco con una sola petición.
MAX_SCENE_BYTES = 25_000_000
MAX_THUMB_BYTES = 3_000_000

_THUMB_DATA_URL_RE = re.compile(r"^data:image/png;base64,(.+)$", re.DOTALL)


def root() -> Path:
    r = Path(settings.WHITEBOARD_ROOT)
    r.mkdir(parents=True, exist_ok=True)
    return r


def _write_bytes_atomic(path: Path, data: bytes) -> None:
    """Mismo patrón que `vault.write_text_atomic`: temporal en el mismo
    directorio + `os.replace`, para que un corte a medio guardado nunca deje
    un fichero corrupto."""
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_bytes(data)
        os.replace(tmp, path)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise


def scene_path(board_id) -> Path:
    return root() / f"{board_id}.json"


def thumb_path(board_id) -> Path:
    return root() / f"{board_id}.png"


EMPTY_SCENE = {"elements": [], "appState": {}, "files": {}}


def read_scene(board_id) -> dict:
    path = scene_path(board_id)
    if not path.exists():
        return dict(EMPTY_SCENE)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return dict(EMPTY_SCENE)
    if not isinstance(data, dict):
        return dict(EMPTY_SCENE)
    return {
        "elements": data.get("elements") if isinstance(data.get("elements"), list) else [],
        "appState": data.get("appState") if isinstance(data.get("appState"), dict) else {},
        "files": data.get("files") if isinstance(data.get("files"), dict) else {},
    }


def write_scene(board_id, elements, app_state, files) -> None:
    payload = json.dumps(
        {"elements": elements, "appState": app_state, "files": files},
        ensure_ascii=False,
    )
    if len(payload.encode("utf-8")) > MAX_SCENE_BYTES:
        raise ValueError("Pizarra demasiado grande (máx. 25 MB)")
    _write_bytes_atomic(scene_path(board_id), payload.encode("utf-8"))


def write_thumb(board_id, data_url: str) -> None:
    """Decodifica una dataURL `image/png` (la exporta el propio Excalidraw en
    el cliente) y la escribe como miniatura de la pizarra."""
    m = _THUMB_DATA_URL_RE.match(data_url or "")
    if not m:
        raise ValueError("Miniatura inválida")
    try:
        raw = base64.b64decode(m.group(1), validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("Miniatura inválida")
    if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Miniatura inválida")
    if len(raw) > MAX_THUMB_BYTES:
        raise ValueError("Miniatura demasiado grande")
    _write_bytes_atomic(thumb_path(board_id), raw)


def delete_board_files(board_id) -> None:
    scene_path(board_id).unlink(missing_ok=True)
    thumb_path(board_id).unlink(missing_ok=True)
