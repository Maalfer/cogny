# Generated for la caducidad de los enlaces de escritura.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notes", "0007_delete_notetoken"),
    ]

    operations = [
        migrations.AddField(
            model_name="sharednote",
            name="expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
