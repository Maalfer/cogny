"""Bóveda pública `/conocimiento`: configuración y enlaces maestros.

El contenido no vive aquí —sigue siendo la misma bóveda de ficheros `.md` que
lee `apps.notes.vault`—; esta app sólo guarda QUIÉN puede leerla desde fuera.
"""
import uuid

from django.db import models


class PublicVault(models.Model):
    """Configuración de la bóveda pública. Fila única (`pk=1`).

    Es un singleton a propósito: hay una bóveda y una sola política de acceso.
    Un modelo con una fila resulta más aburrido que un fichero de settings, pero
    esto lo cambia el propietario desde la web y tiene que persistir sin tocar
    el servidor ni reiniciar nada.
    """

    SINGLETON_PK = 1

    enabled = models.BooleanField(default=False)

    # Días que dura el permiso una vez concedido (al canjear un enlace
    # maestro), para que quien ya entró pueda navegar, volver por un
    # marcador o recargar sin repetir el enlace.
    grant_days = models.PositiveSmallIntegerField(default=30)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "bóveda pública"

    def __str__(self):
        return "activa" if self.enabled else "desactivada"

    @classmethod
    def get(cls) -> "PublicVault":
        obj, _created = cls.objects.get_or_create(pk=cls.SINGLETON_PK)
        return obj

    def save(self, *args, **kwargs):
        # Blindaje: nadie crea una segunda configuración por accidente.
        self.pk = self.SINGLETON_PK
        super().save(*args, **kwargs)


class MasterLink(models.Model):
    """Enlace maestro: única puerta de entrada a la bóveda pública.

    El token es un UUID4 justamente para que no se pueda adivinar: es la única
    barrera que tiene este enlace, así que se manda a dedo y se revoca en cuanto
    se sospeche que ha circulado de más.
    """

    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=80, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    visits = models.PositiveIntegerField(default=0)
    revoked = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "enlace maestro"
        verbose_name_plural = "enlaces maestros"

    def __str__(self):
        return self.name or str(self.token)

    def path(self) -> str:
        return f"/conocimiento/m/{self.token}/"
