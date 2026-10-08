"""Capa de acceso a la bóveda: todo lo que toca el disco vive aquí.

Las notas no están en la BD, son ficheros `.md` bajo `settings.VAULT_ROOT`. Este
módulo concentra las reglas de ese sistema de ficheros —validación de rutas,
orden manual de carpetas, escritura atómica, import/export, optimización de
imágenes— separadas de la capa HTTP (`apps.notes.views`) para que no haya que
llamar a una *vista* ya decorada con `@login_required` sólo para reutilizar
una operación.

Nada de aquí conoce `HttpRequest` ni devuelve respuestas: se comunica con
valores de Python y, cuando algo va mal de una forma que el usuario debe leer,
levanta `VaultError` con el mensaje ya redactado.
"""
import fcntl
import io
import json
import logging
import os
import re
import shutil
import tempfile
import uuid
import zipfile
from pathlib import Path

from django.conf import settings
from django.db import transaction

from .models import SharedNote

log = logging.getLogger(__name__)


class VaultError(ValueError):
    """Error de bóveda con un mensaje ya apto para enseñar al usuario.

    Hereda de `ValueError` a propósito: las rutas inválidas se venían tratando
    así desde el principio y quien haga `except ValueError` sigue funcionando.
    """

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


# ── Límites ──────────────────────────────────────────────────────────────────

# Tope por nota, en BYTES (no en caracteres: con acentos y emojis una nota de
# 5M de caracteres ocupa el doble en disco).
MAX_NOTE_BYTES = 5_000_000

MAX_PATH_DEPTH = 20

# Tope de tamaño descomprimido por importación: generoso para vaults reales
# (unos pocos GB de notas+imágenes) pero evita que un ZIP bomb llene el disco.
MAX_IMPORT_UNCOMPRESSED = 2 * 1024 ** 3

# Fichero de lock (flock) que serializa las importaciones en modo "replace"
# de una misma bóveda: ver el comentario en import_zip().
_IMPORT_LOCK_NAME = ".import.lock"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff", ".heic", ".avif"}
NOTE_EXTS = {".md"}

# Formatos que NO recodificamos a WebP (animados/vectoriales/iconos/ya-webp).
KEEP_AS_IS = {".gif", ".svg", ".ico", ".webp"}

# Carpeta fija donde aterrizan todos los adjuntos subidos desde la web.
ATTACHMENTS_DIR = "Adjuntos"

# Registro (fichero JSON dentro de Adjuntos/) de qué nota subió cada adjunto.
# Sólo lo consulta la resolución de assets para el enlace PÚBLICO (ver
# `_resolve_asset_ref` en views.py): la bóveda autenticada sigue viendo todos
# los adjuntos sin restricción, por diseño. Adjuntos previos a este control
# quedan sin dueño registrado a propósito (`attachment_owner` -> None).
_ATTACHMENT_OWNERS_FILE = ".owners.json"
_ATTACHMENT_OWNERS_LOCK = ".owners.lock"

# `sanitize_name` no filtra la extensión (cualquier editor puede subir un
# .html/.js) y `save_upload` guarda tal cual lo que Pillow no reconoce como
# imagen, así que aquí es donde se decide qué se sirve para renderizar en el
# navegador y qué se fuerza a descargar — lo decide `apps.notes.views.asset`,
# la única vista que devuelve un adjunto. Sólo las imágenes rasterizadas y el
# PDF son inertes al navegarlos directamente; el Content-Type se fija a mano
# en vez de fiarse de `mimetypes.guess_type`, para que un adjunto no pueda
# hacerse pasar por otra cosa.
_INLINE_CONTENT_TYPES = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
    ".ico": "image/x-icon", ".tiff": "image/tiff", ".heic": "image/heic",
    ".avif": "image/avif", ".pdf": "application/pdf",
}
# El SVG es una imagen legítima (se usa en <img>, que nunca ejecuta su script
# embebido) pero, navegado directamente, es un documento con su propio
# contexto de scripting: se sirve con el Content-Type correcto para que siga
# funcionando como <img>, pero forzando descarga en acceso directo.
_SVG_CONTENT_TYPE = "image/svg+xml"


def safe_content_type(filename: str):
    """`(content_type, as_attachment)` seguros para servir `filename` como adjunto."""
    ext = Path(filename).suffix.lower()
    if ext == ".svg":
        return _SVG_CONTENT_TYPE, True
    if ext in _INLINE_CONTENT_TYPES:
        return _INLINE_CONTENT_TYPES[ext], False
    return "application/octet-stream", True


# ── Rutas ────────────────────────────────────────────────────────────────────

def root() -> Path:
    """Raíz de la bóveda, creada si aún no existe."""
    vault_root = settings.VAULT_ROOT
    vault_root.mkdir(parents=True, exist_ok=True)
    return vault_root.resolve()


