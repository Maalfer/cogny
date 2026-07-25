"""Reglas de cuenta compartidas por la web (sesión) y la API v1 (clave).

Las dos capas hacen lo mismo con distinta puerta de entrada: crear accesos
invitados, cambiar su permiso, revocar claves… Si cada una lleva su propia
validación acaban divergiendo, y la que se quede corta es un agujero. Aquí está
la versión única; las vistas sólo traducen a HTTP.
"""
from pathlib import Path

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError

from .models import ApiKey, User

MAX_AVATAR_BYTES = 4 * 1024 * 1024


# ── Avatares ─────────────────────────────────────────────────────────────────

def avatar_path(user) -> Path:
    """Ruta del avatar de un usuario.

    Un fichero por cuenta: con varios accesos, el `avatar.jpg` único de antes
    haría que el último en subir foto pisara la de todos los demás.
    """
    return settings.AVATARS_ROOT / f"avatar-{user.pk}.jpg"


def detect_image_kind(head: bytes):
    """Tipo de imagen según los bytes mágicos, o `None` si no lo es.

    Se mira el contenido y no la extensión ni el `Content-Type`: los dos los
    elige quien sube el archivo.
    """
    if head.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head.startswith(b"GIF87a") or head.startswith(b"GIF89a"):
        return "gif"
    if head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        return "webp"
    return None


# ── Serialización ────────────────────────────────────────────────────────────

def user_json(user: User) -> dict:
    return {
        "id": user.pk,
        "username": user.username,
        "role": user.role,
        "role_label": user.get_role_display(),
        "can_write": user.can_write,
        "is_owner": user.is_owner,
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "created_at": user.date_joined.isoformat(),
    }


def api_key_json(key: ApiKey) -> dict:
    """Todo lo público de una clave. El secreto NO está aquí: sólo existe en el
    momento de crearla, y lo añade quien la crea."""
    return {
        "id": key.pk,
        "name": key.name,
        "prefix": key.prefix,
        "masked": key.masked,
        "read_only": key.read_only,
        "revoked": key.revoked,
        "created_at": key.created_at.isoformat(),
        "last_used_at": key.last_used_at.isoformat() if key.last_used_at else None,
    }


# ── Validación ───────────────────────────────────────────────────────────────

def validate_username(username: str, exclude_pk=None):
    """Mensaje de error del nombre de usuario, o `None` si vale."""
    if not username:
        return "Indica un nombre de usuario"
    try:
        UnicodeUsernameValidator()(username)
    except ValidationError:
        return "Sólo letras, números y @/./+/-/_"
    qs = User.objects.filter(username__iexact=username)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    if qs.exists():
        return "Ese nombre de usuario ya existe"
    return None


def validate_new_user(username: str, password: str, role: str, exclude_pk=None):
    """Valida usuario/contraseña/rol. Devuelve el mensaje de error, o None."""
    error = validate_username(username, exclude_pk)
    if error:
        return error
    if role not in User.GUEST_ROLES:
        return "Permiso inválido: usa 'editor' (lectura y escritura) o 'viewer' (sólo lectura)"
    try:
        validate_password(password)
    except ValidationError as exc:
        return " ".join(exc.messages)
    return None


def validate_new_password(password: str, user=None):
    """Mensaje de error de la contraseña nueva, o `None` si vale."""
    try:
        validate_password(password, user=user)
    except ValidationError as exc:
        return " ".join(exc.messages)
    return None


# ── Accesos invitados ────────────────────────────────────────────────────────

def find_guest(user_id):
    """El invitado sobre el que se va a operar. `(usuario, error, status)`.

    El propietario queda fuera de alcance a propósito: ni se le cambia el rol ni
    se le borra desde aquí, para que no exista forma de dejar el sitio sin dueño.
    """
    user = User.objects.filter(pk=user_id).first()
    if not user:
        return None, "Acceso no encontrado", 404
    if user.is_owner:
        return None, "La cuenta propietaria no se puede modificar desde aquí", 403
    return user, None, 0


def delete_guest(user) -> None:
    """Borra el acceso y su avatar (que vive fuera de la BD, en disco)."""
    avatar = avatar_path(user)
    user.delete()
    avatar.unlink(missing_ok=True)
