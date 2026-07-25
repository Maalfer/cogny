"""Rutas de la API v1 + la documentación Swagger."""
from django.urls import path, re_path

from . import views

app_name = "api"

urlpatterns = [
    # Documentación (públicas: sólo describen la forma de la API).
    path("", views.docs_redirect, name="docs_redirect"),
    path("docs/", views.docs, name="docs"),
    path("v1/openapi.json", views.openapi, name="openapi"),

    # Meta
    path("v1/me", views.me, name="me"),

    # Notas
    path("v1/tree", views.tree, name="tree"),
    path("v1/notes", views.notes, name="notes"),
    path("v1/notes/content", views.note_content, name="note_content"),
    path("v1/notes/rename", views.note_rename, name="note_rename"),
    path("v1/notes/move", views.note_move, name="note_move"),
    path("v1/notes/duplicate", views.note_duplicate, name="note_duplicate"),
    path("v1/search", views.search, name="search"),

    # Carpetas
    path("v1/folders", views.folders, name="folders"),
    path("v1/folders/reorder", views.folder_reorder, name="folder_reorder"),

    # Archivos
    path("v1/files", views.files, name="files"),
    path("v1/files/content", views.file_content, name="file_content"),

    # Compartir
    path("v1/shares", views.shares, name="shares"),

    # Bóveda
    path("v1/vault/stats", views.vault_stats, name="vault_stats"),
    path("v1/vault/export", views.vault_export, name="vault_export"),
    path("v1/vault/import", views.vault_import, name="vault_import"),
    path("v1/vault/optimize-images", views.vault_optimize_images, name="vault_optimize_images"),

    # Perfil
    path("v1/profile", views.profile, name="profile"),
    path("v1/profile/password", views.profile_password, name="profile_password"),

    # Accesos (sólo propietario)
    path("v1/users", views.users, name="users"),

    # Claves
    path("v1/keys", views.keys, name="keys"),
    path("v1/keys/<int:key_id>", views.key_revoke, name="key_revoke"),

    # Cualquier otra ruta bajo /api/v1 → 404 en JSON (va la última a propósito).
    re_path(r"^v1(/.*)?$", views.not_found, name="not_found"),
]
