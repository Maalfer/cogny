"""Comando de auditoría: detecta cuentas 'owner' anómalas.

cogny asume un único propietario por instancia (ver el docstring de
`accounts.models.User`: "el dueño del sitio"). La migración `0005_user_role`
promocionó a `owner` TODAS las cuentas que ya existieran en el momento de
aplicarse, sin poder distinguirlas entre sí: el rol histórico (`admin`/`user`
de `0001_initial`) ya se había borrado un día antes en
`0003_remove_user_role`, así que no queda nada de lo que diferenciarlas.

Una instancia que tuviera cuentas invitadas creadas antes del 24-07-2026 y se
actualizara cruzando esas dos migraciones puede tener hoy más de un `owner`
sin que quede ningún registro de aplicación que lo señale — sólo el propio
estado de la tabla `User`. Este comando no corrige nada automáticamente (no
hay forma de saber, sólo con estos datos, cuál era la cuenta legítima); se
limita a hacer visible la anomalía para que el operador decida.
"""
from django.core.management.base import BaseCommand

from apps.accounts.models import User


class Command(BaseCommand):
    help = "Lista las cuentas con role='owner' y avisa si hay más de una."

    def handle(self, *args, **options):
        owners = User.objects.filter(role=User.ROLE_OWNER).order_by("date_joined")
        count = owners.count()
        if count == 0:
            self.stdout.write(self.style.WARNING("No hay ninguna cuenta 'owner'."))
            return

        for u in owners:
            self.stdout.write(f"{u.username}\trole={u.role}\tdate_joined={u.date_joined:%Y-%m-%d}")

        if count == 1:
            self.stdout.write(self.style.SUCCESS("\nUna sola cuenta 'owner'. Correcto."))
            return

        self.stdout.write(self.style.ERROR(
            f"\n{count} cuentas con role='owner'. cogny asume una sola. Si "
            "esta instancia se actualizó desde una versión anterior a "
            "0003_remove_user_role (24-07-2026) con cuentas invitadas ya "
            "creadas, la migración 0005_user_role pudo haberlas promovido a "
            "todas por igual. Revisa cuál es la cuenta legítima y reasigna "
            "el resto a 'editor'/'viewer' desde el panel de Accesos."
        ))
