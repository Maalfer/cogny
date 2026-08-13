"""Páginas de pizarra: la galería y el lienzo de cada una."""
from django.urls import path

from . import views

app_name = "whiteboard"

urlpatterns = [
    path("pizarra/", views.gallery, name="gallery"),
    path("pizarra/<uuid:board_id>/", views.editor, name="editor"),
]
