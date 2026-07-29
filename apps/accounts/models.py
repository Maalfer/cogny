"""User account model + claves de API."""
import hashlib
import hmac
import secrets

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user — extiende AbstractUser para añadir theme y rol de acceso.

    Conserva el nombre de columna (`theme`) del proyecto original para que la
    migración de datos sea directa.

    La bóveda es una sola y compartida: el rol no reparte contenido, reparte
    permisos sobre ese contenido único.

    - `owner`   — el dueño del sitio. Todo, incluido crear accesos y claves de API.
    - `editor`  — lee y escribe notas, carpetas, adjuntos y enlaces compartidos.
    - `viewer`  — sólo lectura: puede navegar, leer, buscar y exportar.
    """

    THEME_CHOICES = (
        ("dark", "Oscuro"),
        ("light", "Claro"),
        ("dracula", "Drácula"),
        ("pink", "Rosa"),
        ("gold", "Dorado"),
    )

    ROLE_OWNER = "owner"
    ROLE_EDITOR = "editor"
    ROLE_VIEWER = "viewer"
    ROLE_CHOICES = (
        (ROLE_OWNER, "Propietario"),
        (ROLE_EDITOR, "Lectura y escritura"),
        (ROLE_VIEWER, "Sólo lectura"),
    )
    # Roles que se pueden asignar a un acceso invitado (el de propietario no).
    GUEST_ROLES = (ROLE_EDITOR, ROLE_VIEWER)

    theme = models.CharField(max_length=16, choices=THEME_CHOICES, default="dark")
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=ROLE_VIEWER)

    class Meta:
        db_table = "auth_user_custom"
        ordering = ("username",)

    def __str__(self) -> str:
        return self.username

    @property
    def is_owner(self) -> bool:
        return self.role == self.ROLE_OWNER

    @property
    def can_write(self) -> bool:
        return self.role in (self.ROLE_OWNER, self.ROLE_EDITOR)


# ── Claves de API ────────────────────────────────────────────────────────────

# Formato de la clave: "cgny_<prefix>_<secret>".
#   prefix — 8 chars, se guarda en claro: identifica la fila sin revelar nada.
#   secret — 43 chars (32 bytes urlsafe): sólo se ve UNA vez, al crearla.
KEY_PREFIX_LEN = 8
_KEY_NAMESPACE = "cgny"


class ApiKeyManager(models.Manager):
    def create_key(self, user, name: str, read_only: bool = False):
        """Crea una clave y devuelve `(instancia, clave_en_claro)`.

        La clave en claro sólo existe en este retorno: en BD queda el hash.
        """
        prefix = secrets.token_hex(KEY_PREFIX_LEN // 2)
        secret = secrets.token_urlsafe(32)
        raw = f"{_KEY_NAMESPACE}_{prefix}_{secret}"
        key = self.create(
            user=user,
            name=(name or "").strip()[:80] or "Clave sin nombre",
            prefix=prefix,
            key_hash=ApiKey.hash_key(raw),
            read_only=read_only,
        )
        return key, raw


class ApiKey(models.Model):
    """Clave de API para controlar la bóveda desde fuera (curl, IA, scripts).

    El hash es HMAC-SHA256 con `SECRET_KEY`, no PBKDF2: la clave tiene 256 bits
    de entropía aleatoria (no es una contraseña adivinable), así que no hace
    falta un hash lento — y sí hace falta que verificarla sea barato, porque se
    valida en CADA petición de la API.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="api_keys")
    name = models.CharField(max_length=80)
    prefix = models.CharField(max_length=16, unique=True, db_index=True)
    key_hash = models.CharField(max_length=64)
    read_only = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked = models.BooleanField(default=False)

    objects = ApiKeyManager()

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.name} ({self.prefix})"

    @staticmethod
    def hash_key(raw: str) -> str:
        return hmac.new(
            settings.SECRET_KEY.encode("utf-8"), raw.encode("utf-8"), hashlib.sha256
        ).hexdigest()

    @classmethod
    def resolve(cls, raw: str):
        """Devuelve la `ApiKey` válida que corresponde a `raw`, o None."""
        raw = (raw or "").strip()
        # maxsplit=2: `token_urlsafe` mete '_' y '-' en el secreto, así que
        # partir por todos los '_' trocearía la clave y nunca validaría.
        parts = raw.split("_", 2)
        if len(parts) != 3 or parts[0] != _KEY_NAMESPACE or not parts[1] or not parts[2]:
            return None
        key = cls.objects.filter(prefix=parts[1], revoked=False).select_related("user").first()
        if not key:
            return None
        if not hmac.compare_digest(key.key_hash, cls.hash_key(raw)):
            return None
        return key

    @property
    def masked(self) -> str:
        return f"{_KEY_NAMESPACE}_{self.prefix}_{'•' * 12}"
