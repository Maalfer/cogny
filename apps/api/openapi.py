"""Especificación OpenAPI 3.1 de la API v1, escrita a mano.

A mano y no autogenerada a propósito: la API son vistas Django planas (sin DRF)
y meter un generador sólo para esto traería un árbol de dependencias entero.
Con ~30 endpoints estables, el coste de mantener este fichero es menor.

Al añadir o cambiar un endpoint en `views.py`, actualiza también su entrada
aquí: `/api/docs/` es la única documentación de la API.
"""

_DESCRIPTION = """
Control total de la bóveda de notas **Cogny** desde fuera del navegador: curl,
scripts, o un agente de IA (Claude, ChatGPT…).

### Autenticación

Todos los endpoints necesitan una clave de API. Genérala en la web:
**Ajustes → Clave de API → Generar clave**. El secreto se muestra **una sola
vez**, cópialo en ese momento.

Envíala en cada petición de una de estas formas:

```bash
curl -H "Authorization: Bearer cgny_xxxxxxxx_yyyy..." https://HOST/api/v1/me
curl -H "X-API-Key: cgny_xxxxxxxx_yyyy..."            https://HOST/api/v1/me
```

También se acepta `?api_key=` en la URL para descargas directas desde el
navegador, pero deja la clave escrita en los logs del servidor: úsalo sólo
cuando no puedas mandar cabeceras.

### Permisos

El permiso efectivo es el **menor** entre el rol de la cuenta y el de la clave:

| | `viewer` | `editor` | `owner` |
|---|---|---|---|
| Leer, buscar, exportar | ✅ | ✅ | ✅ |
| Crear / editar / borrar / compartir | ❌ | ✅ | ✅ |
| Gestionar accesos y claves de API | ❌ | ❌ | ✅ |

Una clave marcada como **sólo lectura** rechaza con `403` cualquier método que
no sea `GET` o `HEAD`, aunque su cuenta sea propietaria. Ningún `GET` de esta
API modifica nada, así que la regla cubre todas las escrituras (incluida
`POST /vault/optimize-images`).

### Rutas del vault

Casi todos los endpoints reciben un parámetro `path`: la ruta **relativa a la
raíz de la bóveda**, con `/` como separador y la extensión `.md` incluida para
las notas. Ejemplo: `Hacking/CTF/Máquina X.md`. Las rutas con `..` o que se
salgan de la bóveda se rechazan.

### Errores

Todos los errores devuelven `{"error": "mensaje"}` con el código HTTP adecuado
(`400` petición inválida, `401` clave ausente/errónea, `403` clave de sólo
lectura o contraseña incorrecta, `404` no existe, `409` conflicto de nombres,
`413` demasiado grande).
""".strip()


def _resp(desc, schema=None, ref=None):
    content = None
    if ref:
        content = {"application/json": {"schema": {"$ref": f"#/components/schemas/{ref}"}}}
    elif schema:
        content = {"application/json": {"schema": schema}}
    out = {"description": desc}
    if content:
        out["content"] = content
    return out


_ERRORS = {
    "400": _resp("Petición inválida", ref="Error"),
    "401": _resp("Clave de API ausente o inválida", ref="Error"),
    "403": _resp("Clave de sólo lectura, o credenciales incorrectas", ref="Error"),
    "404": _resp("No encontrado", ref="Error"),
}


def _json_body(properties, required=(), example=None):
    schema = {"type": "object", "properties": properties}
    if required:
        schema["required"] = list(required)
    media = {"schema": schema}
    if example:
        media["example"] = example
    return {"required": True, "content": {"application/json": media}}


def _param(name, desc, where="query", required=False, schema=None, example=None):
    p = {"name": name, "in": where, "required": required,
         "description": desc, "schema": schema or {"type": "string"}}
    if example is not None:
        p["example"] = example
    return p


_PATH_Q = _param("path", "Ruta relativa dentro de la bóveda.", required=True,
                 example="Hacking/CTF/Máquina X.md")


