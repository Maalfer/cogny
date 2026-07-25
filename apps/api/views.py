"""API pública v1 — control total de la bóveda con una clave de API.

Pensada para consumirse desde fuera del navegador (curl, scripts, un agente
tipo Claude): cubre notas, carpetas, archivos, enlaces compartidos, la bóveda
entera, el perfil y las propias claves.

Reutiliza a propósito los helpers de `apps.notes.views` (`_safe`, `_build_tree`,
`_rel_of`…): son la única implementación de la validación de rutas del vault y
duplicarlos aquí sería la forma más fácil de acabar con dos reglas de seguridad
que divergen.
"""
import base64
import mimetypes
import re
import secrets
import shutil
from pathlib import Path

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.http import FileResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt

from apps.accounts import services as accounts
from apps.accounts.models import ApiKey, User
from apps.core.api import as_int, as_optional_text, as_text
from apps.notes import vault
from apps.notes.models import SharedNote
from apps.notes.vault import VaultError

from .auth import api_view, body_or_query, json_error, owner_only
from .openapi import build_spec


# ════════════ Helpers ════════════

def _resolve(root: Path, rel: str):
    """`(path, None)` o `(None, JsonResponse de error)`."""
    if not (rel or "").strip():
        return None, json_error("Falta el parámetro 'path'")
    try:
        return vault.safe_path(root, rel), None
    except VaultError as exc:
        return None, json_error(str(exc), exc.status)


def _note_info(root: Path, p: Path) -> dict:
    st = p.stat()
    return {
        "path": vault.rel_of(root, p),
        "name": p.stem,
        "folder": vault.rel_of(root, p.parent) if p.parent != root else "",
        "size": st.st_size,
        "updated": int(st.st_mtime),
    }


def _file_info(root: Path, p: Path) -> dict:
    st = p.stat()
    return {
        "path": vault.rel_of(root, p),
        "name": p.name,
        "ext": p.suffix.lower().lstrip("."),
        "size": st.st_size,
        "updated": int(st.st_mtime),
    }


def _int_query(request, name, default, low, high):
    """Entero del querystring, acotado a [low, high]."""
    value = as_int(request.GET.get(name, default))
    return default if value is None else max(low, min(value, high))


def _require_text(request, *names):
    """Valida que los parámetros indicados sean texto. `(valores, error)`."""
    values = []
    for name in names:
        value = body_or_query(request, name)
        if value is not None and not isinstance(value, str):
            return None, json_error(f"'{name}' debe ser texto")
        values.append(value)
    return values, None


def _role_param(request, default):
    """El rol tal cual lo mandó el cliente, o `default` si no lo mandó.

    Devuelve el valor sin normalizar cuando no es texto, para que el validador
    de turno lo rechace con un 400 en vez de degradarlo al rol por defecto.
    """
    return as_optional_text(body_or_query(request, "role"), default)


# ════════════ Meta ════════════

@api_view(methods=("GET",))
def me(request):
    """Quién soy y con qué clave estoy entrando.

    Deliberadamente barato (no recorre el vault): es el endpoint que se usa
    para comprobar que una clave funciona. Los conteos van en `/vault/stats`.
    """
    return JsonResponse({
        "username": request.user.username,
        "theme": request.user.theme,
        "role": request.user.role,
        "can_write": request.user.can_write and not request.api_key.read_only,
        "version": settings.VERSION,
        "docs": request.build_absolute_uri("/api/docs/"),
        "key": accounts.api_key_json(request.api_key),
    })


@csrf_exempt
def not_found(request, *args, **kwargs):
    """404 en JSON para rutas inexistentes bajo `/api/v1/`.

    Sin esto, un typo en la URL devuelve la página HTML de error de Django, que
    un cliente de API no sabe interpretar.
    """
    return JsonResponse({
        "error": f"Endpoint no encontrado: {request.path}",
        "docs": request.build_absolute_uri("/api/docs/"),
    }, status=404)


def openapi(request):
    """Especificación OpenAPI 3.1 (pública: sólo describe la forma de la API)."""
    return JsonResponse(build_spec(request), json_dumps_params={"ensure_ascii": False})


def docs(request):
    """Swagger UI autoalojado (sin CDN)."""
    return render(request, "api/docs.html", {})


