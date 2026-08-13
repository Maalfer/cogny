"""Pizarras `/pizarra`: lienzos de dibujo tipo Excalidraw.

Como en `apps.notes`, la bóveda es una sola y compartida — no hay pizarras
"privadas" de cada usuario, `created_by` es sólo información de quién la
creó. El contenido pesado (elementos del lienzo + imágenes incrustadas) no
vive en la BD: cuelga de un fichero JSON en disco (`apps.whiteboard.storage`),
igual que las notas cuelgan de ficheros `.md`. Este modelo es sólo el índice
rápido para listar y ordenar sin tener que abrir cada JSON.
"""
import uuid

from django.conf import settings
from django.db import models


class Board(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120, default="Sin título")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="whiteboards",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    has_thumb = models.BooleanField(default=False)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "pizarra"

    def __str__(self):
        return self.name
