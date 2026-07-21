# Punto de entrada del paquete settings.
#
# DJANGO_SETTINGS_MODULE puede ser:
#   - config.settings.dev   (desarrollo local, DEBUG=1)
#   - config.settings.prod  (producción)
#   - config.settings       (alias → prod por defecto; lo que carguen este
#                            módulo sin especificar variante reciben prod).
from .prod import *  # noqa: F401,F403