def docs_redirect(request):
    """`/api/` a secas lleva a la documentación."""
    return redirect("/api/docs/")


# ════════════ Árbol y notas ════════════

@api_view(methods=("GET",))
def tree(request):
    """Árbol completo de la bóveda (carpetas + notas + archivos)."""
    root = vault.root()
    rel = request.GET.get("path", "")
    start = root
    if rel:
        start, err = _resolve(root, rel)
        if err:
            return err
        if not start.is_dir():
            return json_error("La ruta no es una carpeta", 404)
    return JsonResponse({"path": vault.rel_of(root, start) if start != root else "",
                         "tree": vault.build_tree(root, start)})


@api_view(methods=("GET", "POST", "DELETE"))
def notes(request):
    """GET: lista plana de notas · POST: crear · DELETE: borrar."""
    root = vault.root()

    if request.method == "GET":
        folder = (request.GET.get("folder") or "").strip()
        base = root
        if folder:
            base, err = _resolve(root, folder)
            if err:
                return err
        limit = _int_query(request, "limit", 1000, 1, 20000)
        items, truncated = [], False
        for p in vault.iter_notes(root):
            if base != root and base not in p.parents:
                continue
            if len(items) >= limit:
                truncated = True
                break
            try:
                items.append(_note_info(root, p))
            except OSError:
                continue
        return JsonResponse({"count": len(items), "truncated": truncated, "notes": items})

    if request.method == "POST":
        rel = as_text(body_or_query(request, "path")).strip()
        content = body_or_query(request, "content", "") or ""
        if not isinstance(content, str):
            return json_error("'content' debe ser texto")
        if not rel:
            parent = as_text(body_or_query(request, "parent")).strip()
            name = vault.sanitize_name(body_or_query(request, "name"))
            if not name:
                return json_error("Indica 'path', o bien 'parent' y 'name'")
            rel = f"{parent}/{name}" if parent else name
        if not rel.lower().endswith(".md"):
            rel += ".md"
        target, err = _resolve(root, rel)
        if err:
            return err
        if target.exists():
            return json_error("Ya existe una nota en esa ruta", 409)
        target.parent.mkdir(parents=True, exist_ok=True)
        vault.write_text_atomic(target, content)
        return JsonResponse({"success": True, "note": _note_info(root, target)}, status=201)

    # DELETE
    rel = as_text(body_or_query(request, "path")).strip()
    target, err = _resolve(root, rel)
    if err:
        return err
    if not target.is_file() or target.suffix.lower() != ".md":
        return json_error("Nota no encontrada", 404)
    parent, name = target.parent, target.name
    rel_path = vault.rel_of(root, target)
    target.unlink()
    vault.remove_from_order(parent, name)
    SharedNote.objects.filter(path=rel_path).delete()
    return JsonResponse({"success": True})


