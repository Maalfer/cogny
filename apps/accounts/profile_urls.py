"""APIs de perfil en el path antiguo /api/profile/*."""
from django.urls import path
from . import views

app_name = "profile_api"
urlpatterns = [
    path("upload-picture",  views.upload_picture,  name="upload_picture"),
    path("change-username", views.change_username, name="change_username"),
    path("change-password", views.change_password, name="change_password"),
    path("set-theme",       views.set_theme,       name="set_theme"),
]
