# Cogny

Vault de notas Markdown tipo Obsidian en Django 6. Una sola bóveda, con un
propietario y los accesos invitados que éste decida darle.

## Stack

- **Backend**: Django 6.0 + gunicorn WSGI (`config.wsgi:application`, workers `gthread`).
  No hay registro público: los accesos los crea el propietario desde su perfil.
- **BD**: SQLite (`data/db.sqlite3`) — un servidor de BD completo era peso muerto para
  guardar un único usuario y las sesiones.
- **Estáticos**: `manage.py collectstatic` vuelca `static/` → `static_collected/`, que
  nginx sirve directamente vía `alias` (no pasa por Django/WhiteNoise en producción).
  Cache-busting con `?v={{ ASSET_VERSION }}` — sube `ASSET_VERSION` en `.env` tras tocar
  cualquier estático y reinicia el servicio para que se note el cambio.
- **Reverse proxy**: nginx con TLS (Cloudflare delante), dominio
  `cogny.fatimaymariosecasan.es` (más un subdominio DNS-only,
  `subir-cogny.fatimaymariosecasan.es`, sólo para importar bóvedas grandes esquivando
  el límite de 100 MB de Cloudflare).

## Apps

`apps/` contiene 4 apps: `core` (helpers/middleware compartidos), `accounts` (login,
perfil, avatar, tema, claves de API), `notes` (el vault en sí — árbol de archivos,
edición, adjuntos, export/import, enlaces públicos de sólo lectura) y `api` (la API
pública v1 + Swagger).

**La lógica no vive en las vistas.** Hay dos puertas de entrada al mismo sistema —la
web con sesión y la API con clave— así que lo que hacen de verdad está en módulos que
no saben nada de HTTP, y las vistas sólo validan la petición y traducen el resultado:

| Módulo | Qué contiene |
|---|---|
| `apps/notes/vault.py` | Todo lo que toca el disco: rutas seguras (`safe_path`), árbol, orden manual de carpetas, escritura atómica, búsqueda, stats, adjuntos, export/import ZIP, optimización a WebP. |
| `apps/notes/pdf.py` | Exportar una nota a PDF: saneado del HTML y Chromium headless. |
| `apps/accounts/services.py` | Reglas de cuenta: validación de usuario/contraseña/rol, serialización, avatares, accesos invitados. |
| `apps/core/api.py` | Utilidades HTTP comunes: `error_response`, `json_body`, coerción de tipos del cuerpo JSON. |

Si añades una operación, va en el módulo de servicio y la exponen las dos capas; no
la escribas en una vista para llamarla luego desde la otra.

## Accesos y permisos

La bóveda es **una sola y compartida**: el rol no reparte contenido, reparte
permisos sobre ese contenido único (`accounts.User.role`).

| Rol | Puede |
|---|---|
| `owner` | Todo. Además: crear accesos, cambiarles el permiso y gestionar claves de API. |
| `editor` | Leer y escribir: notas, carpetas, adjuntos, enlaces compartidos, import/export. |
| `viewer` | Sólo lectura: navegar, leer, buscar y exportar. |

El propietario los gestiona en **Mi perfil → Accesos** (o por API en `/api/v1/users`).

Cómo se aplica el permiso, por si añades una vista nueva:

- `apps/accounts/permissions.py` tiene los dos decoradores (`require_write`,
  `require_owner`) y es el **único** sitio donde vive la regla. Toda vista que
  modifique la bóveda lleva `@require_write`; toda vista de administración,
  `@require_owner`. Olvidarlo es el fallo fácil: la vista quedaría abierta a los
  invitados de sólo lectura.
- En la API v1 el permiso efectivo es el **menor** entre el rol de la cuenta y
  el flag `read_only` de la clave (`apps/api/auth.py`).
- El frontend esconde los botones que no tocan (clase `role-readonly` en el
  `<body>`, `CAN_WRITE` en `notes.js`, `{% if is_owner %}` en las plantillas).
  Eso es **cosmética**: nunca es la comprobación de seguridad.
- La cuenta propietaria no se puede degradar ni borrar desde ninguna interfaz,
  para que no exista forma de dejar el sitio sin dueño.
- Los avatares son un fichero por cuenta (`avatar-<id>.jpg`): con varios accesos,
  el `avatar.jpg` único de antes hacía que el último en subir foto pisara al resto.

## API pública (v1)

Control total de la bóveda desde fuera del navegador — curl, scripts o un agente de IA.

- **Documentación interactiva**: `/api/docs/` (Swagger UI autoalojado, sin CDN).
  El icono está en **Ajustes → Clave de API → Swagger**. Especificación cruda en
  `/api/v1/openapi.json`.
- **Autenticación**: clave de API, generada desde el mismo panel de Ajustes.
  `Authorization: Bearer cgny_…`, `X-API-Key: cgny_…` o `?api_key=` (esta última deja
  la clave en los logs de nginx; sólo para descargas directas).