@api_view(methods=("GET", "PUT", "POST", "PATCH"))
def note_content(request):
    """GET: leer el Markdown · PUT/POST: sobrescribir · PATCH: editar parcialmente."""
    root = vault.root()

    if request.method == "GET":
        rel = request.GET.get("path", "")
        target, err = _resolve(root, rel)
        if err:
            return err
        if not target.is_file() or target.suffix.lower() != ".md":
            return json_error("Nota no encontrada", 404)
        data = _note_info(root, target)
        data["content"] = target.read_text(encoding="utf-8")
        return JsonResponse(data)

    rel = as_text(body_or_query(request, "path")).strip()
    target, err = _resolve(root, rel)
    if err:
        return err
    if target.suffix.lower() != ".md":
        return json_error("Sólo se permiten archivos .md")

    if request.method in ("PUT", "POST"):
        content = body_or_query(request, "content", "")
        if content is None:
            content = ""
        if not isinstance(content, str):
            return json_error("'content' debe ser texto")
        if len(content.encode("utf-8")) > vault.MAX_NOTE_BYTES:
            return json_error("Nota demasiado grande (máx. 5 MB)", 413)
        # PUT crea la nota si no existe (idempotente); POST exige que exista.
        if not target.is_file() and request.method == "POST":
            return json_error("Nota no encontrada", 404)
        target.parent.mkdir(parents=True, exist_ok=True)
        vault.write_text_atomic(target, content)
        return JsonResponse({"success": True, "note": _note_info(root, target)})

    # PATCH — edición parcial, la forma cómoda para un agente/IA.
    if not target.is_file():
        return json_error("Nota no encontrada", 404)
    current = target.read_text(encoding="utf-8")
    values, err = _require_text(request, "append", "prepend", "find", "replace")
    if err:
        return err
    append, prepend, find, replace = values
    if find is None and append is None and prepend is None:
        return json_error("Indica 'append', 'prepend' o 'find' + 'replace'")

    new = current
    replacements = 0
    if find is not None:
        if replace is None:
            return json_error("'find' necesita 'replace'")
        use_regex = bool(body_or_query(request, "regex", False))
        count = 0 if body_or_query(request, "all", False) else 1
        try:
            if use_regex:
                new, replacements = re.subn(find, replace, new, count=count)
            else:
                replacements = new.count(find) if count == 0 else (1 if find in new else 0)
                new = new.replace(find, replace, -1 if count == 0 else 1)
        except re.error as exc:
            return json_error(f"Expresión regular inválida: {exc}")
        if not replacements:
            return json_error("El texto de 'find' no aparece en la nota", 404)
    if prepend:
        new = f"{prepend}\n{new}" if new and not prepend.endswith("\n") else prepend + new
    if append:
        sep = "" if not new or new.endswith("\n") else "\n"
        new = new + sep + append
    if len(new.encode("utf-8")) > vault.MAX_NOTE_BYTES:
        return json_error("Nota demasiado grande (máx. 5 MB)", 413)
    vault.write_text_atomic(target, new)
    info = _note_info(root, target)
    info["replacements"] = replacements
    return JsonResponse({"success": True, "note": info})


@api_view(methods=("POST",))
def note_rename(request):
    """Renombra una nota (o cualquier elemento) manteniéndola en su carpeta."""
    root = vault.root()
    rel = as_text(body_or_query(request, "path")).strip()
    new_name = vault.sanitize_name(body_or_query(request, "name"))
    if not new_name:
        return json_error("Nombre inválido")
    src, err = _resolve(root, rel)
    if err:
        return err
    if not src.exists():
        return json_error("No existe", 404)
    if src.is_file() and src.suffix.lower() == ".md" and not new_name.endswith(".md"):
        new_name += ".md"
    dst = src.parent / new_name
    if dst.exists() and dst != src:
        return json_error("Ya existe un elemento con ese nombre", 409)
    old_rel, was_dir = vault.rel_of(root, src), src.is_dir()
    src.rename(dst)
    vault.rename_in_order(src.parent, src.name, dst.name)
    new_rel = vault.rel_of(root, dst)
    vault.move_shares(old_rel, new_rel, was_dir)
    return JsonResponse({"success": True, "path": new_rel})


@api_view(methods=("POST",))
def note_move(request):
    """Mueve una nota/carpeta/archivo a otra carpeta."""
    root = vault.root()
    rel = as_text(body_or_query(request, "path")).strip()
    target_rel = as_text(body_or_query(request, "target")).strip()
    src, err = _resolve(root, rel)
    if err:
        return err
    try:
        dst_dir = vault.safe_path(root, target_rel)
    except ValueError as exc:
        return json_error(str(exc))
    if not src.exists() or src == root:
        return json_error("No existe", 404)
    if src == root / "Adjuntos":
        return json_error("La carpeta de adjuntos no se puede mover")
    if not dst_dir.is_dir():
        return json_error("Carpeta destino no encontrada", 404)
    if src.is_dir():
        try:
            dst_dir.relative_to(src)
            return json_error("No se puede mover una carpeta dentro de sí misma")
        except ValueError:
            pass
    if dst_dir == src.parent:
        return JsonResponse({"success": True, "path": vault.rel_of(root, src)})
    dst = dst_dir / src.name
    if dst.exists():
        return json_error("Ya existe un elemento con ese nombre en el destino", 409)
    old_rel, was_dir = vault.rel_of(root, src), src.is_dir()
    shutil.move(str(src), str(dst))
    vault.remove_from_order(src.parent, src.name)
    new_rel = vault.rel_of(root, dst)
    vault.move_shares(old_rel, new_rel, was_dir)
    return JsonResponse({"success": True, "path": new_rel})