def safe_path(base: Path, rel) -> Path:
    """Resuelve `rel` relativo a `base` rechazando rutas que escapen la bóveda.

    Resuelve `base` y `target` para neutralizar symlinks; comparamos por string
    para que la pertenencia siga siendo válida incluso si `target == base`.

    Cada segmento se recorta de espacios (`" vía /tr.md"` -> `"vía/tr.md"`), no
    sólo los extremos de la ruta completa: si no se hiciera, una nota creada con
    un espacio final justo antes de una "/" (p.ej. pegando un título con espacio
    de más) deja en disco una carpeta intermedia con espacio final en el nombre.
    Esa carpeta se sigue listando con normalidad (`iterdir`/`rglob` no filtran
    por nombre), pero cualquier operación posterior que reciba la ruta por API
    -incluido su propio borrado- pasa por `.strip()` sobre la ruta completa
    (ej. en la vista de carpetas), que sólo recorta el espacio si cae en el
    extremo de toda la cadena; en cuanto ese segmento deja de ser el último
    (o la comparación no hace ese strip), el nombre ya no coincide con el que
    hay en disco y la carpeta queda huérfana e imposible de referenciar por
    nombre — vacía o no.
    """
    base = base.resolve()
    rel = (rel if isinstance(rel, str) else "").strip().lstrip("/")
    parts = [p for p in
             (segment.strip() for segment in rel.replace("\\", "/").split("/"))
             if p not in ("", ".")]
    if any(p == ".." for p in parts):
        raise VaultError("Ruta inválida")
    if len(parts) > MAX_PATH_DEPTH:
        raise VaultError("Ruta demasiado profunda")
    target = (base.joinpath(*parts) if parts else base).resolve()
    if target != base and not str(target).startswith(str(base) + os.sep):
        raise VaultError("Ruta fuera del vault")
    return target


def sanitize_name(name) -> str:
    """Nombre de fichero/carpeta seguro a partir de lo que mandó el cliente."""
    # Acepta cualquier cosa: el nombre viene del cliente y un número aquí
    # reventaría el `.strip()` con un 500 en vez de dar un "nombre inválido".
    name = (name if isinstance(name, str) else "").strip().replace("/", "-").replace("\\", "-")
    name = re.sub(r'[<>:"|?*\x00-\x1f]', "", name).strip(". ")
    return name[:120]


def rel_of(base: Path, p: Path) -> str:
    """Ruta de `p` relativa a la bóveda, en formato POSIX (la que ve el cliente)."""
    return p.resolve().relative_to(base).as_posix()


def free_path(directory: Path, stem: str, suffix: str) -> Path:
    """`stem+suffix` dentro de `directory`, añadiendo ' 2', ' 3'… si ya existe."""
    target = directory / f"{stem}{suffix}"
    n = 2
    while target.exists():
        target = directory / f"{stem} {n}{suffix}"
        n += 1
    return target


def write_text_atomic(path: Path, content: str) -> None:
    """Escribe un fichero de texto sin poder dejarlo a medias.

    `write_text` trunca primero y escribe después: si el disco se llena o el
    proceso muere en esa ventana, la nota queda vacía o cortada y el contenido
    anterior ya no existe. Aquí escribimos a un temporal en el MISMO directorio
    (para que `os.replace` sea un rename dentro del mismo sistema de ficheros, y
    por tanto atómico) y lo movemos encima: o se ve la versión vieja entera, o
    la nueva entera, nunca un híbrido.

    El temporal empieza por '.', así que si algo lo dejara huérfano no aparece
    en el árbol ni en el export (ambos filtran los nombres ocultos).

    No hacemos `fsync`: protege del corte de corriente, pero cuesta una escritura
    a disco en cada autoguardado. El fallo realista aquí (disco lleno, proceso
    muerto) ya lo cubre `os.replace`.
    """
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise


# ── Orden manual de carpetas (drag & drop en el árbol) ───────────────────────
# Cada carpeta puede llevar un `.vaultorder` (oculto, fuera del árbol/export)
# con la lista de nombres de sus hijos directos en el orden elegido por el
# usuario. Los hijos que no aparezcan ahí (recién creados, importados...) se
# añaden al final, ordenados alfabéticamente como hasta ahora.

ORDER_FILE = ".vaultorder"


def read_order(directory: Path) -> list:
    f = directory / ORDER_FILE
    if not f.exists():
        return []
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        return [n for n in (data.get("order") or []) if isinstance(n, str)]
    # UnicodeDecodeError no es OSError (hereda de ValueError): un `.vaultorder`
    # con bytes no-UTF-8 -p.ej. plantado por una importación de ZIP, que
    # escribe el contenido tal cual sin validar codificación- se colaba sin
    # capturar y build_tree(), al ser recursivo, propagaba el fallo de esa
    # única carpeta (por profunda que estuviera) hasta romper el árbol
    # completo de la bóveda para todos los usuarios.
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, AttributeError):
        return []