- **Cobertura**: notas (CRUD, renombrar, mover, duplicar, edición parcial con
  find/replace), carpetas (CRUD + orden manual), adjuntos (subida multipart o base64,
  descarga), enlaces compartidos, bóveda entera (stats, export/import ZIP, optimizar
  imágenes a WebP), perfil, accesos invitados y gestión de las propias claves.
- **Claves de sólo lectura**: rechazan todo método distinto de GET/HEAD.

Detalles de implementación que conviene tener presentes al tocar esta parte:

- La API **no acepta la cookie de sesión**. Va exenta de CSRF, así que aceptar sesión
  convertiría cualquier web en un vector de CSRF autenticado; el navegador nunca manda
  `Authorization` por su cuenta, y con clave obligatoria el problema desaparece. Los
  endpoints que consume el propio frontend (`/api/apikeys/*`) sí van con sesión + CSRF.
- Las claves se guardan como HMAC-SHA256 con `SECRET_KEY`, no con PBKDF2: tienen 256
  bits de entropía aleatoria y se verifican en cada petición, así que un hash lento
  sólo costaría latencia.
- `apps/api/openapi.py` está escrito a mano. **Al añadir o cambiar un endpoint hay que
  actualizarlo**: es la única documentación de la API.
- La validación de rutas y el resto de operaciones de bóveda se reutilizan de
  `apps.notes.vault`, para no acabar con dos reglas de seguridad divergentes.

## Tests

```bash
DJANGO_SETTINGS_MODULE=config.settings.dev python manage.py test
```

81 tests en `tests/`, sin dependencias externas y sobre una bóveda temporal (nunca
tocan la real):

- `test_vault.py` — la capa de bóveda: rutas que intentan escapar (`..`, symlinks,
  profundidad), orden manual, escritura atómica, export/import (incluido un ZIP con
  rutas maliciosas) y búsqueda.
- `test_notes_web.py` — endpoints con sesión: CRUD de notas, adjuntos, compartir
  (contraseña, mover, revocar al borrar) y que el rol `viewer` no puede escribir.
- `test_api_v1.py` — API con clave: 401/403 según clave y rol, que la cookie de sesión
  NO abre la API, y el contrato de cada endpoint.

## Desarrollo

```bash
python -m venv venv && source venv/bin/activate
pip install -r ../requirements.txt
cp django_app/.env.example django_app/.env  # rellena DJANGO_SECRET_KEY
cd django_app && python manage.py migrate && python manage.py runserver
```

Crea el único usuario con `python manage.py createsuperuser` (no hay UI de registro).

## Despliegue

- Unit systemd real en producción: `cogny.service` (copia de referencia en
  `scripts/cogny.service`). Reiniciar con `systemctl restart cogny.service`.
- nginx: `proxy_pass http://127.0.0.1:8002`, `client_max_body_size 1024M`, `/static/`
  aliaseado a `django_app/static_collected/` (NO a `static/` — hace falta
  `collectstatic` tras cada cambio en assets).
- `manage.py collectstatic --noinput` después de cada cambio en CSS/JS globales,
  seguido de subir `ASSET_VERSION` en `.env` y reiniciar `cogny.service`.

## Variables de entorno (`.env`)

Ver `.env.example` para la lista completa. Las clave son `DJANGO_SECRET_KEY`,
`DJANGO_ALLOWED_HOSTS`, `DATA_ROOT`/`VAULT_ROOT`/`AVATARS_ROOT`, `ASSET_VERSION`.

## Estructura

```
config/             — settings, urls, wsgi
apps/               — 4 apps (ver lista arriba)
tests/              — suite de tests (manage.py test)
templates/          — base.html, del que heredan todas las páginas
static/js/          — JS común: csrf.js (envoltorio de fetch), app.js (menú + SW), settings-modal.js
static/             — CSS, iconos, vendor (marked, KaTeX, highlight.js, Swagger UI)
data/               — bóveda de notas y db.sqlite3
scripts/cogny.service — copia de referencia de la unidad systemd de producción
```

## Convenciones

- Custom `User` (`accounts.User`) configurado antes de la primera migración.
- `@login_required` + `@require_POST/GET` en todas las vistas del vault, más
  `@require_write` / `@require_owner` según el permiso que exija cada una.
- Variables globales de plantilla vía `apps.core.context_processors.global_context`.
- CSRF se envía vía header `X-CSRFToken`: `static/js/csrf.js` envuelve `fetch()` una
  sola vez para todo el sitio. Se carga sin `defer` a propósito, antes que ningún otro
  script.
- El servidor le habla al JS por un único objeto, `window.COGNY` (definido en
  `base.html`): csrf, versión de assets, host de subidas, y quién eres y qué puedes.
  No metas más `<script>` con lógica en las plantillas.
- La bóveda vive en un único directorio plano (`VAULT_ROOT`), sin separación por
  usuario: los accesos invitados comparten el mismo contenido y lo que cambia
  entre ellos es el permiso, no lo que ven.
