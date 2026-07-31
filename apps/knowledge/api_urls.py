"""Endpoints de administración de la bóveda pública (propietario, con sesión).

Los consume la tarjeta "Bóveda pública" de /settings/.
"""
from django.urls import path

from . import views

app_name = "knowledge_api"

urlpatterns = [
    path("config", views.config_get, name="config_get"),
    path("config/save", views.config_save, name="config_save"),
    path("links", views.links_list, name="links_list"),
    path("links/create", views.links_create, name="links_create"),
    path("links/revoke", views.links_revoke, name="links_revoke"),
]
