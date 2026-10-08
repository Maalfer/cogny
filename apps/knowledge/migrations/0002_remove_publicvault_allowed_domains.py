# Quita el filtro de acceso por dominio/Referer: la bóveda pública ahora sólo
# se entra por enlace maestro (ver apps/knowledge/access.py).
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('knowledge', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='publicvault',
            name='allowed_domains',
        ),
    ]
