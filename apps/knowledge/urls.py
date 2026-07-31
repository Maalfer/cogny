"""Rutas públicas de la bóveda de conocimiento."""
from django.urls import path

from . import views

app_name = "knowledge"

urlpatterns = [
    path("conocimiento/", views.reader, name="reader"),
    # Enlace maestro: canjea y redirige al lector con el permiso ya firmado.
    path("conocimiento/m/<uuid:token>/", views.master_entry, name="master_entry"),
    # API de lectura que consume el propio lector. Cuelga de /conocimiento/ para
    # que la puerta y los datos compartan prefijo y no se pueda tocar uno
    # creyendo que se protege el otro.
    path("conocimiento/api/tree", views.api_tree, name="api_tree"),
    path("conocimiento/api/note", views.api_note, name="api_note"),
    path("conocimiento/api/search", views.api_search, name="api_search"),
    path("conocimiento/api/asset", views.api_asset, name="api_asset"),
]
