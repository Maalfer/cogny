import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='CommunityLink',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('name', models.CharField(blank=True, default='', max_length=80)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('last_used_at', models.DateTimeField(blank=True, null=True)),
                ('visits', models.PositiveIntegerField(default=0)),
                ('revoked', models.BooleanField(default=False)),
            ],
            options={
                'verbose_name': 'enlace comunitario',
                'verbose_name_plural': 'enlaces comunitarios',
                'ordering': ['-created_at'],
            },
        ),
    ]
