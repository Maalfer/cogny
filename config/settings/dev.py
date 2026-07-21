"""Settings de desarrollo local. Hereda de base e invalida lo específico de dev."""
from .base import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = ["*"]

# En dev no requeremos HTTPS, ni HSTS, ni cookies seguras.
SECURE_PROXY_SSL_HEADER = None
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0

# Más verbosidad en logs durante el desarrollo.
LOGGING["root"]["level"] = "DEBUG"  # noqa: F405
LOGGING["loggers"]["django.request"]["level"] = "INFO"  # noqa: F405
