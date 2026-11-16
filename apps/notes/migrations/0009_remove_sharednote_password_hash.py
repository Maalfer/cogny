# Elimina la contraseña opcional de los enlaces compartidos: el token es la
# única credencial del enlace.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("notes", "0008_sharednote_expires_at"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="sharednote",
            name="password_hash",
        ),
    ]