def build_spec(request) -> dict:
    base = request.build_absolute_uri("/").rstrip("/")
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "Cogny API",
            "version": "1",
            "description": _DESCRIPTION,
        },
        "servers": [{"url": base, "description": "Este servidor"}],
        "security": [{"bearerAuth": []}, {"apiKeyAuth": []}],
        "tags": [
            {"name": "Meta", "description": "Identidad y estado de la clave."},
            {"name": "Notas", "description": "Crear, leer, editar, mover y borrar notas Markdown."},
            {"name": "Carpetas", "description": "Estructura de carpetas de la bóveda."},
            {"name": "Archivos", "description": "Adjuntos: imágenes, PDFs y demás."},
            {"name": "Compartir", "description": "Enlaces públicos a notas concretas."},
            {"name": "Bóveda", "description": "Operaciones sobre la bóveda entera."},
            {"name": "Perfil", "description": "Cuenta y preferencias."},
            {"name": "Accesos", "description": "Cuentas invitadas y sus permisos (sólo el propietario)."},
            {"name": "Claves", "description": "Gestión de las propias claves de API."},
        ],
        "components": {
            "securitySchemes": {
                "bearerAuth": {
                    "type": "http", "scheme": "bearer",
                    "description": "Cabecera `Authorization: Bearer cgny_...`",
                },
                "apiKeyAuth": {
                    "type": "apiKey", "in": "header", "name": "X-API-Key",
                    "description": "Cabecera `X-API-Key: cgny_...`",
                },
            },
            "schemas": {
                "Error": {
                    "type": "object",
                    "properties": {"error": {"type": "string"}},
                    "example": {"error": "Nota no encontrada"},
                },
                "Ok": {
                    "type": "object",
                    "properties": {"success": {"type": "boolean"}},
                    "example": {"success": True},
                },
                "Note": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Ruta relativa en la bóveda"},
                        "name": {"type": "string", "description": "Nombre sin la extensión .md"},
                        "folder": {"type": "string", "description": "Carpeta contenedora ('' si está en la raíz)"},
                        "size": {"type": "integer", "description": "Bytes"},
                        "updated": {"type": "integer", "description": "mtime (epoch en segundos)"},
                    },
                    "example": {"path": "Hacking/CTF/Máquina X.md", "name": "Máquina X",
                                "folder": "Hacking/CTF", "size": 8412, "updated": 1753441200},
                },
                "NoteWithContent": {
                    "allOf": [
                        {"$ref": "#/components/schemas/Note"},
                        {"type": "object", "properties": {
                            "content": {"type": "string", "description": "Markdown completo"}}},
                    ],
                },
                "File": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "name": {"type": "string"},
                        "ext": {"type": "string"},
                        "size": {"type": "integer"},
                        "updated": {"type": "integer"},
                    },
                },
                "TreeNode": {
                    "type": "object",
                    "description": "Nodo del árbol. `type` es `folder`, `note` o `file`; "
                                   "las carpetas traen `children` con sus hijos.",
                    "properties": {
                        "type": {"type": "string", "enum": ["folder", "note", "file"]},
                        "name": {"type": "string"},
                        "path": {"type": "string"},
                        "ext": {"type": "string"},
                        "updated": {"type": "integer"},
                        "children": {"type": "array",
                                     "items": {"$ref": "#/components/schemas/TreeNode"}},
                    },
                },
                "Share": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "name": {"type": "string"},
                        "token": {"type": "string"},
                        "url": {"type": "string", "description": "URL pública completa"},
                        "has_password": {"type": "boolean"},
                    },
                },
                "Access": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "username": {"type": "string"},
                        "role": {"type": "string", "enum": ["owner", "editor", "viewer"]},
                        "role_label": {"type": "string"},
                        "can_write": {"type": "boolean"},
                        "is_owner": {"type": "boolean"},
                        "last_login": {"type": ["string", "null"], "format": "date-time"},
                        "created_at": {"type": "string", "format": "date-time"},
                    },
                },
                "ApiKey": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "name": {"type": "string"},
                        "prefix": {"type": "string"},
                        "masked": {"type": "string", "description": "Clave enmascarada, apta para mostrar"},
                        "read_only": {"type": "boolean"},
                        "revoked": {"type": "boolean"},
                        "created_at": {"type": "string", "format": "date-time"},
                        "last_used_at": {"type": ["string", "null"], "format": "date-time"},
                    },
                },
            },
        },
        "paths": _paths(),
    }


