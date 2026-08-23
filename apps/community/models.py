"""Bóveda comunitaria `/comunidad`: quién puede entrar a escribir en ella.

El contenido no vive aquí —es la misma clase de bóveda de ficheros `.md` que
`apps.notes.vault`, pero bajo `settings.COMMUNITY_VAULT_ROOT`, una raíz
totalmente separada de la bóveda privada—; esta app sólo guarda los enlaces
que dan acceso a esa raíz.

A diferencia de `apps.knowledge` (que es de sólo lectura y controla el acceso
por dominio de origen + un enlace maestro), aquí no hay más puerta que el
enlace: quien lo tiene puede leer y escribir cualquier cosa de la bóveda
comunitaria. Por eso no hace falta el singleton `PublicVault` de knowledge —
no hay dominios que filtrar ni un interruptor global: que exista al menos un
`CommunityLink` sin revocar ya es "la bóveda comunitaria está activa".
"""
import uuid

from django.db import models


class CommunityLink(models.Model):
    """Enlace a la bóveda comunitaria: da acceso de lectura y escritura.

    El token es un UUID4 justamente para que no se pueda adivinar: es la única
    barrera que tiene este enlace, así que se manda a dedo (uno por persona,
    si se quiere) y se revoca en cuanto se sospeche que ha circulado de más.
    Revocarlo echa también a quien ya había entrado con él (ver
    `apps/community/access.py`), no sólo bloquea entradas nuevas.
    """

    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=80, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    visits = models.PositiveIntegerField(default=0)
    revoked = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "enlace comunitario"
        verbose_name_plural = "enlaces comunitarios"

    def __str__(self):
        return self.name or str(self.token)

    def path(self) -> str:
        return f"/comunidad/enlace/{self.token}/"
