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
    path("api/apikeys/list", views.api_keys_list, name="api_keys_list"),
    path("api/apikeys/create", views.api_keys_create, name="api_keys_create"),
    path("api/apikeys/revoke", views.api_keys_revoke, name="api_keys_revoke"),
    # Accesos invitados (sólo propietario).
    path("api/users/list", views.users_list, name="users_list"),
    path("api/users/create", views.users_create, name="users_create"),
    path("api/users/set-role", views.users_set_role, name="users_set_role"),
    path("api/users/set-password", views.users_set_password, name="users_set_password"),
    path("api/users/delete", views.users_delete, name="users_delete"),
]