def write_order(directory: Path, order: list) -> None:
    try:
        write_text_atomic(directory / ORDER_FILE,
                          json.dumps({"order": order}, ensure_ascii=False))
    except OSError:
        pass


def set_order(folder: Path, order: list) -> None:
    """Fija el orden de una carpeta, quedándose sólo con los nombres reales.

    Filtrar contra el contenido de la carpeta evita que un cliente manipulado
    escriba basura arbitraria en el `.vaultorder`.
    """
    existing = {e.name for e in folder.iterdir() if not e.name.startswith(".")}
    write_order(folder, [n for n in order if n in existing])


def rename_in_order(directory: Path, old_name: str, new_name: str) -> None:
    order = read_order(directory)
    if old_name in order:
        write_order(directory, [new_name if n == old_name else n for n in order])


def remove_from_order(directory: Path, name: str) -> None:
    order = read_order(directory)
    if name in order:
        write_order(directory, [n for n in order if n != name])


# ── Notas y carpetas privadas (invisibles desde /conocimiento) ───────────────
# A diferencia del orden (que es por carpeta), la privacidad es una propiedad
# de la nota que no depende de en qué carpeta esté en cada momento: un único
# fichero oculto en la RAÍZ de la bóveda, con la lista de rutas marcadas,
# evita reescribir un `.private` por carpeta cada vez que la nota se mueve.
# Sólo afecta a la bóveda pública (`apps.knowledge`); dentro de Cogny con
# sesión la nota se ve exactamente igual que cualquier otra.
#
# La lista mezcla notas y CARPETAS, y la marca de una carpeta se HEREDA: todo
# lo que cuelga de ella queda privado sin escribir una ruta por nota (si no,
# crear una nota dentro de una carpeta ya marcada la publicaría sin querer, y
# mover mil notas obligaría a reescribir mil entradas). Por eso la marca
# propia y la heredada se guardan por separado: quitar la de la carpeta
# devuelve a cada nota su propio estado anterior en vez de publicarlas todas.

PRIVATE_FILE = ".private.json"
# Bloqueo dedicado para el read-modify-write de `.private.json`: a diferencia
# de `.vaultorder` (uno por carpeta, colisión rara), este fichero es GLOBAL y
# lo toca cualquier rename/move/delete de la bóveda entera además del propio
# toggle — con `--workers 2 --threads 4` en gunicorn, dos peticiones que
# mutan a la vez (p.ej. borrar una nota mientras se marca otra como privada)
# perderían en silencio la escritura de la que llega segunda sin este
# candado. Mismo patrón que `_record_attachment_owner` usa para
# `.owners.json`, que tiene exactamente el mismo problema.
_PRIVATE_LOCK = ".private.lock"


def read_private(base: Path) -> set:
    f = base / PRIVATE_FILE
    if not f.exists():
        return set()
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        return {p for p in (data.get("paths") or []) if isinstance(p, str)}
    # Mismo criterio de tolerancia que `read_order`: un fichero corrupto no
    # debe romper el árbol entero, sólo dejar de ocultar nada por esta vez.
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, AttributeError):
        return set()


def write_private(base: Path, paths: set) -> None:
    try:
        write_text_atomic(base / PRIVATE_FILE,
                          json.dumps({"paths": sorted(paths)}, ensure_ascii=False))
    except OSError:
        pass


def marked_private(private_paths: set, rel_path: str) -> bool:
    """¿`rel_path` está oculto por su propia marca o por la de una carpeta que
    lo contiene? Trabaja sobre un set ya leído para poder preguntarlo muchas
    veces (árbol, búsqueda) sin releer `.private.json` en cada elemento.
    """
    if rel_path in private_paths:
        return True
    return any(rel_path.startswith(p + "/") for p in private_paths)


def is_private(base: Path, rel_path: str) -> bool:
    return marked_private(read_private(base), rel_path)


def _mutate_private(base: Path, mutate) -> None:
    """Aplica `mutate(paths) -> (paths_nuevo, changed)` con exclusión mutua.

    `mutate` recibe el set actual y devuelve el que hay que guardar (o el
    mismo, sin tocar, si `changed` es False) — todo el read-modify-write
    ocurre con el lock tomado, así que dos llamadas concurrentes nunca se
    pisan la una a la otra.
    """
    lock_fp = open(base / _PRIVATE_LOCK, "a")
    try:
        fcntl.flock(lock_fp, fcntl.LOCK_EX)
        paths, changed = mutate(read_private(base))
        if changed:
            write_private(base, paths)
    finally:
        fcntl.flock(lock_fp, fcntl.LOCK_UN)
        lock_fp.close()


