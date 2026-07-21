"""User account model."""
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user — extiende AbstractUser para añadir role y theme.

    Conserva los nombres de columna (`role`, `theme`) del proyecto original
    para que la migración de datos sea directa.
    """

    ROLE_CHOICES = (
        ("user", "Usuario"),
        ("admin", "Admin"),
    )
    THEME_CHOICES = (
        ("dark", "Oscuro"),
        ("light", "Claro"),
        ("dracula", "Drácula"),
        ("pink", "Rosa"),
        ("aqua", "Aqua"),
    )

    role = models.CharField(max_length=16, choices=ROLE_CHOICES, default="user")
    theme = models.CharField(max_length=16, choices=THEME_CHOICES, default="dark")

    class Meta:
        db_table = "auth_user_custom"
        ordering = ("username",)

    def __str__(self) -> str:
        return self.username

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    def save(self, *args, **kwargs):
        # role == 'admin' ⇒ is_staff + is_superuser. Esto permite usar los
        # decoradores nativos de Django (@staff_member_required, @permission_required)
        # y, de paso, abrir el Django admin nativo para los admins.
        is_admin = (self.role == "admin")
        if self.is_staff != is_admin:
            self.is_staff = is_admin
        if self.is_superuser != is_admin:
            self.is_superuser = is_admin
        super().save(*args, **kwargs)
