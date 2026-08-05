"""Comandos de gestión de `apps.accounts`."""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.accounts.models import User


class AuditOwnerRolesTests(TestCase):
    def _run(self):
        out = StringIO()
        call_command("audit_owner_roles", stdout=out)
        return out.getvalue()

    def test_una_sola_cuenta_owner_no_avisa(self):
        User.objects.create_user(username="dueño", password="x", role=User.ROLE_OWNER)
        out = self._run()
        self.assertIn("Correcto", out)

    def test_mas_de_una_cuenta_owner_avisa(self):
        """El escenario de la migración 0005_user_role: dos cuentas que no
        deberían ser ambas 'owner' terminan siéndolo."""
        User.objects.create_user(username="dueño", password="x", role=User.ROLE_OWNER)
        User.objects.create_user(username="invitado-antiguo", password="x", role=User.ROLE_OWNER)
        out = self._run()
        self.assertIn("2 cuentas con role='owner'", out)
        self.assertIn("dueño", out)
        self.assertIn("invitado-antiguo", out)

    def test_sin_cuentas_no_falla(self):
        out = self._run()
        self.assertIn("No hay ninguna cuenta", out)