def set_private(base: Path, rel_path: str, private: bool) -> None:
    """Marca (o desmarca) una nota o una carpeta entera.

    Al desmarcar una carpeta NO se tocan las marcas de lo que hay dentro: una
    nota que ya era privada por su cuenta antes de marcar la carpeta lo sigue
    siendo después, que es justo lo que espera quien marcó la carpeta "un
    rato" para esconder una rama entera.
    """
    def mutate(paths):
        before = len(paths)
        if private:
            paths.add(rel_path)
        else:
            paths.discard(rel_path)
        return paths, len(paths) != before
    _mutate_private(base, mutate)


def rename_private(base: Path, old_rel: str, new_rel: str, is_dir: bool) -> None:
    """Reapunta la marca de privacidad tras renombrar o mover `old_rel`.

    Sólo se marcan notas sueltas, pero una nota privada puede vivir dentro de
    una carpeta que se renombra o se mueve: hay que reescribir también el
    prefijo de cualquier ruta marcada que cuelgue de ella (mismo criterio que
    `move_shares` usa para `SharedNote`).
    """
    def mutate(paths):
        changed = False
        if old_rel in paths:
            paths.discard(old_rel)
            paths.add(new_rel)
            changed = True
        if is_dir:
            prefix = old_rel + "/"
            for p in [p for p in paths if p.startswith(prefix)]:
                paths.discard(p)
                paths.add(new_rel + "/" + p[len(prefix):])
                changed = True
        return paths, changed
    _mutate_private(base, mutate)


def drop_private(base: Path, rel_path: str, is_dir: bool) -> None:
    """Quita la marca de privacidad de lo que se acaba de borrar."""
    def mutate(paths):
        before = len(paths)
        paths.discard(rel_path)
        if is_dir:
            prefix = rel_path + "/"
            paths = {p for p in paths if not p.startswith(prefix)}
        return paths, len(paths) != before
    _mutate_private(base, mutate)


# ── Enlaces públicos ─────────────────────────────────────────────────────────

def move_shares(old_rel: str, new_rel: str, is_dir: bool) -> None:
    """Reapunta los enlaces públicos tras renombrar o mover.

    El enlace vive en la BD asociado a una `path` del vault, así que mover el
    fichero sin tocar la fila deja el enlace apuntando a la nada (404 silencioso
    para quien ya lo tuviera). Con una carpeta hay que reescribir además el
    prefijo de todas las notas compartidas que cuelgan de ella.
    """
    # En transacción: mover una carpeta puede tocar N filas y quedarse a medias
    # dejaría unos enlaces apuntando al sitio nuevo y otros al viejo.
    with transaction.atomic():
        SharedNote.objects.filter(path=old_rel).update(path=new_rel)
        if not is_dir:
            return
        old_prefix = old_rel + "/"
        for share in SharedNote.objects.filter(path__startswith=old_prefix):
            share.path = new_rel + "/" + share.path[len(old_prefix):]
            share.save(update_fields=["path", "updated_at"])


def rewrite_attachment_owners(base: Path, old_rel: str, new_rel: str, is_dir: bool) -> None:
    """Reapunta `Adjuntos/.owners.json` tras renombrar o mover `old_rel`.

    Sin esto, una nota renombrada deja de ser la "dueña" registrada de sus
    propias imágenes (ver `attachment_owner`): el enlace público compartido
    sigue funcionando, pero cada `![[...]]` se pinta como "no disponible en
    la vista pública" aunque el archivo siga ahí tal cual y sea la misma
    nota — sólo cambió de nombre. Mismo criterio de prefijo que
    `move_shares`/`rename_private` para carpetas: toda nota que cuelgue de
    `old_rel/` se reapunta también. Mismo candado que `_record_attachment_owner`
    para no pisarse con una subida concurrente.
    """
    attachments_dir = base / ATTACHMENTS_DIR
    if not attachments_dir.is_dir():
        return
    lock_fp = open(attachments_dir / _ATTACHMENT_OWNERS_LOCK, "a")
    try:
        fcntl.flock(lock_fp, fcntl.LOCK_EX)
        owners = _read_attachment_owners(attachments_dir)
        changed = False
        prefix = old_rel + "/"
        for filename, note_path in list(owners.items()):
            if note_path == old_rel:
                owners[filename] = new_rel
                changed = True
            elif is_dir and note_path.startswith(prefix):
                owners[filename] = new_rel + "/" + note_path[len(prefix):]
                changed = True
        if changed:
            write_text_atomic(attachments_dir / _ATTACHMENT_OWNERS_FILE, json.dumps(owners))
    finally:
        fcntl.flock(lock_fp, fcntl.LOCK_UN)
        lock_fp.close()


