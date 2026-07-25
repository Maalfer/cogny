"""Vistas de cuenta: login, logout, perfil, ajustes, accesos invitados.

No hay registro público: los accesos los crea el propietario desde su perfil,
eligiendo si cada invitado entra en sólo lectura o con permiso de escritura.
Las reglas (validación, serialización, avatares) están en `services.py`, que
comparte con la API v1.
"""
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.api import as_int, as_optional_text, as_text, error_response as _err, json_body

from . import services
from .models import ApiKey, User
from .permissions import require_owner


def login_view(request):
    if request.user.is_authenticated:
        return redirect("root")
    error = ""
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        # Lookup case-insensitive (compatibilidad con COLLATE NOCASE antiguo).
        u = User.objects.filter(username__iexact=username).first() if username else None
        user = authenticate(request, username=u.username, password=password) if u else None
        if user:
            login(request, user)
            return redirect("root")
        error = "Usuario o contraseña incorrectos"
    return render(request, "accounts/login.html", {"error": error})


@require_POST
def logout_view(request):
    logout(request)
    return redirect("/")


@login_required
def profile(request):
    return render(request, "accounts/profile.html", {
        "user": request.user,
        "has_avatar": services.avatar_path(request.user).exists(),
        "guest_roles": User.ROLE_CHOICES,
    })


# ── Ajustes de la cuenta propia ──────────────────────────────────────────────

@login_required
@require_POST
def upload_picture(request):
    f = request.FILES.get("file")
    if not f:
        return _err("Falta archivo")
    if f.size > services.MAX_AVATAR_BYTES:
        return _err("Imagen demasiado grande (máx 4 MB)")
    if not services.detect_image_kind(f.read(32)):
        return _err("Sólo se permiten imágenes (jpg, png, webp, gif)")
    target = services.avatar_path(request.user)
    target.parent.mkdir(parents=True, exist_ok=True)
    # OJO: f.chunks() hace seek(0) internamente, así que NO escribimos aparte los
    # 32 bytes ya leídos (duplicarlos corrompería la imagen).
    with open(target, "wb") as fp:
        for chunk in f.chunks():
            fp.write(chunk)
    return JsonResponse({"success": True, "url": f"/static/avatars/{target.name}"})


@login_required
@require_POST
@json_body
def change_username(request):
    username = as_text(request.data.get("username")).strip()
    error = services.validate_username(username, exclude_pk=request.user.pk)
    if error:
        return _err(error)
    request.user.username = username
    request.user.save(update_fields=["username"])
    return JsonResponse({"success": True, "username": request.user.username})


@login_required
@require_POST
@json_body
def change_password(request):
    if not request.user.check_password(as_text(request.data.get("current_password"))):
        return _err("Contraseña actual incorrecta")
    new = as_text(request.data.get("new_password"))
    error = services.validate_new_password(new, user=request.user)
    if error:
        return _err(error)
    request.user.set_password(new)
    request.user.save()
    # Sin esto, cambiar la contraseña cerraría también la sesión desde la que se
    # está cambiando (el hash de sesión deja de casar).
    update_session_auth_hash(request, request.user)
    return JsonResponse({"success": True})


@login_required
@require_POST
@json_body
def set_theme(request):
    theme = request.data.get("theme", "dark")
    if theme not in dict(User.THEME_CHOICES):
        return _err("Tema inválido")
    request.user.theme = theme
    request.user.save(update_fields=["theme"])
    return JsonResponse({"success": True})


# ── Claves de API (panel de Ajustes) ─────────────────────────────────────────
# Estos endpoints van con sesión + CSRF, como el resto de la web. La API en sí
# (`/api/v1/`) sólo acepta clave de API: ver `apps.api.auth`.

@login_required
@require_owner
def api_keys_list(request):
    keys = ApiKey.objects.filter(user=request.user, revoked=False)
    return JsonResponse({"keys": [services.api_key_json(k) for k in keys]})


@login_required
@require_owner
@require_POST
@json_body
def api_keys_create(request):
    key, raw = ApiKey.objects.create_key(
        request.user,
        as_text(request.data.get("name")).strip(),
        read_only=bool(request.data.get("read_only")),
    )
    # `raw` viaja UNA sola vez: a partir de aquí en BD sólo queda el hash.
    return JsonResponse({"success": True, "key": {**services.api_key_json(key), "secret": raw}})


@login_required
@require_owner
@require_POST
@json_body
def api_keys_revoke(request):
    key = ApiKey.objects.filter(pk=as_int(request.data.get("id")), user=request.user).first()
    if not key:
        return _err("Clave no encontrada", 404)
    key.revoked = True
    key.save(update_fields=["revoked"])
    return JsonResponse({"success": True})


# ── Accesos invitados (sección "Accesos" del perfil) ─────────────────────────
# Todo esto es exclusivo del propietario. Los invitados comparten la MISMA
# bóveda: el rol decide si además de leer pueden escribir.

@login_required
@require_owner
def users_list(request):
    return JsonResponse({"users": [services.user_json(u) for u in User.objects.all()]})


@login_required
@require_owner
@require_POST
@json_body
def users_create(request):
    username = as_text(request.data.get("username")).strip()
    password = as_text(request.data.get("password"))
    role = as_optional_text(request.data.get("role"), User.ROLE_VIEWER)
    error = services.validate_new_user(username, password, role)
    if error:
        return _err(error)
    user = User.objects.create_user(username=username, password=password, role=role)
    return JsonResponse({"success": True, "user": services.user_json(user)}, status=201)


def _guest(request):
    """`(invitado, None)` o `(None, respuesta de error)`."""
    user, error, status = services.find_guest(as_int(request.data.get("id")))
    return (user, None) if user else (None, _err(error, status))


@login_required
@require_owner
@require_POST
@json_body
def users_set_role(request):
    user, err = _guest(request)
    if err:
        return err
    role = as_optional_text(request.data.get("role"), None)
    if role not in User.GUEST_ROLES:
        return _err("Permiso inválido")
    user.role = role
    user.save(update_fields=["role"])
    return JsonResponse({"success": True, "user": services.user_json(user)})


@login_required
@require_owner
@require_POST
@json_body
def users_set_password(request):
    user, err = _guest(request)
    if err:
        return err
    password = as_text(request.data.get("password"))
    error = services.validate_new_password(password, user=user)
    if error:
        return _err(error)
    user.set_password(password)
    user.save()
    # Invalida las sesiones abiertas de ese invitado: cambiar la contraseña
    # tiene que servir también para echar a quien esté dentro ahora mismo.
    return JsonResponse({"success": True})


@login_required
@require_owner
@require_POST
@json_body
def users_delete(request):
    user, err = _guest(request)
    if err:
        return err
    services.delete_guest(user)
    return JsonResponse({"success": True})
