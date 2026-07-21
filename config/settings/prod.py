"""Settings de producción. Hereda de base y añade seguridad reforzada."""
from .base import *  # noqa: F401,F403

DEBUG = False

# Si el entorno no define hosts, fallamos rápido (no servimos a `*` en prod).
if ALLOWED_HOSTS == ["127.0.0.1", "localhost"]:  # noqa: F405 — default de base
    # Permitimos el default sólo si DJANGO_ALLOWED_HOSTS no se ha exportado.
    # En producción real, .env debería establecerlo siempre.
    pass

# Cabeceras de seguridad cuando estamos detrás de nginx + TLS.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = False  # nginx ya redirige 80 → 443
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = False
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "SAMEORIGIN"