def drop_shares(rel_path: str, is_dir: bool) -> None:
    """Revoca los enlaces públicos de lo que se acaba de borrar.

    Sin esto quedarían enlaces vivos apuntando a notas que ya no existen —o
    peor, si más tarde se crea una nota nueva con la misma ruta, apuntando
    sin querer a un contenido totalmente distinto del que tenía el enlace.
    """
    SharedNote.objects.filter(path=rel_path).delete()
    if is_dir:
        SharedNote.objects.filter(path__startswith=rel_path + "/").delete()


# ── Árbol ────────────────────────────────────────────────────────────────────

def build_tree(base: Path, directory: Path, private_paths: set = None,
               inherited_private: bool = False) -> list:
    # `private_paths` se calcula una sola vez (en la llamada de más arriba) y
    # se propaga en la recursión: evita releer `.private.json` una vez por
    # carpeta en bóvedas con muchas subcarpetas.
    if private_paths is None:
        private_paths = read_private(base)
    items = []
    try:
        entries = [e for e in directory.iterdir() if not e.name.startswith(".")]
    except OSError:
        return items
    order = read_order(directory)
    rank = {name: i for i, name in enumerate(order)}
    ordered = sorted((e for e in entries if e.name in rank), key=lambda e: rank[e.name])
    rest = sorted((e for e in entries if e.name not in rank),
                  key=lambda e: (not e.is_dir(), e.name.lower()))
    for entry in ordered + rest:
        # `stat()` puede fallar si el archivo desapareció entre iterdir y
        # aquí (race condition durante una operación bulk). Lo saltamos.
        try:
            is_dir = entry.is_dir()
            mtime = int(entry.stat().st_mtime) if not is_dir else None
        except OSError:
            continue
        # `private` es la marca PROPIA (la que se pone y se quita desde el
        # menú) y `private_inherited` la que viene de una carpeta de arriba:
        # el frontend las necesita separadas para no ofrecer "Hacer pública"
        # en una nota que seguiría oculta por su carpeta.
        rel = rel_of(base, entry)
        own_private = rel in private_paths
        if is_dir:
            items.append({
                "type": "folder", "name": entry.name,
                "path": rel,
                "private": own_private,
                "private_inherited": inherited_private,
                "children": build_tree(base, entry, private_paths,
                                       inherited_private or own_private),
            })
        elif entry.suffix.lower() == ".md":
            items.append({
                "type": "note", "name": entry.stem,
                "path": rel,
                "updated": mtime,
                "private": own_private,
                "private_inherited": inherited_private,
            })
        else:
            items.append({
                "type": "file", "name": entry.name,
                "ext": entry.suffix.lower().lstrip("."),
                "path": rel,
                "updated": mtime,
            })
    return items


def iter_notes(base: Path):
    """Notas de la bóveda, en orden y saltando lo oculto."""
    for p in sorted(base.rglob("*.md")):
        if any(part.startswith(".") for part in p.relative_to(base).parts):
            continue
        yield p


def iter_files(base: Path):
    """Adjuntos (todo lo que no es una nota), en orden y saltando lo oculto."""
    for p in sorted(base.rglob("*")):
        if any(part.startswith(".") for part in p.relative_to(base).parts):
            continue
        if p.is_file() and p.suffix.lower() != ".md":
            yield p


def search_notes(base: Path, terms: list, limit: int, snippet_before: int, snippet_after: int,
                 exclude: set = frozenset()):
    """Notas que contienen TODOS los términos. Devuelve `(path, texto, idx)`.

    El índice es el de la primera aparición del primer término: quien llama
    decide con qué margen recorta el fragmento que enseña. `exclude` son rutas
    relativas de notas O de carpetas (en cuyo caso cae todo lo que cuelga de
    ellas, ver `marked_private`) y se descarta ANTES de contar para el `limit`
    — si no, una nota privada que encajase se comería un hueco del cupo de
    resultados públicos.
    """
    found = 0
    for f in iter_notes(base):
        if exclude and marked_private(exclude, rel_of(base, f)):
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        low = text.lower()
        if not all(t in low for t in terms):
            continue
        idx = low.find(terms[0])
        yield f, text[max(0, idx - snippet_before): idx + snippet_after].replace("\n", " ")
        found += 1
        if found >= limit:
            return


# ── Estadísticas ─────────────────────────────────────────────────────────────

def stats(base: Path) -> dict:
    """Tamaño total de la bóveda, desglose por tipo y conteos."""
    totals = {
        "total_bytes": 0, "notes_bytes": 0, "images_bytes": 0, "other_bytes": 0,
        "n_notes": 0, "n_images": 0, "n_other": 0, "n_folders": 0,
    }
    for p in base.rglob("*"):
        try:
            if p.is_dir():
                if not p.name.startswith("."):
                    totals["n_folders"] += 1
                continue
            size = p.stat().st_size
        except OSError:
            continue
        totals["total_bytes"] += size
        ext = p.suffix.lower()
        if ext in NOTE_EXTS:
            totals["notes_bytes"] += size
            totals["n_notes"] += 1
        elif ext in IMAGE_EXTS:
            totals["images_bytes"] += size
            totals["n_images"] += 1
        else:
            totals["other_bytes"] += size
            totals["n_other"] += 1
    return totals