@api_view(methods=("POST",))
def note_duplicate(request):
    """Copia una nota junto a la original (con nombre nuevo o ' 2' automático)."""
    root = vault.root()
    rel = as_text(body_or_query(request, "path")).strip()
    src, err = _resolve(root, rel)
    if err:
        return err
    if not src.is_file() or src.suffix.lower() != ".md":
        return json_error("Nota no encontrada", 404)
    name = vault.sanitize_name(body_or_query(request, "name"))
    if name:
        dst = src.parent / (name if name.endswith(".md") else name + ".md")
        if dst.exists():
            return json_error("Ya existe una nota con ese nombre", 409)
    else:
        n = 2
        while (src.parent / f"{src.stem} {n}.md").exists():
            n += 1
        dst = src.parent / f"{src.stem} {n}.md"
    vault.write_text_atomic(dst, src.read_text(encoding="utf-8"))
    return JsonResponse({"success": True, "note": _note_info(root, dst)}, status=201)


@api_view(methods=("GET",))
def search(request):
    """Busca notas que contengan TODOS los términos (case-insensitive)."""
    root = vault.root()
    q = (request.GET.get("q") or "").strip()
    terms = [t.lower() for t in q.split() if t]
    if not terms:
        return json_error("Falta el parámetro 'q'")
    try:
        limit = max(1, min(int(request.GET.get("limit", 50)), 500))
    except ValueError:
        limit = 50
    results = []
    for f in vault.iter_notes(root):
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        low = text.lower()
        if not all(t in low for t in terms):
            continue
        idx = low.find(terms[0])
        info = _note_info(root, f)
        info["snippet"] = text[max(0, idx - 60): idx + 120].replace("\n", " ")
        results.append(info)
        if len(results) >= limit:
            break
    return JsonResponse({"count": len(results), "results": results})


# ════════════ Carpetas ════════════

@api_view(methods=("GET", "POST", "DELETE"))
def folders(request):
    """GET: lista de carpetas · POST: crear · DELETE: borrar (recursivo)."""
    root = vault.root()

    if request.method == "GET":
        out = []
        for p in sorted(root.rglob("*")):
            rel_parts = p.relative_to(root).parts
            try:
                if any(part.startswith(".") for part in rel_parts) or not p.is_dir():
                    continue
                n_notes = sum(1 for c in p.iterdir() if c.suffix.lower() == ".md")
            except OSError:
                continue
            out.append({
                "path": vault.rel_of(root, p),
                "name": p.name,
                "notes": n_notes,
            })
        return JsonResponse({"count": len(out), "folders": out})

    if request.method == "POST":
        rel = as_text(body_or_query(request, "path")).strip()
        if not rel:
            parent = as_text(body_or_query(request, "parent")).strip()
            name = vault.sanitize_name(body_or_query(request, "name"))
            if not name:
                return json_error("Indica 'path', o bien 'parent' y 'name'")
            rel = f"{parent}/{name}" if parent else name
        target, err = _resolve(root, rel)
        if err:
            return err
        if target.exists():
            return json_error("Ya existe una carpeta con esa ruta", 409)
        target.mkdir(parents=True)
        return JsonResponse({"success": True, "path": vault.rel_of(root, target)}, status=201)

    # DELETE
    rel = as_text(body_or_query(request, "path")).strip()
    target, err = _resolve(root, rel)
    if err:
        return err
    if not target.is_dir() or target == root:
        return json_error("Carpeta no encontrada", 404)
    parent, name = target.parent, target.name
    prefix = vault.rel_of(root, target) + "/"
    # Primero el disco y después la BD: si fallara el borrado de la carpeta, con
    # el orden inverso ya habríamos revocado enlaces de notas que siguen ahí.
    # Igual que en `notes` DELETE y en el borrado de la web.
    shutil.rmtree(target)
    vault.remove_from_order(parent, name)
    SharedNote.objects.filter(path__startswith=prefix).delete()
    return JsonResponse({"success": True})


