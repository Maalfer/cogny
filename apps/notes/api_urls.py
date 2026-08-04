from django.urls import path
from . import views

app_name = "notes_api"

urlpatterns = [
    path("tree", views.tree, name="tree"),
    path("file", views.file_get, name="file_get"),
    path("save", views.file_save, name="file_save"),
    path("create", views.create, name="create"),
    path("rename", views.rename, name="rename"),
    path("move", views.move, name="move"),
    path("reorder", views.reorder, name="reorder"),
    path("delete", views.delete, name="delete"),
    path("search", views.search, name="search"),
    path("upload", views.upload, name="upload"),
    path("asset", views.asset, name="asset"),
    path("export", views.export_vault, name="export"),
    path("import", views.import_vault, name="import"),
    path("storage", views.storage, name="storage"),
    path("pdf", views.notes_pdf, name="pdf"),
    path("themes", views.themes_list, name="themes"),
    path("themes/save", views.theme_save, name="theme_save"),
    path("themes/delete", views.theme_delete, name="theme_delete"),
    path("themes/preview", views.theme_preview, name="theme_preview"),
    path("themes/image", views.theme_image, name="theme_image"),
    path("themes/image/upload", views.theme_image_upload, name="theme_image_upload"),
    path("themes/image/delete", views.theme_image_delete, name="theme_image_delete"),
    path("optimize-images", views.optimize_images, name="optimize_images"),
    path("share/create", views.share_create, name="share_create"),
    path("share/status", views.share_status, name="share_status"),
    path("share/list", views.share_list, name="share_list"),
    path("share/revoke", views.share_revoke, name="share_revoke"),
]
