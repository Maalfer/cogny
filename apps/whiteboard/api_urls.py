from django.urls import path

from . import views

app_name = "whiteboard_api"

urlpatterns = [
    path("list", views.list_boards, name="list"),
    path("create", views.create, name="create"),
    path("rename", views.rename, name="rename"),
    path("duplicate", views.duplicate, name="duplicate"),
    path("delete", views.delete, name="delete"),
    path("scene/save", views.scene_save, name="scene_save"),
    path("thumb/save", views.thumb_save, name="thumb_save"),
    path("thumb", views.thumb, name="thumb"),
]
