"""Notes vault — el contenido vive en disco (archivos .md).

Esta app es 'view-only' para Django ORM en cuanto al contenido: las notas son
archivos Markdown bajo settings.VAULT_ROOT/. Los modelos que sí definimos son
metadata (no contenido): enlaces públicos y marcas de exportación a PDF."""
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


class PdfTheme(models.Model):
    """Plantilla HTML+CSS con la que se maqueta una nota exportada a PDF.

    El tema ES la plantilla: no hay ajustes sueltos (color, posición del logo,
    portada sí/no…) porque cualquiera de esas decisiones se escribe mejor en
    el propio CSS, y una lista de casillas siempre se queda corta frente a lo
    que se puede pedir a un PDF con identidad de empresa. `html` lleva dentro
    su `<style>`; el marcador `{{ contenido }}` es donde entra la nota. Ver
    `themes.py` para los marcadores y el saneado.
    """

    name = models.CharField(max_length=80)
    html = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "pk"]

    def __str__(self):
        return self.name


class PdfThemeImage(models.Model):
    """Imagen de un tema (logo, sello, fondo…), referenciable como `{{ img:nombre }}`.

    Los bytes van a disco (`DATA_ROOT/themes/`), no a la base de datos: se leen
    enteros en cada exportación para incrustarlos como `data:` URI, que es la
    única forma de que lleguen al PDF (Chromium imprime sin red).
    """

    theme = models.ForeignKey(PdfTheme, on_delete=models.CASCADE, related_name="images")
    name = models.CharField(max_length=60)
    ext = models.CharField(max_length=5)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["theme", "name"], name="uniq_theme_image_name"),
        ]

    def __str__(self):
        return f"{self.theme.name}/{self.name}"