@api_view(methods=("POST",))
def folder_reorder(request):
    """Fija el orden manual de los hijos directos de una carpeta."""
    root = vault.root()
    folder_rel = as_text(body_or_query(request, "folder")).strip()
    order = body_or_query(request, "order")
    if not isinstance(order, list) or not all(isinstance(n, str) for n in order):
        return json_error("'order' debe ser una lista de nombres")
    folder, err = _resolve(root, folder_rel)
    if err:
        return err
    if not folder.is_dir():
        return json_error("Carpeta no encontrada", 404)
    vault.set_order(folder, order)
    return JsonResponse({"success": True})


# ════════════ Archivos / adjuntos ════════════

_MAX_UPLOAD_BYTES = 200 * 1024 * 1024


@api_view(methods=("GET", "POST", "DELETE"))
def files(request):
    """GET: lista de adjuntos · POST: subir · DELETE: borrar."""
    root = vault.root()

    if request.method == "GET":
        base = root
        folder = (request.GET.get("folder") or "").strip()
        if folder:
            base, err = _resolve(root, folder)
            if err:
                return err
        limit = _int_query(request, "limit", 1000, 1, 20000)
        items, truncated = [], False
        for p in vault.iter_files(root):
            if base != root and base not in p.parents:
                continue
            if len(items) >= limit:
                truncated = True
                break
            try:
                items.append(_file_info(root, p))
            except OSError:
                continue
        return JsonResponse({"count": len(items), "truncated": truncated, "files": items})

    if request.method == "POST":
        upload = request.FILES.get("file")
        if upload:
            # Misma rutina que la web: recodifica a WebP si compensa y elige un
            # nombre libre dentro de la carpeta de adjuntos.
            target = vault.save_upload(root, upload)
            return JsonResponse({"success": True, "file": _file_info(root, target),
                                 "embed": f"![[{target.name}]]"}, status=201)
        # Alternativa sin multipart: base64 en JSON (cómodo desde un agente).
        name = vault.sanitize_name(body_or_query(request, "name"))
        b64 = body_or_query(request, "content_base64") or ""
        if not name or not b64:
            return json_error(
                "Sube un fichero multipart en 'file', o pasa 'name' y 'content_base64'")
        try:
            blob = base64.b64decode(b64, validate=True)
        except (ValueError, TypeError):
            return json_error("'content_base64' no es base64 válido")
        if len(blob) > _MAX_UPLOAD_BYTES:
            return json_error("Archivo demasiado grande (máx. 200 MB)", 413)
        folder = as_text(body_or_query(request, "folder"), "Adjuntos").strip() or "Adjuntos"
        target_dir, err = _resolve(root, folder)
        if err:
            return err
        if target_dir.exists() and not target_dir.is_dir():
            return json_error("'folder' apunta a un archivo, no a una carpeta")
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / name
        if target.exists():
            stem, suf = target.stem, target.suffix
            n = 2
            while (target_dir / f"{stem} {n}{suf}").exists():
                n += 1
            target = target_dir / f"{stem} {n}{suf}"
        target.write_bytes(blob)
        return JsonResponse({"success": True, "file": _file_info(root, target),
                             "embed": f"![[{target.name}]]"}, status=201)

    # DELETE
    rel = as_text(body_or_query(request, "path")).strip()
    target, err = _resolve(root, rel)
    if err:
        return err
    if not target.is_file():
        return json_error("Archivo no encontrado", 404)
    if target.suffix.lower() == ".md":
        # Borrar una nota por aquí saltaría la revocación de su enlace público
        # y dejaría el token vivo apuntando a un fichero que ya no existe.
        return json_error("Eso es una nota: bórrala con DELETE /api/v1/notes")
    parent, name = target.parent, target.name
    target.unlink()
    vault.remove_from_order(parent, name)
    return JsonResponse({"success": True})


@api_view(methods=("GET",))
def file_content(request):
    """Descarga el binario de un adjunto."""
    root = vault.root()
    rel = request.GET.get("path", "")
    target, err = _resolve(root, rel)
    if err:
        return err
    if not target.is_file():
        return json_error("Archivo no encontrado", 404)
    ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    return FileResponse(open(target, "rb"), content_type=ctype, filename=target.name)


# ════════════ Enlaces compartidos ════════════

