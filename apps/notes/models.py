"""Notes vault — el contenido vive en disco (archivos .md).

Esta app es 'view-only' para Django ORM en cuanto al contenido: las notas son
archivos Markdown bajo settings.VAULT_ROOT/. El único modelo que sí
definimos es metadata de enlaces públicos (no contenido)."""
from django.db import models


class SharedNote(models.Model):
    """Enlace público a una nota concreta (`path` del vault).

    `token` es la parte pública de la URL (`/s/<token>/`); una nota sólo puede
    tener un enlace activo a la vez (`path` es único), así que reabrir el
    modal de "Compartir" reutiliza el mismo token en vez de invalidar enlaces
    ya repartidos. `password_hash` vacío = acceso libre; con contraseña, el
    hash se guarda con el mismo hasher que usa Django para las cuentas.
    """

    token = models.CharField(max_length=32, primary_key=True, editable=False)
    path = models.CharField(max_length=600, unique=True)
    password_hash = models.CharField(max_length=128, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.path} ({self.token})"
