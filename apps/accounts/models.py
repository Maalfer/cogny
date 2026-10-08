"""User account model."""
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user — extiende AbstractUser para añadir theme y rol de acceso.

    Conserva el nombre de columna (`theme`) del proyecto original para que la
    migración de datos sea directa.

    La bóveda es una sola y compartida: el rol no reparte contenido, reparte
    permisos sobre ese contenido único.

    - `owner`   — el dueño del sitio. Todo, incluido crear accesos.
    - `editor`  — lee y escribe notas, carpetas, adjuntos y enlaces compartidos.
    - `viewer`  — sólo lectura: puede navegar, leer, buscar y exportar.
    """

    THEME_CHOICES = (
        ("dark", "Oscuro"),
        ("light", "Claro"),
        ("dracula", "Drácula"),
        ("pink", "Rosa"),
        ("gold", "Dorado"),
        ("dark-cristal", "Dark Cristal"),
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
