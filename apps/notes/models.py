"""Notes vault — el contenido vive en disco (archivos .md).

Esta app es 'view-only' para Django ORM en cuanto al contenido: las notas son
archivos Markdown bajo settings.VAULT_ROOT/. Los modelos que sí definimos son
metadata (no contenido): enlaces públicos y marcas de exportación a PDF."""
from django.db import models
from django.utils import timezone


class SharedNoteQuerySet(models.QuerySet):
    """Enlaces que siguen sirviendo (`alive()`), no los ya caducados.

    Un `expires_at` pasado equivale a un enlace revocado: ni aparece en el
    modal ni en el panel de ajustes, y `/s/<token>/` responde 404. La fila
    puede seguir en la BD hasta que barra `views._purge_expired_shares`; lo
    que nunca puede es seguir dando acceso.
    """

    def alive(self):
        return self.filter(
            models.Q(expires_at__isnull=True)
            | models.Q(expires_at__gt=timezone.now())
        )


class SharedNote(models.Model):
    """Enlace público a una nota concreta (`path` del vault).

    `token` es la parte pública de la URL (`/s/<token>/`); una nota sólo puede
    tener un enlace activo a la vez (`path` es único), así que reabrir el
    modal de "Compartir" reutiliza el mismo token en vez de invalidar enlaces
    ya repartidos. El token ES la única credencial del enlace.

    `can_write` convierte el enlace en editable: quien lo abra escribe en la
    nota como el dueño, sin cuenta. Es una decisión por enlace y NO por
    persona (el token es la única credencial), así que se apaga por defecto y
    el modal avisa de lo que implica antes de encenderlo. Sigue sin dar acceso
    a nada más que a ESA nota: ni árbol, ni renombrar, ni borrar. En modo
    escritura también expone el API JSON de la nota y sus adjuntos (ver
    `views.shared_note_note` / `shared_note_assets`), pensado para dárselo a
    una IA que gestione la nota por HTTP sin sesión.

    `expires_at` es la caducidad del enlace (vacía = no caduca). Los enlaces
    editables se crean con 10 minutos de vida (`views.SHARE_WRITE_TTL`) y se
    rearman al volver a guardarlos: así una nota no queda escribible para
    siempre sólo porque su dueño olvidó revocar el enlace. Al apagar la
    escritura la caducidad se borra y el enlace vuelve a ser el de lectura de
    siempre.
    """

    token = models.CharField(max_length=32, primary_key=True, editable=False)
    path = models.CharField(max_length=600, unique=True)
    can_write = models.BooleanField(default=False)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = SharedNoteQuerySet.as_manager()

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