def _paths() -> dict:
    return {
        # ── Meta ──────────────────────────────────────────────────────────
        "/api/v1/me": {
            "get": {
                "tags": ["Meta"],
                "summary": "Quién soy",
                "description": "Devuelve el usuario, la versión de la app y los datos "
                               "de la clave con la que estás entrando. Útil como "
                               "comprobación rápida de que la clave funciona.",
                "responses": {
                    "200": _resp("OK", {"type": "object", "properties": {
                        "username": {"type": "string"},
                        "theme": {"type": "string"},
                        "role": {"type": "string", "enum": ["owner", "editor", "viewer"]},
                        "can_write": {"type": "boolean", "description": "Permiso efectivo (rol de la cuenta ∧ clave)"},
                        "version": {"type": "string"},
                        "docs": {"type": "string", "description": "URL de esta documentación"},
                        "key": {"$ref": "#/components/schemas/ApiKey"},
                    }}),
                    **_ERRORS,
                },
            },
        },

        # ── Notas ─────────────────────────────────────────────────────────
        "/api/v1/tree": {
            "get": {
                "tags": ["Notas"],
                "summary": "Árbol completo de la bóveda",
                "description": "Estructura jerárquica de carpetas, notas y archivos, "
                               "en el mismo orden que muestra la web.",
                "parameters": [_param("path", "Subárbol a devolver. Vacío = la bóveda entera.")],
                "responses": {
                    "200": _resp("OK", {"type": "object", "properties": {
                        "path": {"type": "string"},
                        "tree": {"type": "array",
                                 "items": {"$ref": "#/components/schemas/TreeNode"}},
                    }}),
                    **_ERRORS,
                },
            },
        },
        "/api/v1/notes": {
            "get": {
                "tags": ["Notas"],
                "summary": "Lista plana de notas",
                "description": "Todas las notas de la bóveda, sin contenido. Para el "
                               "contenido usa `/api/v1/notes/content`.",
                "parameters": [
                    _param("folder", "Limitar a una carpeta (recursivo).", example="Hacking"),
                    _param("limit", "Máximo de resultados (1-20000, por defecto 1000).",
                           schema={"type": "integer", "default": 1000}),
                ],
                "responses": {
                    "200": _resp("OK", {"type": "object", "properties": {
                        "count": {"type": "integer"},
                        "truncated": {"type": "boolean", "description": "`true` si se alcanzó `limit` y quedan más notas"},
                        "notes": {"type": "array",
                                  "items": {"$ref": "#/components/schemas/Note"}},
                    }}),
                    **_ERRORS,
                },
            },
            "post": {
                "tags": ["Notas"],
                "summary": "Crear una nota",
                "description": "Crea la nota y las carpetas intermedias que falten. "
                               "Falla con 409 si ya existe: para sobrescribir usa "
                               "`PUT /api/v1/notes/content`.",
                "requestBody": _json_body({
                    "path": {"type": "string", "description": "Ruta completa. La extensión `.md` se añade sola si falta."},
                    "parent": {"type": "string", "description": "Alternativa a `path`: carpeta destino."},
                    "name": {"type": "string", "description": "Alternativa a `path`: nombre de la nota."},
                    "content": {"type": "string", "description": "Markdown inicial (opcional)."},
                }, example={"path": "Hacking/CTF/Máquina Nueva.md",
                            "content": "# Máquina Nueva\n\n## Reconocimiento\n"}),
                "responses": {
                    "201": _resp("Creada", {"type": "object", "properties": {
                        "success": {"type": "boolean"},
                        "note": {"$ref": "#/components/schemas/Note"}}}),
                    "409": _resp("Ya existe una nota en esa ruta", ref="Error"),
                    **_ERRORS,
                },
            },
            "delete": {
                "tags": ["Notas"],
                "summary": "Borrar una nota",
                "description": "Borra la nota y revoca su enlace público si lo tenía. "
                               "No hay papelera: es irreversible.",
                "parameters": [_PATH_Q],
                "responses": {"200": _resp("Borrada", ref="Ok"), **_ERRORS},
            },
        },
        "/api/v1/notes/content": {
            "get": {
                "tags": ["Notas"],
                "summary": "Leer el Markdown de una nota",
                "parameters": [_PATH_Q],
                "responses": {
                    "200": _resp("OK", ref="NoteWithContent"),
                    **_ERRORS,
                },
            },
            "put": {
                "tags": ["Notas"],
                "summary": "Sobrescribir una nota (la crea si no existe)",
                "description": "Idempotente: reemplaza el contenido entero. Máximo 5 MB.",
                "requestBody": _json_body({
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                }, required=["path", "content"],
                    example={"path": "Hacking/CTF/Máquina X.md",
                             "content": "# Máquina X\n\nContenido nuevo.\n"}),
                "responses": {
                    "200": _resp("Guardada", {"type": "object", "properties": {
                        "success": {"type": "boolean"},
                        "note": {"$ref": "#/components/schemas/Note"}}}),
                    "413": _resp("Nota demasiado grande", ref="Error"),
                    **_ERRORS,
                },
            },
            "patch": {
                "tags": ["Notas"],
                "summary": "Edición parcial (añadir texto o buscar y reemplazar)",
                "description": "La forma cómoda de editar desde un agente sin reenviar "
                               "la nota entera. Puedes combinar `find`/`replace` con "
                               "`append` y `prepend` en la misma llamada; el orden de "
                               "aplicación es reemplazo → prepend → append.",
                "requestBody": _json_body({
                    "path": {"type": "string"},
                    "append": {"type": "string", "description": "Texto a añadir al final."},
                    "prepend": {"type": "string", "description": "Texto a añadir al principio."},
                    "find": {"type": "string", "description": "Texto (o regex) a buscar."},
                    "replace": {"type": "string", "description": "Sustituto de `find`."},
                    "regex": {"type": "boolean", "description": "Tratar `find` como expresión regular de Python.", "default": False},
                    "all": {"type": "boolean", "description": "Reemplazar todas las apariciones en vez de sólo la primera.", "default": False},
                }, required=["path"],
                    example={"path": "Hacking/CTF/Máquina X.md",
                             "append": "\n## Lecciones aprendidas\n\n- Validar el Origin.\n"}),
                "responses": {
                    "200": _resp("Editada", {"type": "object", "properties": {
                        "success": {"type": "boolean"},
                        "note": {"$ref": "#/components/schemas/Note"}}}),
                    **_ERRORS,
                },
            },
        },
        "/api/v1/notes/rename": {
            "post": {
                "tags": ["Notas"],
                "summary": "Renombrar (sin cambiar de carpeta)",
                "description": "Vale para notas, carpetas y archivos. El enlace público "
                               "de la nota, si lo hay, se conserva.",
                "requestBody": _json_body({
                    "path": {"type": "string"},
                    "name": {"type": "string", "description": "Nombre nuevo. `.md` se añade solo en notas."},
                }, required=["path", "name"],
                    example={"path": "Hacking/CTF/Máquina X.md", "name": "Máquina X (resuelta)"}),
                "responses": {
                    "200": _resp("Renombrada", {"type": "object", "properties": {
                        "success": {"type": "boolean"}, "path": {"type": "string"}}}),
                    "409": _resp("Ya existe un elemento con ese nombre", ref="Error"),
                    **_ERRORS,
                },
            },
        },
        "/api/v1/notes/move": {
            "post": {
                "tags": ["Notas"],
                "summary": "Mover a otra carpeta",
                "description": "Vale para notas, carpetas y archivos. `target` vacío "
                               "mueve a la raíz de la bóveda.",
                "requestBody": _json_body({
                    "path": {"type": "string", "description": "Elemento a mover."},
                    "target": {"type": "string", "description": "Carpeta destino (debe existir)."},
                }, required=["path"],
                    example={"path": "Máquina X.md", "target": "Hacking/CTF"}),
                "responses": {
                    "200": _resp("Movida", {"type": "object", "properties": {
                        "success": {"type": "boolean"}, "path": {"type": "string"}}}),
                    "409": _resp("Ya existe un elemento con ese nombre en el destino", ref="Error"),
                    **_ERRORS,
                },
            },
        },
        "/api/v1/notes/duplicate": {
            "post": {
                "tags": ["Notas"],
                "summary": "Duplicar una nota",
                "description": "Copia la nota en su misma carpeta. Sin `name`, añade "
                               "un sufijo numérico libre.",
                "requestBody": _json_body({
                    "path": {"type": "string"},
                    "name": {"type": "string", "description": "Nombre de la copia (opcional)."},
                }, required=["path"]),
                "responses": {
                    "201": _resp("Duplicada", {"type": "object", "properties": {
                        "success": {"type": "boolean"},
                        "note": {"$ref": "#/components/schemas/Note"}}}),
                    **_ERRORS,
                },
            },
        },
        "/api/v1/search": {
            "get": {
                "tags": ["Notas"],
                "summary": "Buscar en el contenido de las notas",
                "description": "Devuelve las notas que contienen **todos** los términos "
                               "(sin distinguir mayúsculas), con un fragmento de contexto.",
                "parameters": [
                    _param("q", "Términos separados por espacios.", required=True, example="csrf token"),
                    _param("limit", "Máximo de resultados (1-500, por defecto 50).",
                           schema={"type": "integer", "default": 50}),
                ],
                "responses": {
                    "200": _resp("OK", {"type": "object", "properties": {
                        "count": {"type": "integer"},
                        "results": {"type": "array", "items": {
                            "allOf": [
                                {"$ref": "#/components/schemas/Note"},
                                {"type": "object", "properties": {"snippet": {"type": "string"}}},
                            ]}},
                    }}),
                    **_ERRORS,
                },
            },
        },

        # ── Carpetas ──────────────────────────────────────────────────────
        "/api/v1/folders": {
            "get": {
                "tags": ["Carpetas"],
                "summary": "Lista de carpetas",
                "responses": {
                    "200": _resp("OK", {"type": "object", "properties": {
                        "count": {"type": "integer"},
                        "folders": {"type": "array", "items": {"type": "object", "properties": {
                            "path": {"type": "string"}, "name": {"type": "string"},
                            "notes": {"type": "integer", "description": "Notas directas (no recursivo)"}}}},
                    }}),
                    **_ERRORS,
                },
            },
            "post": {
                "tags": ["Carpetas"],
                "summary": "Crear una carpeta",
                "description": "Crea también las carpetas intermedias que falten.",
                "requestBody": _json_body({
                    "path": {"type": "string", "description": "Ruta completa de la carpeta nueva."},
                    "parent": {"type": "string", "description": "Alternativa a `path`."},
                    "name": {"type": "string", "description": "Alternativa a `path`."},
                }, example={"path": "Hacking/HackTheBox"}),
                "responses": {
                    "201": _resp("Creada", {"type": "object", "properties": {
                        "success": {"type": "boolean"}, "path": {"type": "string"}}}),
                    "409": _resp("Ya existe", ref="Error"),
                    **_ERRORS,
                },
            },
            "delete": {
                "tags": ["Carpetas"],
                "summary": "Borrar una carpeta y todo su contenido",
                "description": "**Recursivo e irreversible.** Revoca también los enlaces "
                               "públicos de las notas que contenía.",
                "parameters": [_param("path", "Carpeta a borrar.", required=True, example="Hacking/Pruebas")],
                "responses": {"200": _resp("Borrada", ref="Ok"), **_ERRORS},
            },
        },
        "/api/v1/folders/reorder": {
            "post": {
                "tags": ["Carpetas"],
                "summary": "Fijar el orden manual de una carpeta",
                "description": "Mismo orden que el drag & drop del árbol en la web. Los "
                               "nombres que no existan en la carpeta se ignoran; los que "
                               "falten quedan al final, alfabéticamente.",
                "requestBody": _json_body({
                    "folder": {"type": "string", "description": "Carpeta cuyo orden se fija ('' = raíz)."},
                    "order": {"type": "array", "items": {"type": "string"},
                              "description": "Nombres de los hijos directos, en orden. Las notas llevan `.md`."},
                }, required=["order"],
                    example={"folder": "Hacking", "order": ["CTF", "Notas.md"]}),
                "responses": {"200": _resp("OK", ref="Ok"), **_ERRORS},
            },
        },

        # ── Archivos ──────────────────────────────────────────────────────
        "/api/v1/files": {
            "get": {
                "tags": ["Archivos"],
                "summary": "Lista de adjuntos",
                "description": "Todo lo que no es `.md`: imágenes, PDFs, etc.",
                "parameters": [
                    _param("folder", "Limitar a una carpeta (recursivo).", example="Adjuntos"),
                    _param("limit", "Máximo de resultados (1-20000, por defecto 1000).",
                           schema={"type": "integer", "default": 1000}),
                ],
                "responses": {
                    "200": _resp("OK", {"type": "object", "properties": {
                        "count": {"type": "integer"},
                        "truncated": {"type": "boolean"},
                        "files": {"type": "array", "items": {"$ref": "#/components/schemas/File"}},
                    }}),
                    **_ERRORS,
                },
            },
            "post": {
                "tags": ["Archivos"],
                "summary": "Subir un adjunto",
                "description": "Dos formas:\n\n"
                               "- **`multipart/form-data`** con el campo `file`: igual que "
                               "la web — las imágenes ráster se recodifican a WebP y el "
                               "archivo va siempre a la carpeta `Adjuntos`.\n"
                               "- **JSON** con `content_base64`: se guarda tal cual, en la "
                               "carpeta que indiques.\n\n"
                               "Si ya hay un archivo con ese nombre se añade un sufijo "
                               "numérico en vez de sobrescribir. La respuesta incluye "
                               "`embed`, listo para pegar en una nota.",
                "requestBody": {
                    "required": True,
                    "content": {
                        "multipart/form-data": {"schema": {"type": "object", "properties": {
                            "file": {"type": "string", "format": "binary"}}, "required": ["file"]}},
                        "application/json": {"schema": {"type": "object", "properties": {
                            "name": {"type": "string", "description": "Nombre con extensión."},
                            "content_base64": {"type": "string", "description": "Contenido en base64."},
                            "folder": {"type": "string", "description": "Carpeta destino (por defecto `Adjuntos`)."},
                        }, "required": ["name", "content_base64"]}},
                    },
                },
                "responses": {
                    "201": _resp("Subido", {"type": "object", "properties": {
                        "success": {"type": "boolean"},
                        "file": {"$ref": "#/components/schemas/File"},
                        "embed": {"type": "string", "example": "![[diagrama.webp]]"}}}),
                    "413": _resp("Archivo demasiado grande", ref="Error"),
                    **_ERRORS,
                },
            },
            "delete": {
                "tags": ["Archivos"],
                "summary": "Borrar un adjunto",
                "parameters": [_param("path", "Ruta del adjunto.", required=True,
                                      example="Adjuntos/diagrama.webp")],
                "responses": {"200": _resp("Borrado", ref="Ok"), **_ERRORS},
            },
        },
        "/api/v1/files/content": {
            "get": {
                "tags": ["Archivos"],
                "summary": "Descargar un adjunto",
                "description": "Devuelve el binario con su `Content-Type`. Para incrustarlo "
                               "en un `<img>` puedes usar `?api_key=` (con la advertencia "
                               "sobre logs de la introducción).",
                "parameters": [_param("path", "Ruta del adjunto.", required=True,
                                      example="Adjuntos/diagrama.webp")],
                "responses": {
                    "200": {"description": "El fichero",
                            "content": {"application/octet-stream": {
                                "schema": {"type": "string", "format": "binary"}}}},
                    **_ERRORS,
                },
            },
        },

        # ── Compartir ─────────────────────────────────────────────────────
        "/api/v1/shares": {
            "get": {
                "tags": ["Compartir"],
                "summary": "Enlaces públicos activos",
                "responses": {
                    "200": _resp("OK", {"type": "object", "properties": {
                        "shares": {"type": "array",
                                   "items": {"$ref": "#/components/schemas/Share"}}}}),
                    **_ERRORS,
                },
            },
            "post": {
                "tags": ["Compartir"],
                "summary": "Compartir una nota (o cambiarle la contraseña)",
                "description": "Si la nota ya estaba compartida reutiliza el mismo token, "
                               "así que los enlaces repartidos siguen valiendo. "
                               "`password` vacío deja el enlace sin contraseña.",
                "requestBody": _json_body({
                    "path": {"type": "string"},
                    "password": {"type": "string", "description": "Opcional. Protege el enlace."},
                }, required=["path"],
                    example={"path": "Hacking/CTF/Máquina X.md", "password": ""}),
                "responses": {
                    "200": _resp("Compartida", {"type": "object", "properties": {
                        "success": {"type": "boolean"}, "token": {"type": "string"},
                        "url": {"type": "string"}, "has_password": {"type": "boolean"}}}),
                    **_ERRORS,
                },
            },
            "delete": {
                "tags": ["Compartir"],
                "summary": "Dejar de compartir",
                "description": "Por `path` o por `token`. El enlace deja de funcionar al instante.",
                "parameters": [
                    _param("path", "Ruta de la nota."),
                    _param("token", "Token del enlace (alternativa a `path`)."),
                ],
                "responses": {"200": _resp("Revocado", ref="Ok"), **_ERRORS},
            },
        },

        # ── Bóveda ────────────────────────────────────────────────────────
        "/api/v1/vault/stats": {
            "get": {
                "tags": ["Bóveda"],
                "summary": "Tamaño y conteos de la bóveda",
                "responses": {
                    "200": _resp("OK", {"type": "object", "properties": {
                        "total_bytes": {"type": "integer"},
                        "notes_bytes": {"type": "integer"},
                        "images_bytes": {"type": "integer"},
                        "other_bytes": {"type": "integer"},
                        "n_notes": {"type": "integer"},
                        "n_images": {"type": "integer"},
                        "n_other": {"type": "integer"},
                        "n_folders": {"type": "integer"}}}),
                    **_ERRORS,
                },
            },
        },
        "/api/v1/vault/export": {
            "get": {
                "tags": ["Bóveda"],
                "summary": "Descargar la bóveda entera en ZIP",
                "description": "Copia de seguridad completa: notas y adjuntos.",
                "responses": {
                    "200": {"description": "ZIP con toda la bóveda",
                            "content": {"application/zip": {
                                "schema": {"type": "string", "format": "binary"}}}},
                    **_ERRORS,
                },
            },
        },
        "/api/v1/vault/import": {
            "post": {
                "tags": ["Bóveda"],
                "summary": "Importar un ZIP de bóveda",
                "description": "`mode=merge` (por defecto) añade y sobrescribe lo que "
                               "coincida; **`mode=replace` borra la bóveda actual antes "
                               "de importar**.",
                "requestBody": {"required": True, "content": {"multipart/form-data": {
                    "schema": {"type": "object", "properties": {
                        "file": {"type": "string", "format": "binary"},
                        "mode": {"type": "string", "enum": ["merge", "replace"], "default": "merge"},
                    }, "required": ["file"]}}}},
                "responses": {"200": _resp("Importada", ref="Ok"), **_ERRORS},
            },
        },
        "/api/v1/vault/optimize-images": {
            "post": {
                "tags": ["Bóveda"],
                "summary": "Recodificar las imágenes de la bóveda a WebP",
                "description": "Convierte in-place las imágenes ráster que encojan al "
                               "pasar a WebP y actualiza las referencias `![[…]]` de las "
                               "notas. Puede tardar bastante en bóvedas grandes: la "
                               "respuesta llega cuando ha terminado todo el proceso.",
                "responses": {
                    "200": _resp("Resumen final", {"type": "object", "properties": {
                        "success": {"type": "boolean"},
                        "converted": {"type": "integer"},
                        "skipped": {"type": "integer"},
                        "saved_bytes": {"type": "integer"}}}),
                    **_ERRORS,
                },
            },
        },

        # ── Perfil ────────────────────────────────────────────────────────
        "/api/v1/profile": {
            "get": {
                "tags": ["Perfil"],
                "summary": "Datos de la cuenta",
                "responses": {
                    "200": _resp("OK", {"type": "object", "properties": {
                        "username": {"type": "string"}, "theme": {"type": "string"},
                        "last_login": {"type": ["string", "null"]},
                        "date_joined": {"type": "string"}}}),
                    **_ERRORS,
                },
            },
            "patch": {
                "tags": ["Perfil"],
                "summary": "Cambiar nombre de usuario o tema",
                "requestBody": _json_body({
                    "username": {"type": "string"},
                    "theme": {"type": "string", "enum": ["dark", "light", "dracula", "pink", "gold"]},
                }, example={"theme": "dracula"}),
                "responses": {
                    "200": _resp("Actualizado", {"type": "object", "properties": {
                        "success": {"type": "boolean"}, "username": {"type": "string"},
                        "theme": {"type": "string"}}}),
                    "409": _resp("Ese nombre ya existe", ref="Error"),
                    **_ERRORS,
                },
            },
        },
        "/api/v1/profile/password": {
            "post": {
                "tags": ["Perfil"],
                "summary": "Cambiar la contraseña",
                "description": "Exige la contraseña actual. No invalida las claves de API.",
                "requestBody": _json_body({
                    "current_password": {"type": "string"},
                    "new_password": {"type": "string"},
                }, required=["current_password", "new_password"]),
                "responses": {"200": _resp("Cambiada", ref="Ok"), **_ERRORS},
            },
        },

        # ── Accesos ───────────────────────────────────────────────────────
        "/api/v1/users": {
            "get": {
                "tags": ["Accesos"],
                "summary": "Listar los accesos al sitio",
                "description": "Incluye la cuenta propietaria y todos los invitados.",
                "responses": {
                    "200": _resp("OK", {"type": "object", "properties": {
                        "users": {"type": "array",
                                  "items": {"$ref": "#/components/schemas/Access"}}}}),
                    **_ERRORS,
                },
            },
            "post": {
                "tags": ["Accesos"],
                "summary": "Crear un acceso invitado",
                "description": "El invitado entra en la **misma** bóveda con el usuario y "
                               "contraseña que le des. `role` decide qué puede hacer: "
                               "`viewer` sólo lee, `editor` además escribe.",
                "requestBody": _json_body({
                    "username": {"type": "string"},
                    "password": {"type": "string"},
                    "role": {"type": "string", "enum": ["viewer", "editor"], "default": "viewer"},
                }, required=["username", "password"],
                    example={"username": "ana", "password": "una-contraseña-larga", "role": "viewer"}),
                "responses": {
                    "201": _resp("Creado", {"type": "object", "properties": {
                        "success": {"type": "boolean"},
                        "user": {"$ref": "#/components/schemas/Access"}}}),
                    **_ERRORS,
                },
            },
            "patch": {
                "tags": ["Accesos"],
                "summary": "Cambiar el permiso o la contraseña de un invitado",
                "description": "Cambiar la contraseña cierra además las sesiones que ese "
                               "invitado tuviera abiertas. La cuenta propietaria no se "
                               "puede modificar desde aquí.",
                "requestBody": _json_body({
                    "id": {"type": "integer"},
                    "role": {"type": "string", "enum": ["viewer", "editor"]},
                    "password": {"type": "string"},
                }, required=["id"], example={"id": 2, "role": "editor"}),
                "responses": {
                    "200": _resp("Actualizado", {"type": "object", "properties": {
                        "success": {"type": "boolean"},
                        "user": {"$ref": "#/components/schemas/Access"}}}),
                    **_ERRORS,
                },
            },
            "delete": {
                "tags": ["Accesos"],
                "summary": "Eliminar un acceso invitado",
                "description": "Irreversible: la cuenta deja de poder entrar. Las notas "
                               "no se tocan (la bóveda es del propietario).",
                "parameters": [_param("id", "ID del acceso.", required=True,
                                      schema={"type": "integer"})],
                "responses": {"200": _resp("Eliminado", ref="Ok"), **_ERRORS},
            },
        },

        # ── Claves ────────────────────────────────────────────────────────
        "/api/v1/keys": {
            "get": {
                "tags": ["Claves"],
                "summary": "Listar mis claves de API",
                "description": "Nunca devuelve el secreto: sólo el prefijo y la versión enmascarada.",
                "responses": {
                    "200": _resp("OK", {"type": "object", "properties": {
                        "keys": {"type": "array",
                                 "items": {"$ref": "#/components/schemas/ApiKey"}}}}),
                    **_ERRORS,
                },
            },
            "post": {
                "tags": ["Claves"],
                "summary": "Crear una clave nueva",
                "description": "El campo `key` de la respuesta es la **única** vez que se "
                               "ve el secreto completo. Guárdalo.",
                "requestBody": _json_body({
                    "name": {"type": "string", "description": "Para qué es (te ayuda a revocarla luego)."},
                    "read_only": {"type": "boolean", "default": False},
                }, example={"name": "Claude", "read_only": False}),
                "responses": {
                    "201": _resp("Creada", {"type": "object", "properties": {
                        "success": {"type": "boolean"},
                        "key": {"allOf": [
                            {"$ref": "#/components/schemas/ApiKey"},
                            {"type": "object", "properties": {
                                "key": {"type": "string", "description": "El secreto en claro. Sólo aparece aquí."}}},
                        ]}}}),
                    **_ERRORS,
                },
            },
        },
        "/api/v1/keys/{id}": {
            "delete": {
                "tags": ["Claves"],
                "summary": "Revocar una clave",
                "description": "Irreversible. Si revocas la clave con la que estás llamando, "
                               "la siguiente petición ya dará 401.",
                "parameters": [_param("id", "ID de la clave.", where="path", required=True,
                                      schema={"type": "integer"})],
                "responses": {"200": _resp("Revocada", ref="Ok"), **_ERRORS},
            },
        },
    }