@api_view(methods=("GET", "POST", "DELETE"))
def shares(request):
    """GET: enlaces públicos activos · POST: compartir · DELETE: revocar."""
    root = vault.root()

    if request.method == "GET":
        return JsonResponse({"shares": [{
            "path": s.path,
            "name": Path(s.path).stem,
            "token": s.token,
            "url": request.build_absolute_uri(f"/s/{s.token}/"),
            "has_password": bool(s.password_hash),
            "created_at": s.created_at.isoformat(),
        } for s in SharedNote.objects.all().order_by("-updated_at")]})

    if request.method == "POST":
        rel = as_text(body_or_query(request, "path")).strip()
        password = body_or_query(request, "password") or ""
        if not isinstance(password, str):
            return json_error("'password' debe ser texto")
        target, err = _resolve(root, rel)
        if err:
            return err
        if not target.is_file() or target.suffix.lower() != ".md":
            return json_error("Nota no encontrada", 404)
        rel_path = vault.rel_of(root, target)
        share, _created = SharedNote.objects.get_or_create(
            path=rel_path, defaults={"token": secrets.token_urlsafe(16)})
        share.password_hash = make_password(password) if password else ""
        share.save(update_fields=["password_hash", "updated_at"])
        return JsonResponse({
            "success": True, "token": share.token,
            "url": request.build_absolute_uri(f"/s/{share.token}/"),
            "has_password": bool(share.password_hash),
        })

    # DELETE (por 'path' o por 'token')
    rel = as_text(body_or_query(request, "path")).strip()
    token = as_text(body_or_query(request, "token")).strip()
    if token:
        deleted, _ = SharedNote.objects.filter(token=token).delete()
    elif rel:
        target, err = _resolve(root, rel)
        if err:
            return err
        deleted, _ = SharedNote.objects.filter(path=vault.rel_of(root, target)).delete()
    else:
        return json_error("Indica 'path' o 'token'")
    if not deleted:
        return json_error("Ese enlace no existe", 404)
    return JsonResponse({"success": True})


# ════════════ Bóveda completa ════════════

@api_view(methods=("GET",))
def vault_stats(request):
    """Tamaño y conteos de la bóveda."""
    return JsonResponse({"success": True, **vault.stats(vault.root())})


@api_view(methods=("GET",))
def vault_export(request):
    """Descarga la bóveda entera como ZIP."""
    tmp, size = vault.export_zip(vault.root())
    name = vault.sanitize_name(request.user.username) or "vault"
    resp = FileResponse(tmp, content_type="application/zip")
    resp["Content-Disposition"] = f'attachment; filename="vault-{name}.zip"'
    resp["Content-Length"] = str(size)
    return resp


@api_view(methods=("POST",))
def vault_import(request):
    """Importa un ZIP de bóveda (`mode=merge` por defecto, o `replace`)."""
    upload = request.FILES.get("file")
    if not upload:
        return json_error("Sube el ZIP como fichero multipart en el campo 'file'")
    try:
        vault.import_zip(vault.root(), upload, request.POST.get("mode", "merge"))
    except VaultError as exc:
        return json_error(str(exc), exc.status)
    return JsonResponse({"success": True})


@api_view(methods=("POST",))
def vault_optimize_images(request):
    """Recodifica las imágenes de la bóveda a WebP y devuelve el resumen final.

    La web va pintando los eventos intermedios en una barra de progreso; a un
    cliente de API sólo le sirve el último, así que consumimos el generador
    entero y devolvemos ese.
    """
    last = {}
    for event in vault.optimize_images(vault.root()):
        if event.get("phase") in ("done", "error"):
            last = event
    if last.get("phase") == "error":
        return json_error(last.get("error", "Error optimizando"), 500)
    last.pop("phase", None)   # detalle del stream interno, no del contrato
    return JsonResponse({"success": True, **last})


# ════════════ Perfil ════════════

