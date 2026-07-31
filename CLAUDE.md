# Cogny

Bóveda de notas en Markdown, autoalojada, estilo Obsidian. Django + gunicorn,
sin frontend framework. Las notas son ficheros en disco, no filas de base de
datos — la BD (SQLite) sólo guarda cuentas, sesiones, claves de API y la
configuración de la bóveda pública.

## Apps

- `apps/core` — helpers y middleware compartidos (`GlobalContextMiddleware`,
  `UploadCorsMiddleware`), utilidades HTTP comunes (`apps/core/api.py`:
  `error_response`, `json_body`, coerción de tipos del body JSON).
- `apps/accounts` — login, perfil, ajustes, avatar, tema, roles y claves de
  API. Reglas de cuenta en `apps/accounts/services.py`; permisos por rol en
  `apps/accounts/permissions.py` (`require_write`, `require_owner` — la
  comprobación es siempre de servidor, el frontend sólo esconde botones).
- `apps/notes` — el vault en sí: árbol de carpetas, edición, adjuntos,
  export/import ZIP, enlaces públicos de sólo lectura. Todo lo que toca disco
  vive en `apps/notes/vault.py` (rutas seguras vía `safe_path`, orden manual
  de carpetas, escritura atómica, búsqueda, stats, optimización a WebP);
  `apps/notes/pdf.py` exporta una nota a PDF con Chromium headless.
- `apps/knowledge` — bóveda pública de sólo lectura en `/conocimiento`, para
  compartir la misma bóveda de `apps.notes` hacia fuera sin exponer el editor.
  Dos formas de entrar: por dominio de origen permitido (`Referer`/`Origin`,
  ver aviso en `apps/knowledge/access.py` — es una puerta blanda, no control
  de acceso real) o por enlace maestro (`MasterLink`, token UUID4 revocable).
  El permiso se firma en una cookie (`django.core.signing`) para no depender
  del `Referer` en cada navegación.
- `apps/api` — API pública v1 autenticada por clave (`apps/api/auth.py`) +
  Swagger en `/api/docs/` (`apps/api/openapi.py`).

**La lógica no vive en las vistas.** Hay dos entradas al mismo sistema — la
web con sesión y la API con clave —, así que las vistas sólo validan la
petición y traducen el resultado; lo que hace de verdad el trabajo está en
los módulos de servicio de arriba. Si añades una operación, va en el módulo
de servicio y la exponen las dos capas.

## Settings

`config/settings/base.py` + `dev.py` (DEBUG, sin HTTPS) + `prod.py` (cookies
seguras, HSTS, detrás de nginx). `.env` en la raíz se carga a mano en
`base.py` (sin `python-dotenv`); variables clave: `DJANGO_SECRET_KEY`,
`DJANGO_ALLOWED_HOSTS`, `DATA_ROOT`/`VAULT_ROOT`/`AVATARS_ROOT`/`DB_PATH`,
`ASSET_VERSION` (cache-busting de estáticos), `UPLOAD_HOST`. `VERSION` es un
fichero en la raíz, no una variable — súbelo en cada release junto al tag de
git (`VERSION` + badge de `README.md` + tag `vX.Y.Z`).

## Tests

`tests/` a nivel de raíz, uno por área (`test_vault.py`, `test_notes_web.py`,
`test_api_v1.py`, `test_knowledge.py`). Usan un `DATA_ROOT` propio y aislado
(no `/tmp` compartido) para no interferir entre tests ni con una bóveda real.

## Docker / despliegue

`docker compose up --build` levanta todo en `localhost:8000` con SQLite y
datos en `./data` (ver `docker-compose.yml`). `scripts/docker-entrypoint.sh`
aplica `migrate` y `collectstatic` antes de arrancar gunicorn — no hace falta
tocarlo al añadir apps o migraciones nuevas, es genérico.

En producción, `scripts/cogny.service` es la unidad systemd de referencia
(gunicorn detrás de nginx con TLS). Tras tocar estáticos: `collectstatic`,
subir `ASSET_VERSION` en `.env` y reiniciar el servicio.

## Qué NO va al repo

Ver `.gitignore`: la bóveda de notas real, avatares, `db.sqlite3`, `.env` y
cualquier `*.bak*` de edición son datos de cada instalación, nunca contenido
de git. `README.md` es la cara pública del proyecto (con capturas y badge de
versión) — no lo sustituyas por documentación interna; si necesitas describir
arquitectura para trabajar en el código, este fichero es el sitio.
