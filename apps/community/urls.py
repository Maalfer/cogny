"""Rutas de la bóveda comunitaria."""
from django.urls import path

from . import views

app_name = "community"

urlpatterns = [
    path("comunidad/", views.vault_page, name="vault_page"),
    # Enlace: canjea y redirige al vault con el permiso ya firmado en cookie.
    path("comunidad/enlace/<uuid:token>/", views.link_entry, name="link_entry"),
    # API del propio vault. Cuelga de "comunidad/" para que la puerta y los
    # datos compartan prefijo (mismo criterio que apps.knowledge).
    path("comunidad/api/tree", views.api_tree, name="api_tree"),
    path("comunidad/api/file", views.api_file_get, name="api_file_get"),
    path("comunidad/api/save", views.api_file_save, name="api_file_save"),
    path("comunidad/api/create", views.api_create, name="api_create"),
    path("comunidad/api/rename", views.api_rename, name="api_rename"),
    path("comunidad/api/move", views.api_move, name="api_move"),
    path("comunidad/api/reorder", views.api_reorder, name="api_reorder"),
    path("comunidad/api/delete", views.api_delete, name="api_delete"),
    path("comunidad/api/search", views.api_search, name="api_search"),
    path("comunidad/api/upload", views.api_upload, name="api_upload"),
    path("comunidad/api/asset", views.api_asset, name="api_asset"),
    path("comunidad/api/pdf", views.api_pdf, name="api_pdf"),
    path("comunidad/api/copy-to-private", views.api_copy_to_private, name="api_copy_to_private"),
]
