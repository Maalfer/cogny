"""Endpoints de administración de la bóveda comunitaria (propietario, con sesión).

Los consume la tarjeta "Bóveda comunitaria" de /settings/.
"""
from django.urls import path

from . import views

app_name = "community_api"

urlpatterns = [
    path("links", views.links_list, name="links_list"),
    path("links/create", views.links_create, name="links_create"),
    path("links/revoke", views.links_revoke, name="links_revoke"),
]