# ── Adjuntos ─────────────────────────────────────────────────────────────────

def to_webp(data: bytes):
    """Recodifica `data` a WebP, o `None` si no conviene (o no se puede).

    No recodifica si el archivo no es una imagen que Pillow entienda, o si el
    WebP resultante no sale más pequeño que el original.
    """
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return None
    try:
        img = Image.open(io.BytesIO(data))
        # Respetar la rotación EXIF antes de re-codificar.
        img = ImageOps.exif_transpose(img)
        # Convertir paletas/CMYK a RGB(A), que es lo que admite WebP.
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA" if "A" in img.mode else "RGB")
        buf = io.BytesIO()
        img.save(buf, "WEBP", quality=85, method=6)
        out = buf.getvalue()
        return out if len(out) < len(data) else None
    except Exception:
        # Pillow no entiende el formato: se guarda el original tal cual.
        return None


def save_upload(base: Path, uploaded_file, note_path: str = "") -> Path:
    """Guarda un adjunto en la bóveda y devuelve su ruta final.

    Si es una imagen ráster la recodificamos a WebP (~30-50% menos peso sin
    pérdida visible). Animados (gif), vectoriales (svg) y formatos que Pillow no
    entiende se guardan tal cual.

    Todos los adjuntos aterrizan SIEMPRE en `Adjuntos/`: la nota los referencia
    como `![[nombre]]`, que resuelve por nombre de archivo en toda la bóveda, así
    que su ubicación física no afecta al renderizado y las mantenemos juntas.

    `note_path`, si se indica, queda registrado como la nota que subió este
    adjunto (ver `attachment_owner`) — sólo lo usa la resolución de assets del
    enlace público, para no publicar por su nombre un adjunto sin relación con
    la nota que se comparte.
    """
    target_dir = base / ATTACHMENTS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    name = sanitize_name(uploaded_file.name)
    ext = Path(uploaded_file.name or "").suffix.lower()

    optimized = None
    if ext in IMAGE_EXTS and ext not in KEEP_AS_IS:
        # Sólo leemos el fichero entero en memoria si es una imagen ráster
        # candidata; para un pdf o un zip nos ahorramos el viaje.
        optimized = to_webp(b"".join(uploaded_file.chunks()))

    if optimized is not None:
        target = free_path(target_dir, Path(name).stem or "imagen", ".webp")
        target.write_bytes(optimized)
    else:
        stem, suffix = Path(name).stem, Path(name).suffix
        target = free_path(target_dir, stem, suffix)
        with open(target, "wb") as fp:
            for chunk in uploaded_file.chunks():
                fp.write(chunk)

    if note_path:
        _record_attachment_owner(target_dir, target.name, note_path)
    return target


