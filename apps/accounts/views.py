"""Vistas de cuenta: login, logout, perfil, ajustes.

Sitio de un solo usuario: no hay alta de cuentas ni gestión de usuarios."""
import json

from django.conf import settings
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST

from .models import User

MAX_AVATAR_BYTES = 4 * 1024 * 1024


def _detect_image_kind(head: bytes) -> str | None:
    if head.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head.startswith(b"GIF87a") or head.startswith(b"GIF89a"):
        return "gif"
    if head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        return "webp"
    return None


def login_view(request):
    if request.user.is_authenticated:
        return redirect("home")
    error = ""
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        # Lookup case-insensitive (compatibilidad con COLLATE NOCASE antiguo).
        u = User.objects.filter(username__iexact=username).first() if username else None
        user = authenticate(request, username=u.username, password=password) if u else None
        if user:
            login(request, user)
            return redirect("home")
        error = "Usuario o contraseña incorrectos"
    return render(request, "accounts/login.html", {"error": error})


@require_POST
def logout_view(request):
    logout(request)
    return redirect("/")


@login_required
def profile(request):
    has_avatar = (settings.AVATARS_ROOT / f"{request.user.id}.jpg").exists()
    return render(request, "accounts/profile.html", {
        "user": request.user, "has_avatar": has_avatar,
    })


@login_required
@require_POST
def upload_picture(request):
    f = request.FILES.get("file")
    if not f:
        return JsonResponse({"error": "Falta archivo"}, status=400)
    if f.size > MAX_AVATAR_BYTES:
        return JsonResponse({"error": "Imagen demasiado grande (máx 4 MB)"}, status=400)
    head = f.read(32)
    if not _detect_image_kind(head):
        return JsonResponse({"error": "Sólo se permiten imágenes (jpg, png, webp, gif)"}, status=400)
    settings.AVATARS_ROOT.mkdir(parents=True, exist_ok=True)
    target = settings.AVATARS_ROOT / f"{request.user.id}.jpg"
    # OJO: f.chunks() hace seek(0) internamente, así que NO escribimos `head`
    # aparte (duplicaría los primeros 32 bytes y corrompería la imagen).
    with open(target, "wb") as fp:
        for chunk in f.chunks():
            fp.write(chunk)
    return JsonResponse({"success": True, "url": f"/static/avatars/{request.user.id}.jpg"})


@login_required
@require_POST
def change_username(request):
    data = json.loads(request.body or "{}")
    username = (data.get("username") or "").strip()
    if not username:
        return JsonResponse({"error": "Nombre vacío"}, status=400)
    try:
        UnicodeUsernameValidator()(username)
    except ValidationError:
        return JsonResponse({"error": "Sólo letras, números y @/./+/-/_"}, status=400)
    if User.objects.filter(username__iexact=username).exclude(pk=request.user.pk).exists():
        return JsonResponse({"error": "Ese nombre ya existe"}, status=400)
    request.user.username = username
    request.user.save(update_fields=["username"])
    return JsonResponse({"success": True, "username": request.user.username})


@login_required
@require_POST
def change_password(request):
    data = json.loads(request.body or "{}")
    cur = data.get("current_password", "")
    new = data.get("new_password", "")
    if not request.user.check_password(cur):
        return JsonResponse({"error": "Contraseña actual incorrecta"}, status=400)
    try:
        validate_password(new, user=request.user)
    except ValidationError as exc:
        return JsonResponse({"error": " ".join(exc.messages)}, status=400)
    request.user.set_password(new)
    request.user.save()
    update_session_auth_hash(request, request.user)
    return JsonResponse({"success": True})


@login_required
@require_POST
def set_theme(request):
    data = json.loads(request.body or "{}")
    theme = data.get("theme", "dark")
    if theme not in ("dark", "light", "dracula", "pink", "aqua"):
        return JsonResponse({"error": "Tema inválido"}, status=400)
    request.user.theme = theme
    request.user.save(update_fields=["theme"])
    return JsonResponse({"success": True})
