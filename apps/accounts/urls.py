from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    path("login", views.login_view, name="login"),
    path("logout", views.logout_view, name="logout"),
    path("profile/", views.profile, name="profile"),
    path("api/profile/upload-picture", views.upload_picture, name="upload_picture"),
    path("api/profile/change-username", views.change_username, name="change_username"),
    path("api/profile/change-password", views.change_password, name="change_password"),
    path("api/profile/set-theme", views.set_theme, name="set_theme"),
]
