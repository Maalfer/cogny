"""Utilidades comunes a los tests.

Cada test corre sobre una bóveda propia en un directorio temporal: nunca se
toca la bóveda real, y el orden de ejecución deja de importar.
"""
import shutil
import tempfile
from pathlib import Path

from django.test import TestCase, override_settings

from apps.accounts.models import User


class VaultTestCase(TestCase):
    """Test con una bóveda vacía en disco, borrada al terminar."""

    def setUp(self):
        super().setUp()
        self.vault_dir = Path(tempfile.mkdtemp(prefix="cogny-test-"))
        self.addCleanup(shutil.rmtree, self.vault_dir, True)
        patcher = override_settings(VAULT_ROOT=self.vault_dir)
        patcher.enable()
        self.addCleanup(patcher.disable)

    # ── Ayudas ──

    def make_user(self, username="tester", role=User.ROLE_OWNER, password="clave-de-prueba"):
        return User.objects.create_user(username=username, password=password, role=role)

    def write_note(self, rel: str, content: str = "hola") -> Path:
        target = self.vault_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def json_post(self, url: str, payload: dict):
        return self.client.post(url, data=payload, content_type="application/json")