@api_view(methods=("GET", "PATCH", "POST"))
def profile(request):
    """GET: datos de la cuenta · PATCH/POST: cambiar nombre o tema."""
    user = request.user
    if request.method == "GET":
        return JsonResponse({
            "username": user.username,
            "theme": user.theme,
            "role": user.role,
            "can_write": user.can_write,
            "last_login": user.last_login.isoformat() if user.last_login else None,
            "date_joined": user.date_joined.isoformat(),
        })

    fields = []
    username = as_text(body_or_query(request, "username")).strip()
    theme = as_text(body_or_query(request, "theme"))
    if username:
        error = accounts.validate_username(username, exclude_pk=user.pk)
        if error:
            return json_error(error)
        user.username = username
        fields.append("username")
    if theme:
        if theme not in dict(User.THEME_CHOICES):
            return json_error(
                f"Tema inválido (usa: {', '.join(dict(User.THEME_CHOICES))})")
        user.theme = theme
        fields.append("theme")
    if not fields:
        return json_error("Nada que cambiar: indica 'username' y/o 'theme'")
    user.save(update_fields=fields)
    return JsonResponse({"success": True, "username": user.username, "theme": user.theme})


@api_view(methods=("POST",))
def profile_password(request):
    """Cambia la contraseña de la cuenta (exige la actual)."""
    user = request.user
    current = body_or_query(request, "current_password") or ""
    new = body_or_query(request, "new_password") or ""
    if not user.check_password(current):
        return json_error("Contraseña actual incorrecta", 403)
    error = accounts.validate_new_password(new, user=user)
    if error:
        return json_error(error)
    user.set_password(new)
    user.save()
    return JsonResponse({"success": True})


# ════════════ Accesos invitados ════════════

@api_view(methods=("GET", "POST", "PATCH", "DELETE"))
@owner_only
def users(request):
    """Accesos al sitio: GET listar · POST crear · PATCH cambiar permiso o
    contraseña · DELETE borrar. Exclusivo del propietario."""
    if request.method == "GET":
        return JsonResponse({"users": [accounts.user_json(u) for u in User.objects.all()]})

    if request.method == "POST":
        username = as_text(body_or_query(request, "username")).strip()
        password = as_text(body_or_query(request, "password"))
        # El rol NO cae al valor por defecto si viene con basura: dar un
        # `viewer` en silencio a quien pidió otra cosa es peor que un 400.
        role = _role_param(request, default=User.ROLE_VIEWER)
        error = accounts.validate_new_user(username, password, role)
        if error:
            return json_error(error)
        user = User.objects.create_user(username=username, password=password, role=role)
        return JsonResponse({"success": True, "user": accounts.user_json(user)}, status=201)

    target, error, status = accounts.find_guest(as_int(body_or_query(request, "id")))
    if error:
        return json_error(error, status)

    if request.method == "DELETE":
        accounts.delete_guest(target)
        return JsonResponse({"success": True})

    # PATCH — rol y/o contraseña.
    fields = []
    role = _role_param(request, default=None)
    password = as_text(body_or_query(request, "password"))
    if role is not None:
        if role not in User.GUEST_ROLES:
            return json_error(
                f"Permiso inválido (usa: {', '.join(User.GUEST_ROLES)})")
        target.role = role
        fields.append("role")
    if password:
        error = accounts.validate_new_password(password, user=target)
        if error:
            return json_error(error)
        target.set_password(password)
        fields.append("password")
    if not fields:
        return json_error("Nada que cambiar: indica 'role' y/o 'password'")
    target.save()
    return JsonResponse({"success": True, "user": accounts.user_json(target)})


# ════════════ Claves de API ════════════

@api_view(methods=("GET", "POST"))
@owner_only
def keys(request):
    """GET: lista de claves · POST: crea una nueva (el secreto sólo se ve aquí)."""
    if request.method == "GET":
        return JsonResponse({"keys": [
            accounts.api_key_json(k) for k in ApiKey.objects.filter(user=request.user)]})
    name = as_text(body_or_query(request, "name")).strip()
    read_only = bool(body_or_query(request, "read_only", False))
    key, raw = ApiKey.objects.create_key(request.user, name, read_only=read_only)
    data = accounts.api_key_json(key)
    data["key"] = raw
    return JsonResponse({"success": True, "key": data}, status=201)


@api_view(methods=("DELETE", "POST"))
@owner_only
def key_revoke(request, key_id):
    """Revoca una clave (irreversible; la clave deja de funcionar al instante)."""
    key = ApiKey.objects.filter(pk=key_id, user=request.user).first()
    if not key:
        return json_error("Clave no encontrada", 404)
    key.revoked = True
    key.save(update_fields=["revoked"])
    return JsonResponse({"success": True})