def _read_attachment_owners(attachments_dir: Path) -> dict:
    try:
        return json.loads((attachments_dir / _ATTACHMENT_OWNERS_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _record_attachment_owner(attachments_dir: Path, filename: str, note_path: str) -> None:
    lock_fp = open(attachments_dir / _ATTACHMENT_OWNERS_LOCK, "a")
    try:
        fcntl.flock(lock_fp, fcntl.LOCK_EX)
        owners = _read_attachment_owners(attachments_dir)
        owners[filename] = note_path
        write_text_atomic(attachments_dir / _ATTACHMENT_OWNERS_FILE, json.dumps(owners))
    finally:
        fcntl.flock(lock_fp, fcntl.LOCK_UN)
        lock_fp.close()


def attachment_owner(base: Path, attachment_path: Path):
    """Ruta (relativa a la bóveda) de la nota que subió este adjunto, o `None`
    si no hay registro — adjunto anterior a este control, o fuera de
    `Adjuntos/`."""
    attachments_dir = base / ATTACHMENTS_DIR
    try:
        rel = attachment_path.relative_to(attachments_dir)
    except ValueError:
        return None
    return _read_attachment_owners(attachments_dir).get(str(rel).replace("\\", "/"))


def optimize_images(base: Path):
    """Recodifica a WebP las imágenes ráster de la bóveda, in-place.

    Generador de eventos (dicts) para que quien llama decida cómo enseñarlos:
    la web los va escupiendo como NDJSON para pintar una barra de progreso y la
    API se queda sólo con el último.

        {"phase":"scan"}
        {"phase":"start","total":N}
        {"phase":"progress","i":k,"total":N,"name":…,"converted":c,"skipped":s,"saved_bytes":b}
        {"phase":"rewriting","notes":M}
        {"phase":"done","converted":…,"skipped":…,"saved_bytes":…}
        {"phase":"error","error":…}
    """
    yield {"phase": "scan"}
    candidates = []
    try:
        for p in base.rglob("*"):
            try:
                if not p.is_file():
                    continue
            except OSError:
                continue
            ext = p.suffix.lower()
            if ext in KEEP_AS_IS or ext not in IMAGE_EXTS:
                continue
            candidates.append(p)
    except OSError as exc:
        yield {"phase": "error", "error": f"Error escaneando: {exc}"}
        return

    total = len(candidates)
    yield {"phase": "start", "total": total}

    converted = skipped = saved_bytes = 0
    renames = []

    for i, img_path in enumerate(candidates, start=1):
        def progress():
            return {"phase": "progress", "i": i, "total": total, "name": img_path.name,
                    "converted": converted, "skipped": skipped, "saved_bytes": saved_bytes}
        try:
            orig_size = img_path.stat().st_size
            new_data = to_webp(img_path.read_bytes())
        except OSError:
            new_data = None
        if new_data is None:
            skipped += 1
            yield progress()
            continue
        new_path = img_path.with_suffix(".webp")
        if new_path.exists() and new_path != img_path:
            new_path = free_path(img_path.parent, img_path.stem, ".webp")
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
            yield progress()
            continue
        saved_bytes += orig_size - len(new_data)
        converted += 1
        renames.append((img_path.name, new_path.name))
        # Un evento cada 5 imágenes para no inundar el wire (~10/s típico).
        if i % 5 == 0 or i == total:
            yield progress()

    # Reescribir referencias en notas: sólo dentro de embeds ![[nombre]] (la
    # sintaxis con la que esta app inserta imágenes), no un replace ciego que
    # podría corromper prosa que mencione el mismo nombre por coincidencia.
    if renames:
        patterns = [
            (re.compile(r"(?<=!\[\[)" + re.escape(old) + r"(?=[|\]])"), new)
            for old, new in renames if old != new
        ]
        md_files = list(base.rglob("*.md"))
        yield {"phase": "rewriting", "notes": len(md_files)}
        for md in md_files:
            try:
                text = md.read_text(encoding="utf-8")
            except OSError:
                continue
            new_text = text
            for pattern, new_name in patterns:
                new_text = pattern.sub(new_name, new_text)
            if new_text != text:
                try:
                    write_text_atomic(md, new_text)
                except OSError as exc:
                    log.warning("optimize: write md %s falló: %s", md, exc)

    yield {"phase": "done", "converted": converted,
           "skipped": skipped, "saved_bytes": saved_bytes}


# ── Export / import ──────────────────────────────────────────────────────────

def export_zip(base: Path):
    """Comprime la bóveda entera. Devuelve `(fichero_temporal, tamaño)`.

    Escribimos a un fichero temporal en disco (no a `BytesIO`): para bóvedas de
    cientos de MB evita mantener el ZIP entero en RAM por duplicado, una vez al
    construirlo y otra al leerlo. `TemporaryFile` no deja rastro en disco: el
    hueco se libera solo al cerrarse, incluso si el proceso muere a medias.
    """
    tmp = tempfile.TemporaryFile()
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in base.rglob("*"):
            if f.is_file() and not any(p.startswith(".") for p in f.parts):
                zf.write(f, arcname=str(f.relative_to(base)))
    size = tmp.tell()
    tmp.seek(0)
    return tmp, size


def export_files_zip(files):
    """Comprime una lista concreta de archivos. `files` es un iterable de
    `(Path, arcname)`. Mismo patrón que `export_zip` (fichero temporal, no
    `BytesIO`) y mismo motivo: no duplicar el contenido en RAM — aquí importa
    menos por el tamaño (son imágenes, no la bóveda entera) pero mantiene un
    único sitio con el patrón correcto de `TemporaryFile` + `ZipFile`.
    """
    tmp = tempfile.TemporaryFile()
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, arcname in files:
            zf.write(path, arcname=arcname)
    size = tmp.tell()
    tmp.seek(0)
    return tmp, size


def import_zip(base: Path, fileobj, mode: str = "merge") -> None:
    """Extrae un ZIP de bóveda. `mode="replace"` sustituye lo que hubiera.

    Levanta `VaultError` con el mensaje ya redactado si el ZIP no sirve.
    """
    try:
        with zipfile.ZipFile(fileobj, "r") as zf:
            members = [info for info in zf.infolist() if not info.is_dir()]
            if sum(info.file_size for info in members) > MAX_IMPORT_UNCOMPRESSED:
                raise VaultError("El ZIP supera el tamaño máximo permitido al descomprimir")
            # Valida TODAS las rutas (misma regla que el resto de operaciones:
            # sin ".." y con profundidad acotada) antes de tocar el disco, para
            # no dejar una importación a medias si una entrada es inválida.
            try:
                targets = [(info, safe_path(base, info.filename)) for info in members]
            except VaultError as exc:
                raise VaultError(f"Ruta inválida en el ZIP ({exc})") from exc

            if mode != "replace":
                _extract(zf, targets)
                return

            if not targets:
                # Un ZIP sin entradas no lanza excepción al "extraerlo" (no hay
                # nada que iterar), así que sin este corte "reemplazar" con un
                # ZIP vacío se leería como éxito y tiraría el respaldo entero.
                raise VaultError("El ZIP está vacío: no hay nada con qué reemplazar la bóveda")

            # Modo "replace": borrar y extraer después deja la bóveda vacía y sin
            # rehacer si la extracción falla a medias (disco lleno, ZIP corrupto en
            # una entrada que sólo se descubre al leerla). En vez de borrar,
            # apartamos lo actual con un `rename` —barato, mismo sistema de
            # ficheros— y sólo lo tiramos cuando la importación ha terminado bien.
            # Si algo falla, lo devolvemos a su sitio y el usuario no pierde nada.
            #
            # Todo esto asume que sólo UNA importación "replace" toca `base` a la
            # vez. gunicorn corre con `--threads 4` (gthread): varios hilos
            # comparten el mismo `os.getpid()`, así que dos "replace" concurrentes
            # del mismo worker podían generar el mismo nombre de stash y pisarse
            # entre sí — carrera confirmada de extremo a extremo (10 peticiones
            # concurrentes -> varias fallaban con 500, y en el peor caso alguna
            # importación ya terminada con éxito perdía sus ficheros porque el
            # siguiente "replace" los barría al mismo stash compartido antes de
            # borrarlo). `fcntl.flock` —a propósito, no `fcntl.lockf`: los locks
            # POSIX de `lockf` son por proceso y NO bloquean a otro hilo del mismo
            # proceso, justo el caso que hay que cubrir aquí— serializa todos los
            # "replace" de esta bóveda; el nombre del stash pasa a un UUID por
            # operación como defensa adicional, ya sin depender de la exclusión
            # mutua para no colisionar.
            lock_path = base / _IMPORT_LOCK_NAME
            lock_fp = open(lock_path, "a")
            try:
                try:
                    fcntl.flock(lock_fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError as exc:
                    raise VaultError(
                        "Ya hay una importación en curso sobre esta bóveda; "
                        "inténtalo de nuevo en unos segundos",
                        409,
                    ) from exc

                stash = base / f".import-anterior-{uuid.uuid4().hex}"
                stash.mkdir(exist_ok=True)
                moved = []
                try:
                    for it in base.iterdir():
                        if it.name.startswith("."):
                            continue
                        it.rename(stash / it.name)
                        moved.append(it.name)
                    _extract(zf, targets)
                except Exception:
                    # Deshacer: quitamos lo poco que se haya extraído y restauramos.
                    for it in base.iterdir():
                        if it.name.startswith("."):
                            continue
                        shutil.rmtree(it, ignore_errors=True) if it.is_dir() else it.unlink(missing_ok=True)
                    for name in moved:
                        try:
                            (stash / name).rename(base / name)
                        except OSError:
                            log.exception("import: no se pudo restaurar %s", name)
                    shutil.rmtree(stash, ignore_errors=True)
                    raise
                shutil.rmtree(stash, ignore_errors=True)
            finally:
                fcntl.flock(lock_fp, fcntl.LOCK_UN)
                lock_fp.close()
    except zipfile.BadZipFile as exc:
        raise VaultError("ZIP inválido") from exc
    except OSError as exc:
        raise VaultError(
            f"No se pudo importar (la bóveda anterior sigue intacta): {exc}", 500) from exc


def _extract(zf, targets) -> None:
    for info, target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "wb") as fp:
            fp.write(zf.read(info))


def reject_attachments_root(base: Path, target: Path, verb: str) -> None:
    """Corta operaciones sobre la carpeta `Adjuntos/` de la RAÍZ de la bóveda.

    Es la única carpeta con ruta fija que el backend impone (`save_upload`
    sube ahí siempre): moverla, copiarla o renombrarla dejaría subidas
    futuras creando una "Adjuntos" nueva y vacía en la raíz, duplicando la
    carpeta y rompiendo la resolución de adjuntos existentes. Único punto
    para esa operación en `apps.notes.views` evita que una segunda llamada
    futura se olvide de repetir el guardia.
    """
    if target == base / ATTACHMENTS_DIR:
        raise VaultError(f"La carpeta de adjuntos no se puede {verb}")
