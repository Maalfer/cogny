"""Settings base — comunes a todos los entornos.

`dev` y `prod` heredan de aquí y sólo sobrescriben lo específico de cada entorno
(DEBUG, ALLOWED_HOSTS, cookies seguras, HSTS, etc.).
"""
import os
from pathlib import Path

# config/settings/base.py → BASE_DIR = django_app/
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# .env loader minimalista (sin dependencias externas).
ENV_FILE = BASE_DIR / ".env"
if ENV_FILE.exists():
    for _line in ENV_FILE.read_text().splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _v = _line.split("=", 1)
        os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

# ── Núcleo ───────────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or "cogny-dev-secret-CHANGE-ME"

# Versión de la app (fichero VERSION en la raíz del repo). Se muestra en el
# header de la UI — súbela ahí en cada release, junto al tag de git.
VERSION = (BASE_DIR / "VERSION").read_text().strip() if (BASE_DIR / "VERSION").exists() else "0.0.0"

_hosts = [h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if h.strip()]
ALLOWED_HOSTS = _hosts or ["127.0.0.1", "localhost"]

CSRF_TRUSTED_ORIGINS = [
    f"https://{h}" for h in ALLOWED_HOSTS if h not in ("127.0.0.1", "localhost", "*")
] + ["http://127.0.0.1:8002", "http://localhost:8002"]

# ── Apps / middleware ────────────────────────────────────────────────────────
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # Local apps
    "apps.core",
    "apps.accounts",
    "apps.notes",
    "apps.api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.GlobalContextMiddleware",
    "apps.core.middleware.UploadCorsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {
        "builtins": ["apps.core.templatetags.cogny_tags"],
        "context_processors": [
            "django.template.context_processors.debug",
            "django.template.context_processors.request",
            "django.contrib.auth.context_processors.auth",
            "django.contrib.messages.context_processors.messages",
            "apps.core.context_processors.global_context",
        ],
    },
}]

# ── BD ───────────────────────────────────────────────────────────────────────
# SQLite: la app guarda un único usuario y las sesiones; un servidor de BD
# completo (MySQL) era peso muerto. El fichero vive junto al resto de datos.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("DB_PATH", str(BASE_DIR / "data" / "db.sqlite3")),
        "OPTIONS": {
            # WAL: lectores y el (único) escritor no se bloquean entre sí.
            "init_command": "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;",
            "timeout": 20,
        },
    }
}

# ── Auth ─────────────────────────────────────────────────────────────────────
AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 6}},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

# ── I18N ─────────────────────────────────────────────────────────────────────
LANGUAGE_CODE = "es"
TIME_ZONE = "Europe/Madrid"
USE_I18N = True
USE_TZ = True

# ── Static / Media ───────────────────────────────────────────────────────────
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = Path(os.environ.get("STATIC_ROOT", BASE_DIR / "static_collected"))
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Uploads: tope 1 GB (import de bóvedas completas).
# nginx debe ir alineado en client_max_body_size.
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024 * 1024 + 10 * 1024 * 1024

# ── Sesiones / CSRF ──────────────────────────────────────────────────────────
SESSION_COOKIE_AGE = 60 * 60 * 24 * 365
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
CSRF_HEADER_NAME = "HTTP_X_CSRFTOKEN"
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
# Cookies con nombre propio: evita que la sesión de Pingu (mismo dominio padre)
# y la de cogny se pisen entre sí en el navegador.
SESSION_COOKIE_NAME = "cogny_sessionid"
CSRF_COOKIE_NAME = "cogny_csrftoken"

# ── Logging ──────────────────────────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "{asctime} {levelname} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}

# ── Constantes app ───────────────────────────────────────────────────────────
ASSET_VERSION = os.environ.get("ASSET_VERSION", "v1")

# Subdominio DNS-only (fuera de Cloudflare) para importar bóvedas grandes,
# esquivando el límite de 100 MB por request del proxy de Cloudflare.
UPLOAD_HOST = os.environ.get("UPLOAD_HOST", "")

DATA_ROOT = Path(os.environ.get("DATA_ROOT", BASE_DIR / "data"))
VAULT_ROOT = Path(os.environ.get("VAULT_ROOT", DATA_ROOT / "vault"))
AVATARS_ROOT = Path(os.environ.get("AVATARS_ROOT", BASE_DIR / "static" / "avatars"))
