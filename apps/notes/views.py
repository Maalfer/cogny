"""Vault de notas Markdown por usuario (lectura/escritura sobre disco)."""
import io
import json
import logging
import os
import re
import secrets
import shutil
import zipfile
from pathlib import Path
from urllib.parse import quote

log = logging.getLogger(__name__)

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import check_password, make_password
from django.core import signing
from django.http import (
    FileResponse, Http404, HttpResponse, JsonResponse, StreamingHttpResponse,
)
from django.shortcuts import render
from django.views.decorators.http import require_POST, require_GET

from apps.core.api import error_response as _err
from .models import SharedNote


# ════════════ Helpers ════════════

def _user_root(request) -> Path:
    root = settings.VAULT_ROOT / str(request.user.id)
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


_MAX_PATH_DEPTH = 20


def _safe(root: Path, rel: str) -> Path:
    """Resuelve `rel` relativo a `root` rechazando rutas que escapen el vault.

    Resuelve `root` y `target` para neutralizar symlinks; comparamos por string
    para que la pertenencia siga siendo válida incluso si `target == root`.
    """
    root = root.resolve()
    rel = (rel or "").strip().lstrip("/")
    parts = [p for p in rel.replace("\\", "/").split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        raise ValueError("Ruta inválida")
    if len(parts) > _MAX_PATH_DEPTH:
        raise ValueError("Ruta demasiado profunda")
    target = (root.joinpath(*parts) if parts else root).resolve()
    if target != root and not str(target).startswith(str(root) + os.sep):
        raise ValueError("Ruta fuera del vault")
    return target


def _sanitize_name(name: str) -> str:
    name = (name or "").strip().replace("/", "-").replace("\\", "-")
    name = re.sub(r'[<>:"|?*\x00-\x1f]', "", name).strip(". ")
    return name[:120]


def _rel_of(root: Path, p: Path) -> str:
    return p.resolve().relative_to(root).as_posix()


# ────────── Orden manual de carpetas (drag & drop en el árbol) ──────────
# Cada carpeta puede llevar un `.vaultorder` (oculto, fuera del árbol/export)
# con la lista de nombres de sus hijos directos en el orden elegido por el
# usuario. Los hijos que no aparezcan ahí (recién creados, importados...) se
# añaden al final, ordenados alfabéticamente como hasta ahora.
_ORDER_FILE = ".vaultorder"


def _read_order(directory: Path) -> list:
    f = directory / _ORDER_FILE
    if not f.exists():
        return []
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        return [n for n in (data.get("order") or []) if isinstance(n, str)]
    except (OSError, json.JSONDecodeError, AttributeError):
        return []


def _write_order(directory: Path, order: list) -> None:
    try:
        (directory / _ORDER_FILE).write_text(
            json.dumps({"order": order}, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def _rename_in_order(directory: Path, old_name: str, new_name: str) -> None:
    order = _read_order(directory)
    if old_name in order:
        _write_order(directory, [new_name if n == old_name else n for n in order])


def _remove_from_order(directory: Path, name: str) -> None:
    order = _read_order(directory)
    if name in order:
        _write_order(directory, [n for n in order if n != name])


def _build_tree(root: Path, directory: Path) -> list:
    items = []
    try:
        entries = [e for e in directory.iterdir() if not e.name.startswith(".")]
    except OSError:
        return items
    order = _read_order(directory)
    rank = {name: i for i, name in enumerate(order)}
    ordered = sorted((e for e in entries if e.name in rank), key=lambda e: rank[e.name])
    rest = sorted((e for e in entries if e.name not in rank), key=lambda e: (not e.is_dir(), e.name.lower()))
    for entry in ordered + rest:
        # `stat()` puede fallar si el archivo desapareció entre iterdir y
        # aquí (race condition durante una operación bulk). Lo saltamos.
        try:
            is_dir = entry.is_dir()
            mtime = int(entry.stat().st_mtime) if not is_dir else None
        except OSError:
            continue
        if is_dir:
            items.append({
                "type": "folder", "name": entry.name,
                "path": _rel_of(root, entry),
                "children": _build_tree(root, entry),
            })
        elif entry.suffix.lower() == ".md":
            items.append({
                "type": "note", "name": entry.stem,
                "path": _rel_of(root, entry),
                "updated": mtime,
            })
        else:
            items.append({
                "type": "file", "name": entry.name,
                "ext": entry.suffix.lower().lstrip("."),
                "path": _rel_of(root, entry),
                "updated": mtime,
            })
    return items


# ════════════ Views ════════════

@login_required
def index(request):
    _user_root(request)  # asegura directorio
    return render(request, "notes/notes.html", {})


@login_required
@require_GET
def tree(request):
    root = _user_root(request)
    return JsonResponse({"tree": _build_tree(root, root)})


@login_required
@require_GET
def file_get(request):
    root = _user_root(request)
    rel = request.GET.get("path", "")
    try:
        target = _safe(root, rel)
    except ValueError as e:
        return _err(str(e))
    if not target.exists() or target.suffix.lower() != ".md":
        return _err("Nota no encontrada", 404)
    return JsonResponse({
        "path": _rel_of(root, target),
        "name": target.stem,
        "content": target.read_text(encoding="utf-8"),
    })


@login_required
@require_POST
def file_save(request):
    root = _user_root(request)
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return _err("JSON inválido")
    rel = (data.get("path") or "").strip()
    content = data.get("content")
    if content is None:
        content = ""
    if len(content) > 5_000_000:
        return _err("Nota demasiado grande")
    try:
        target = _safe(root, rel)
    except ValueError as e:
        return _err(str(e))
    if target.suffix.lower() != ".md":
        return _err("Solo se permiten archivos .md")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return JsonResponse({"success": True, "path": _rel_of(root, target),
                          "updated": int(target.stat().st_mtime)})


@login_required
@require_POST
def create(request):
    root = _user_root(request)
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return _err("JSON inválido")
    parent_rel = (data.get("parent") or "").strip()
    name = _sanitize_name(data.get("name") or "")
    kind = data.get("type", "note")
    if not name:
        return _err("Nombre inválido")
    try:
        parent_dir = _safe(root, parent_rel)
    except ValueError as e:
        return _err(str(e))
    parent_dir.mkdir(parents=True, exist_ok=True)
    if kind == "folder":
        target = parent_dir / name
        if target.exists():
            return _err("Ya existe una carpeta con ese nombre")
        target.mkdir()
        return JsonResponse({"success": True, "path": _rel_of(root, target), "type": "folder"})
    fname = name if name.endswith(".md") else name + ".md"
    target = parent_dir / fname
    if target.exists():
        # añadir sufijo numérico
        stem, suf = target.stem, target.suffix
        n = 2
        while (parent_dir / f"{stem} {n}{suf}").exists():
            n += 1
        target = parent_dir / f"{stem} {n}{suf}"
    target.write_text("", encoding="utf-8")
    return JsonResponse({"success": True, "path": _rel_of(root, target), "type": "note"})


@login_required
@require_POST
def rename(request):
    root = _user_root(request)
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return _err("JSON inválido")
    rel = (data.get("path") or "").strip()
    new_name = _sanitize_name(data.get("name") or "")
    if not new_name:
        return _err("Nombre inválido")
    try:
        src = _safe(root, rel)
    except ValueError as e:
        return _err(str(e))
    if not src.exists():
        return _err("No existe", 404)
    if src.is_file() and src.suffix.lower() == ".md" and not new_name.endswith(".md"):
        new_name += ".md"
    dst = src.parent / new_name
    if dst.exists() and dst != src:
        return _err("Ya existe con ese nombre")
    src.rename(dst)
    _rename_in_order(src.parent, src.name, dst.name)
    return JsonResponse({"success": True, "path": _rel_of(root, dst)})


@login_required
@require_POST
def move(request):
    """Mueve una nota/carpeta/archivo a otra carpeta (drag & drop del árbol).

    Solo reubica en el filesystem; el orden dentro de la carpeta destino lo
    fija el frontend con una llamada aparte a `reorder` (conoce la posición
    exacta donde se soltó, cosa que este endpoint no necesita saber).
    """
    root = _user_root(request)
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return _err("JSON inválido")
    rel = (data.get("path") or "").strip()
    target_rel = (data.get("target") or "").strip()
    try:
        src = _safe(root, rel)
        dst_dir = _safe(root, target_rel)
    except ValueError as e:
        return _err(str(e))
    if not src.exists() or src == root:
        return _err("No existe", 404)
    if src == root / "Adjuntos":
        # upload() cuelga SIEMPRE de esta ruta fija (root/"Adjuntos"): moverla de
        # sitio no rompe nada (los embeds resuelven por basename en todo el vault),
        # pero el próximo subir crearía una "Adjuntos" nueva y vacía en la raíz,
        # duplicando la carpeta. El frontend ya no permite arrastrarla; esto es el
        # cierre server-side para quien llame al endpoint directamente.
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
        return JsonResponse({"success": True, "path": _rel_of(root, src)})
    dst = dst_dir / src.name
    if dst.exists():
        return _err("Ya existe un elemento con ese nombre en el destino")
    shutil.move(str(src), str(dst))
    _remove_from_order(src.parent, src.name)
    return JsonResponse({"success": True, "path": _rel_of(root, dst)})


@login_required
@require_POST
def reorder(request):
    """Fija el orden manual de los hijos directos de una carpeta."""
    root = _user_root(request)
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return _err("JSON inválido")
    folder_rel = (data.get("folder") or "").strip()
    order = data.get("order")
    if not isinstance(order, list) or not all(isinstance(n, str) for n in order):
        return _err("Orden inválido")
    try:
        folder = _safe(root, folder_rel)
    except ValueError as e:
        return _err(str(e))
    if not folder.exists() or not folder.is_dir():
        return _err("Carpeta no encontrada", 404)
    # Solo se admiten nombres que existan de verdad en la carpeta (evita que
    # un cliente manipulado escriba basura arbitraria en el .vaultorder).
    existing = {e.name for e in folder.iterdir() if not e.name.startswith(".")}
    _write_order(folder, [n for n in order if n in existing])
    return JsonResponse({"success": True})


@login_required
@require_POST
def delete(request):
    root = _user_root(request)
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return _err("JSON inválido")
    rel = (data.get("path") or "").strip()
    try:
        target = _safe(root, rel)
    except ValueError as e:
        return _err(str(e))
    if not target.exists() or target == root:
        return _err("No existe", 404)
    parent, name = target.parent, target.name
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()
    _remove_from_order(parent, name)
    return JsonResponse({"success": True})


_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff", ".heic", ".avif"}
_NOTE_EXTS = {".md"}


# ════════════ Compartir nota (enlace público, con contraseña opcional) ═════════

@login_required
@require_POST
def share_create(request):
    """Crea (o actualiza) el enlace público de una nota.

    Reutiliza el token existente si la nota ya se había compartido antes, para
    que el enlace no cambie cada vez que se reabre el modal de "Compartir".
    `password` vacío/ausente quita la contraseña; con valor, la (re)establece.
    """
    root = _user_root(request)
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return _err("JSON inválido")
    rel = (data.get("path") or "").strip()
    password = data.get("password") or ""
    try:
        target = _safe(root, rel)
    except ValueError as e:
        return _err(str(e))
    if not target.exists() or target.suffix.lower() != ".md":
        return _err("Nota no encontrada", 404)
    rel_path = _rel_of(root, target)
    share, _created = SharedNote.objects.get_or_create(
        user=request.user, path=rel_path,
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
    root = _user_root(request)
    rel = request.GET.get("path", "")
    try:
        target = _safe(root, rel)
    except ValueError as e:
        return _err(str(e))
    rel_path = _rel_of(root, target)
    share = SharedNote.objects.filter(user=request.user, path=rel_path).first()
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
    """Todos los enlaces públicos activos del usuario (panel "Enlaces compartidos")."""
    shares = SharedNote.objects.filter(user=request.user).order_by("-updated_at")
    return JsonResponse({"shares": [
        {
            "path": s.path,
            "name": Path(s.path).stem,
            "token": s.token,
            "url": request.build_absolute_uri(f"/s/{s.token}/"),
            "has_password": bool(s.password_hash),
        }
        for s in shares
    ]})


@login_required
@require_POST
def share_revoke(request):
    """Deja de compartir una nota (borra el enlace público)."""
    root = _user_root(request)
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return _err("JSON inválido")
    rel = (data.get("path") or "").strip()
    try:
        target = _safe(root, rel)
    except ValueError as e:
        return _err(str(e))
    rel_path = _rel_of(root, target)
    SharedNote.objects.filter(user=request.user, path=rel_path).delete()
    return JsonResponse({"success": True})


# ── Vista pública (sin login) de una nota compartida ────────────────────────

# Sólo imágenes y PDFs se resuelven en la vista pública: los embeds a OTRAS
# notas (![[OtraNota]]) no se exponen (evita que compartir una nota filtre el
# resto de la bóveda por transclusión) y se muestran como "no disponible".
_SHARE_ASSET_EXTS = _IMAGE_EXTS | {".pdf"}
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

    Misma semántica que `findFileByName` del cliente: ruta exacta primero,
    si no por nombre de archivo en cualquier parte del vault.
    """
    cleaned = ref.replace("\\", "/").split("#")[0].strip().lstrip("./")
    if not cleaned:
        return None
    try:
        direct = _safe(root, cleaned)
        if direct.is_file() and direct.suffix.lower() in _SHARE_ASSET_EXTS:
            return direct
    except ValueError:
        pass
    base = cleaned.rsplit("/", 1)[-1].lower()
    base_noext = re.sub(r"\.[^.]+$", "", base)
    for p in root.rglob("*"):
        try:
            if not p.is_file() or p.suffix.lower() not in _SHARE_ASSET_EXTS:
                continue
        except OSError:
            continue
        nlow = p.name.lower()
        if nlow == base or p.stem.lower() == base_noext:
            return p
    return None


def _sign_share_asset(token: str, rel_path: str) -> str:
    return signing.dumps({"t": token, "p": rel_path}, salt=_SHARE_ASSET_SALT)


def _build_share_assets(root: Path, token: str, content: str) -> dict:
    """`{ref_original: url_firmada}` sólo para las imágenes/PDFs referenciados
    por ESTA nota — nunca la bóveda entera."""
    out = {}
    for ref in _extract_asset_refs(content):
        hit = _resolve_asset_ref(root, ref)
        if hit:
            rel = _rel_of(root, hit)
            sig = quote(_sign_share_asset(token, rel), safe="")
            out[ref] = f"/s/{token}/asset?p={sig}"
    return out


def _share_gate_key(token: str) -> str:
    return f"shared_verified_{token}"


def shared_note_view(request, token):
    share = SharedNote.objects.filter(token=token).select_related("user").first()
    if not share:
        raise Http404
    root = (settings.VAULT_ROOT / str(share.user_id)).resolve()
    try:
        target = _safe(root, share.path)
    except ValueError:
        raise Http404
    if not target.exists() or target.suffix.lower() != ".md":
        raise Http404

    gate_key = _share_gate_key(token)
    error = ""
    if share.password_hash:
        if request.method == "POST":
            password = request.POST.get("password", "")
            if check_password(password, share.password_hash):
                request.session[gate_key] = True
            else:
                error = "Contraseña incorrecta"
        if not request.session.get(gate_key):
            return render(request, "notes/shared_gate.html", {"error": error})

    content = target.read_text(encoding="utf-8")
    assets = _build_share_assets(root, token, content)
    return render(request, "notes/shared.html", {
        "note_name": target.stem,
        "content": content,
        "assets": assets,
        "owner_username": share.user.username,
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
    root = (settings.VAULT_ROOT / str(share.user_id)).resolve()
    try:
        target = _safe(root, data.get("p", ""))
    except ValueError:
        raise Http404
    if not target.exists() or target.is_dir():
        raise Http404
    return FileResponse(open(target, "rb"))


@login_required
@require_GET
def storage(request):
    """Devuelve estadísticas de la bóveda: total, desglose y conteos."""
    root = _user_root(request)
    total_bytes = 0
    notes_bytes = 0
    images_bytes = 0
    other_bytes = 0
    n_notes = 0
    n_images = 0
    n_other = 0
    n_folders = 0
    for p in root.rglob("*"):
        try:
            if p.is_dir():
                if not p.name.startswith("."):
                    n_folders += 1
                continue
            size = p.stat().st_size
        except OSError:
            continue
        total_bytes += size
        ext = p.suffix.lower()
        if ext in _NOTE_EXTS:
            notes_bytes += size; n_notes += 1
        elif ext in _IMAGE_EXTS:
            images_bytes += size; n_images += 1
        else:
            other_bytes += size; n_other += 1
    return JsonResponse({
        "success": True,
        "total_bytes": total_bytes,
        "notes_bytes": notes_bytes,
        "images_bytes": images_bytes,
        "other_bytes": other_bytes,
        "n_notes": n_notes,
        "n_images": n_images,
        "n_other": n_other,
        "n_folders": n_folders,
    })


@login_required
@require_POST
def optimize_images(request):
    """Recodifica imágenes ráster de la bóveda a WebP, in-place.

    Devuelve una respuesta de tipo NDJSON (una línea JSON por evento) para
    que el frontend pinte la barra de progreso en tiempo real:

      {"phase":"scan"}
      {"phase":"start","total":N}
      {"phase":"progress","i":k,"total":N,"name":"...","converted":c,"skipped":s,"saved_bytes":b}
      {"phase":"rewriting","notes":M}
      {"phase":"done","converted":...,"skipped":...,"saved_bytes":...}

    En caso de error fatal: {"phase":"error","error":"..."}
    """
    import io
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return _err("Pillow no instalado", 500)
    root = _user_root(request)

    def jline(obj):
        return (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")

    def stream():
        yield jline({"phase": "scan"})
        # Lista de candidatas (ráster, no-webp/gif/svg/ico).
        candidates = []
        try:
            for p in root.rglob("*"):
                try:
                    if not p.is_file():
                        continue
                except OSError:
                    continue
                ext = p.suffix.lower()
                if ext in {".webp", ".gif", ".svg", ".ico"}:
                    continue
                if ext not in _IMAGE_EXTS:
                    continue
                candidates.append(p)
        except OSError as exc:
            yield jline({"phase": "error", "error": f"Error escaneando: {exc}"})
            return

        total = len(candidates)
        yield jline({"phase": "start", "total": total})

        converted = skipped = saved_bytes = 0
        renames = []

        for i, img_path in enumerate(candidates, start=1):
            try:
                orig_size = img_path.stat().st_size
                with img_path.open("rb") as fp:
                    img = Image.open(fp); img.load()
                img = ImageOps.exif_transpose(img)
                if img.mode not in ("RGB", "RGBA"):
                    img = img.convert("RGBA" if "A" in img.mode else "RGB")
                buf = io.BytesIO()
                img.save(buf, "WEBP", quality=85, method=6)
                new_data = buf.getvalue()
            except Exception:
                skipped += 1
                yield jline({"phase": "progress", "i": i, "total": total,
                             "name": img_path.name, "converted": converted,
                             "skipped": skipped, "saved_bytes": saved_bytes})
                continue
            if len(new_data) >= orig_size:
                skipped += 1
                yield jline({"phase": "progress", "i": i, "total": total,
                             "name": img_path.name, "converted": converted,
                             "skipped": skipped, "saved_bytes": saved_bytes})
                continue
            new_path = img_path.with_suffix(".webp")
            if new_path.exists() and new_path != img_path:
                n = 2
                while img_path.with_name(f"{img_path.stem} {n}.webp").exists():
                    n += 1
                new_path = img_path.with_name(f"{img_path.stem} {n}.webp")
            try:
                new_path.write_bytes(new_data)
                if new_path != img_path:
                    try:
                        img_path.unlink()
                    except OSError as exc:
                        log.warning("optimize: unlink %s falló: %s", img_path, exc)
            except OSError as exc:
                log.warning("optimize: write %s falló: %s", new_path, exc)
                skipped += 1
                yield jline({"phase": "progress", "i": i, "total": total,
                             "name": img_path.name, "converted": converted,
                             "skipped": skipped, "saved_bytes": saved_bytes})
                continue
            saved_bytes += orig_size - len(new_data)
            converted += 1
            renames.append((img_path.name, new_path.name))
            # Yield cada 5 imágenes para no inundar el wire (~10/s típico).
            if i % 5 == 0 or i == total:
                yield jline({"phase": "progress", "i": i, "total": total,
                             "name": img_path.name, "converted": converted,
                             "skipped": skipped, "saved_bytes": saved_bytes})

        # Reescribir referencias en notas: sólo dentro de embeds ![[nombre]]
        # (la sintaxis que usa esta app para insertar imágenes), no un
        # replace ciego que podría corromper prosa que mencione el mismo
        # nombre de archivo por coincidencia.
        if renames:
            rename_patterns = [
                (re.compile(r"(?<=!\[\[)" + re.escape(old_name) + r"(?=[|\]])"), new_name)
                for old_name, new_name in renames if old_name != new_name
            ]
            md_files = list(root.rglob("*.md"))
            yield jline({"phase": "rewriting", "notes": len(md_files)})
            for md in md_files:
                try:
                    text = md.read_text(encoding="utf-8")
                except OSError:
                    continue
                new_text = text
                for pattern, new_name in rename_patterns:
                    new_text = pattern.sub(new_name, new_text)
                if new_text != text:
                    try:
                        md.write_text(new_text, encoding="utf-8")
                    except OSError as exc:
                        log.warning("optimize: write md %s falló: %s", md, exc)

        yield jline({"phase": "done", "converted": converted,
                     "skipped": skipped, "saved_bytes": saved_bytes})

    resp = StreamingHttpResponse(stream(), content_type="application/x-ndjson")
    resp["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp["X-Accel-Buffering"] = "no"   # nginx: no bufferizar (flush inmediato)
    return resp


@login_required
@require_GET
def search(request):
    root = _user_root(request)
    q = (request.GET.get("q") or "").strip()
    terms = [t.lower() for t in q.split() if t]
    if not terms:
        return JsonResponse({"results": []})
    results = []
    for f in root.rglob("*.md"):
        try:
            text = f.read_text(encoding="utf-8")
        except Exception:
            continue
        low = text.lower()
        if not all(t in low for t in terms):
            continue
        # snippet
        idx = low.find(terms[0])
        snippet = text[max(0, idx - 40): idx + 80].replace("\n", " ")
        results.append({
            "path": _rel_of(root, f), "name": f.stem,
            "snippet": snippet,
            "updated": int(f.stat().st_mtime),
        })
        if len(results) >= 50:
            break
    return JsonResponse({"results": results})


@login_required
@require_POST
def upload(request):
    """Sube un asset (imagen u otro) a la bóveda del usuario.

    Si es una imagen rasterizada (jpg/png/bmp/tiff/heic/jpeg), la
    recodificamos a WebP para reducir peso (~30-50%) preservando calidad.
    Animados (gif), vectoriales (svg) y formatos sin Pillow soporte se
    guardan tal cual. WebP ya optimizado también se guarda sin recodificar.
    """
    root = _user_root(request)
    f = request.FILES.get("file")
    if not f:
        return _err("Falta archivo")
    # Todos los assets se guardan SIEMPRE en "Adjuntos" (se ignora el parámetro
    # "dir" del cliente). La nota inserta la referencia como ![[nombre]], que
    # resuelve por basename global, así que la ubicación física no afecta al
    # renderizado y mantenemos todas las imágenes centralizadas.
    target_dir = root / "Adjuntos"
    target_dir.mkdir(parents=True, exist_ok=True)

    fname = _sanitize_name(f.name)
    optimized_bytes, new_ext = _maybe_to_webp(f)

    if new_ext:
        # Cambiamos la extensión al .webp resultante.
        stem = Path(fname).stem or "imagen"
        fname = f"{stem}.webp"

    target = target_dir / fname
    if target.exists():
        stem, suf = target.stem, target.suffix
        n = 2
        while (target_dir / f"{stem} {n}{suf}").exists():
            n += 1
        target = target_dir / f"{stem} {n}{suf}"

    if optimized_bytes is not None:
        target.write_bytes(optimized_bytes)
    else:
        with open(target, "wb") as fp:
            for chunk in f.chunks():
                fp.write(chunk)
    return JsonResponse({
        "success": True,
        "name": target.name,
        "path": _rel_of(root, target),
    })


# Formatos que NO recodificamos a WebP (anim/vectorial/icono/ya-webp).
_KEEP_AS_IS = {".gif", ".svg", ".ico", ".webp"}


def _maybe_to_webp(uploaded_file):
    """Devuelve `(bytes_optimizados, '.webp')` si conviene recodificar, o
    `(None, None)` si dejamos el archivo tal cual.

    No re-codifica si:
    - El archivo no es una imagen reconocible por Pillow.
    - Es una extensión que mantenemos sin tocar (`_KEEP_AS_IS`).
    - El WebP resultante quedaría MAYOR que el original.
    """
    import io
    ext = Path(uploaded_file.name or "").suffix.lower()
    if ext in _KEEP_AS_IS or ext not in _IMAGE_EXTS:
        # No es una extensión de imagen ráster reconocida (pdf, zip, docx...):
        # nos ahorramos leer el archivo entero en memoria sólo para que
        # Pillow falle al abrirlo.
        return None, None
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return None, None
    try:
        # Leer en memoria. Para imágenes muy grandes, Pillow ya gestiona
        # streaming interno; aquí asumimos que entran en RAM (típico < 20 MB).
        data = b"".join(uploaded_file.chunks())
        img = Image.open(io.BytesIO(data))
        # Respetar rotación EXIF antes de re-codificar.
        img = ImageOps.exif_transpose(img)
        # Convertir paletas/CMYK a RGB(A) para WebP.
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA" if "A" in img.mode else "RGB")
        buf = io.BytesIO()
        img.save(buf, "WEBP", quality=85, method=6)
        out = buf.getvalue()
        if len(out) >= len(data):
            return None, None
        return out, ".webp"
    except Exception:
        # Si Pillow no entiende el formato, guardamos el archivo original.
        return None, None


@login_required
@require_GET
def asset(request):
    root = _user_root(request)
    rel = request.GET.get("path", "")
    try:
        target = _safe(root, rel)
    except ValueError:
        raise Http404
    if not target.exists() or target.is_dir():
        raise Http404
    return FileResponse(open(target, "rb"))


@login_required
@require_GET
def export_vault(request):
    root = _user_root(request)
    # Escribimos a un fichero temporal en disco (no a BytesIO): para vaults
    # de cientos de MB evita mantener el ZIP entero en RAM por duplicado
    # (una vez al construirlo, otra vez al leerlo con getvalue()).
    # TemporaryFile no deja rastro en disco: el hueco se libera solo al
    # cerrarse, incluso si el proceso muere a medias.
    tmp = _tempfile.TemporaryFile()
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in root.rglob("*"):
            if f.is_file() and not any(p.startswith(".") for p in f.parts):
                zf.write(f, arcname=str(f.relative_to(root)))
    size = tmp.tell()
    tmp.seek(0)
    resp = FileResponse(tmp, content_type="application/zip")
    fname = _sanitize_name(request.user.username) or "vault"
    resp["Content-Disposition"] = f'attachment; filename="vault-{fname}.zip"'
    resp["Content-Length"] = str(size)
    return resp


# Tope de tamaño descomprimido por importación: generoso para vaults reales
# (unos pocos GB de notas+imágenes) pero evita que un ZIP bomb llene el disco.
_MAX_IMPORT_UNCOMPRESSED = 2 * 1024 ** 3


@login_required
@require_POST
def import_vault(request):
    root = _user_root(request)
    f = request.FILES.get("file")
    if not f:
        return _err("Falta archivo")
    mode = request.POST.get("mode", "merge")
    try:
        with zipfile.ZipFile(f, "r") as zf:
            members = [info for info in zf.infolist() if not info.is_dir()]
            total_uncompressed = sum(info.file_size for info in members)
            if total_uncompressed > _MAX_IMPORT_UNCOMPRESSED:
                return _err("El ZIP supera el tamaño máximo permitido al descomprimir")
            # Valida TODAS las rutas (misma regla que el resto de endpoints:
            # sin ".." y con profundidad acotada) antes de tocar el disco, para
            # no dejar una importación a medias si una entrada es inválida.
            try:
                targets = [(info, _safe(root, info.filename)) for info in members]
            except ValueError as e:
                return _err(f"Ruta inválida en el ZIP ({e})")

            if mode == "replace":
                for it in root.iterdir():
                    if it.name.startswith("."): continue
                    if it.is_dir(): shutil.rmtree(it)
                    else: it.unlink()
            for info, target in targets:
                target.parent.mkdir(parents=True, exist_ok=True)
                with open(target, "wb") as fp:
                    fp.write(zf.read(info))
    except zipfile.BadZipFile:
        return _err("ZIP inválido")
    return JsonResponse({"success": True})


# ════════════ Exportar nota a PDF (Chromium headless) ════════════
import subprocess as _subprocess
import tempfile as _tempfile

import glob as _glob
from html import escape as _html_escape
from html.parser import HTMLParser as _HTMLParser


# Etiquetas sin uso legítimo en el HTML ya renderizado de una nota (no las
# genera marked/KaTeX/Mermaid/highlight.js): se eliminan junto a su contenido.
_UNSAFE_TAGS = {"script", "iframe", "object", "embed", "link", "meta", "base", "applet", "form"}

# html.parser pone en minúsculas todo nombre de etiqueta/atributo, pero SVG
# (que Mermaid genera embebido en el HTML de la nota) es sensible a
# mayúsculas en varios nombres — sin restaurarlos, cosas como viewBox o
# foreignObject dejan de surtir efecto y el diagrama se renderiza mal.
# Tablas de "ajuste" de SVG del propio estándar HTML5 (recortadas a los
# nombres que sí tienen mayúsculas; el resto ya sobrevive intacto).
_SVG_TAG_CASE = {t.lower(): t for t in (
    "altGlyph", "altGlyphDef", "altGlyphItem", "animateColor", "animateMotion",
    "animateTransform", "clipPath", "feBlend", "feColorMatrix",
    "feComponentTransfer", "feComposite", "feConvolveMatrix", "feDiffuseLighting",
    "feDisplacementMap", "feDistantLight", "feDropShadow", "feFlood", "feFuncA",
    "feFuncB", "feFuncG", "feFuncR", "feGaussianBlur", "feImage", "feMerge",
    "feMergeNode", "feMorphology", "feOffset", "fePointLight", "feSpecularLighting",
    "feSpotLight", "feTile", "feTurbulence", "foreignObject", "glyphRef",
    "linearGradient", "radialGradient", "textPath",
)}
_SVG_ATTR_CASE = {a.lower(): a for a in (
    "attributeName", "attributeType", "baseFrequency", "calcMode", "clipPath",
    "clipPathUnits", "diffuseConstant", "edgeMode", "filterUnits", "glyphRef",
    "gradientTransform", "gradientUnits", "kernelMatrix", "kernelUnitLength",
    "keyPoints", "keySplines", "keyTimes", "lengthAdjust", "limitingConeAngle",
    "markerHeight", "markerUnits", "markerWidth", "maskContentUnits", "maskUnits",
    "numOctaves", "pathLength", "patternContentUnits", "patternTransform",
    "patternUnits", "pointsAtX", "pointsAtY", "pointsAtZ", "preserveAlpha",
    "preserveAspectRatio", "primitiveUnits", "refX", "refY", "repeatCount",
    "repeatDur", "requiredExtensions", "requiredFeatures", "specularConstant",
    "specularExponent", "spreadMethod", "startOffset", "stdDeviation",
    "stitchTiles", "surfaceScale", "systemLanguage", "tableValues", "targetX",
    "targetY", "textLength", "viewBox", "viewTarget", "xChannelSelector",
    "yChannelSelector", "zoomAndPan",
)}
# Atributos que pueden apuntar a un recurso: sólo se permiten esquemas inofensivos
# (http/https/mailto/data:image), rutas relativas o fragmentos (#ancla).
_URI_ATTRS = {"src", "href", "xlink:href", "action", "formaction"}
_SAFE_URI_RE = re.compile(r"^(https?:|mailto:|data:image/|#|/|[^:]*$)", re.IGNORECASE)


class _NoteHTMLSanitizer(_HTMLParser):
    """Sanitiza el HTML de una nota antes de imprimirlo a PDF.

    Es una lista de bloqueo (no de permiso): el contenido renderizado incluye
    demasiadas etiquetas/atributos legítimos (KaTeX, Mermaid-SVG, highlight.js)
    como para enumerarlos todos sin arriesgarse a romper el renderizado. En su
    lugar neutralizamos los vectores concretos: handlers on*, iframes/objects/
    scripts, y cualquier URI que no sea http(s)/mailto/data:image/relativa
    (bloquea en particular `file://`, que con Chromium en modo headless podría
    leer notas de otros usuarios o el .env del servidor).
    """

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.out = []
        self._skip_depth = 0

    def _clean_attrs(self, attrs):
        cleaned = []
        for name, value in attrs:
            lname = name.lower()
            if lname.startswith("on"):
                continue
            if lname in _URI_ATTRS and value and not _SAFE_URI_RE.match(value.strip()):
                continue
            cleaned.append((_SVG_ATTR_CASE.get(lname, name), value))
        return cleaned

    def _emit_start(self, tag, attrs, self_closing):
        if tag in _UNSAFE_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        tag = _SVG_TAG_CASE.get(tag, tag)
        attr_str = "".join(
            f' {n}="{_html_escape(v, quote=True)}"' if v is not None else f" {n}"
            for n, v in self._clean_attrs(attrs)
        )
        self.out.append(f"<{tag}{attr_str}{' /' if self_closing else ''}>")

    def handle_starttag(self, tag, attrs):
        self._emit_start(tag, attrs, self_closing=False)

    def handle_startendtag(self, tag, attrs):
        self._emit_start(tag, attrs, self_closing=True)

    def handle_endtag(self, tag):
        if tag in _UNSAFE_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth:
            return
        self.out.append(f"</{_SVG_TAG_CASE.get(tag, tag)}>")

    def handle_data(self, data):
        if not self._skip_depth:
            self.out.append(data)

    def handle_entityref(self, name):
        if not self._skip_depth:
            self.out.append(f"&{name};")

    def handle_charref(self, name):
        if not self._skip_depth:
            self.out.append(f"&#{name};")

    # Comentarios, doctype y processing instructions se descartan sin más
    # (no aportan nada al HTML ya renderizado de una nota).


def _sanitize_note_html(raw: str) -> str:
    parser = _NoteHTMLSanitizer()
    parser.feed(raw or "")
    parser.close()
    return "".join(parser.out)


def _resolve_chromium():
    """Resuelve un binario Chromium que funcione para imprimir a PDF.

    El paquete `chromium` de Debian (v150, actualizado 2026-07-06) crashea
    en modo headless en este servidor (SIGTRAP / `trap int3` al arrancar,
    independientemente de los flags), lo que rompía la exportación a PDF.
    Preferimos el `chrome-headless-shell` que Playwright deja cacheado: es
    self-contained, está fijado a una versión y funciona de forma fiable.
    Si no hay ninguno, caemos al chromium del sistema como último recurso.
    """
    patterns = [
        "/home/mario/.cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-linux*/chrome-headless-shell",
        "/root/.cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-linux*/chrome-headless-shell",
    ]
    for pat in patterns:
        # Versión más alta primero (orden lexicográfico inverso sobre el nº de build).
        for hit in sorted(_glob.glob(pat), reverse=True):
            if os.access(hit, os.X_OK):
                return hit
    return shutil.which("chromium") or shutil.which("chromium-browser") or "/usr/bin/chromium"


_CHROMIUM_BIN = _resolve_chromium()


_PDF_CSS_CACHE = None


def _pdf_styles():
    # Combina (y cachea) las hojas necesarias para el PDF, leidas de disco:
    # notes_print.css + highlight + KaTeX (con las fuentes reescritas a file://).
    # Asi el documento es 100% local (sin red), que es lo unico fiable con
    # Chromium headless --single-process ejecutado por www-data.
    global _PDF_CSS_CACHE
    if _PDF_CSS_CACHE is not None:
        return _PDF_CSS_CACHE
    sroot = str(settings.STATIC_ROOT)

    def _read(rel):
        try:
            with open(os.path.join(sroot, rel), encoding="utf-8") as fh:
                return fh.read()
        except OSError:
            return ""

    parts = [_read("notes/notes_print.css"), _read("vendor/highlight-github-dark.min.css")]
    katex = _read("vendor/katex/katex.min.css")
    if katex:
        fonts_dir = os.path.join(sroot, "vendor", "katex", "fonts") + "/"
        katex = katex.replace("url(fonts/", "url(file://" + fonts_dir)
        parts.append(katex)
    _PDF_CSS_CACHE = "\n".join(p for p in parts if p)
    return _PDF_CSS_CACHE


@login_required
@require_POST
def notes_pdf(request):
    # Genera un PDF de la nota renderizada. El cliente envia el HTML ya
    # renderizado (con imagenes incrustadas como data-URI); aqui lo envolvemos en
    # un documento autonomo y lo imprimimos a PDF con Chromium headless,
    # devolviendolo como descarga. Funciona igual en movil y escritorio.
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return _err("JSON invalido")
    body_html = _sanitize_note_html(data.get("html") or "")
    if not body_html.strip():
        return _err("Nada que exportar")
    title = _sanitize_name(data.get("title") or "nota") or "nota"
    dark = bool(data.get("dark"))
    body_class = "markdown-body print-dark" if dark else "markdown-body"

    doc = (
        '<!doctype html><html><head><meta charset="utf-8"><style>'
        + _pdf_styles() +
        '</style></head><body class="' + body_class + '">' + body_html + '</body></html>'
    )

    workdir = _tempfile.mkdtemp(prefix="notepdf_")
    try:
        in_html = os.path.join(workdir, "in.html")
        out_pdf = os.path.join(workdir, "out.pdf")
        with open(in_html, "w", encoding="utf-8") as fh:
            fh.write(doc)
        cmd = [
            _CHROMIUM_BIN, "--headless", "--no-sandbox", "--disable-gpu",
            "--disable-dev-shm-usage", "--disable-crash-reporter", "--disable-breakpad",
            "--no-zygote", "--single-process", "--allow-file-access-from-files",
            # El HTML ya viene renderizado (KaTeX/Mermaid/highlight corrieron en
            # el cliente); Chromium sólo necesita maquetar e imprimir, no
            # ejecutar JS. Esto neutraliza cualquier handler on*/script que se
            # hubiera colado pese al saneado de _sanitize_note_html.
            "--disable-javascript",
            "--user-data-dir=" + os.path.join(workdir, "ud"),
            "--no-pdf-header-footer", "--virtual-time-budget=8000",
            "--print-to-pdf=" + out_pdf, "file://" + in_html,
        ]
        env = dict(os.environ, HOME=workdir)
        try:
            _subprocess.run(cmd, env=env, timeout=60,
                            stdout=_subprocess.DEVNULL, stderr=_subprocess.DEVNULL)
        except _subprocess.TimeoutExpired:
            return _err("Tiempo agotado generando el PDF", 504)
        except FileNotFoundError:
            return _err("Chromium no disponible en el servidor", 500)
        if not os.path.exists(out_pdf) or os.path.getsize(out_pdf) == 0:
            return _err("No se pudo generar el PDF", 500)
        with open(out_pdf, "rb") as fh:
            pdf_bytes = fh.read()
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    resp = HttpResponse(pdf_bytes, content_type="application/pdf")
    resp["Content-Disposition"] = 'attachment; filename="' + title + '.pdf"'
    resp["Content-Length"] = str(len(pdf_bytes))
    return resp
