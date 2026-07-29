"""Middleware que inyecta variables globales (tema) y habilita el CORS de subidas."""
from django.conf import settings
from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin


class GlobalContextMiddleware(MiddlewareMixin):
    """Lee la cookie bh_theme y la expone como request.bh_theme."""

    def process_request(self, request):
        theme = request.COOKIES.get("bh_theme", "")
        if theme not in ("dark", "light", "dracula", "pink", "gold"):
            theme = ""
        # Si el usuario está autenticado y tiene un theme guardado, ese gana.
        if request.user.is_authenticated and getattr(request.user, "theme", None):
            theme = request.user.theme
        request.bh_theme = theme or "dark"
        return None

    def process_response(self, request, response):
        # Refresca la cookie con el tema actual para que el script inline del <html>
        # pueda leerlo antes de que cargue el CSS.
        theme = getattr(request, "bh_theme", None)
        if theme and request.COOKIES.get("bh_theme") != theme:
            response.set_cookie(
                "bh_theme", theme, max_age=60 * 60 * 24 * 365 * 5, samesite="Lax"
            )
        return response


class UploadCorsMiddleware(MiddlewareMixin):
    """CORS acotado al import de bóvedas desde el host de subidas DNS-only.

    El import de una bóveda completa puede pesar cientos de MB y Cloudflare corta
    en 100 MB, así que el cliente lo manda a `UPLOAD_HOST` (subdominio gris, fuera
    del proxy). Eso lo convierte en una petición cross-origin, que necesita:

    - responder al preflight `OPTIONS` (lo dispara la cabecera `X-CSRFToken`),
    - `Allow-Credentials` para que viaje la cookie de sesión — sin ella el import
      sería anónimo y devolvería 302 al login.

    Sólo se permite el origen canónico del sitio y sólo sobre `/api/notes/import`:
    este host esquiva Cloudflare, así que no debe abrir nada más.
    """

    _PATH = "/api/notes/import"

    def _allowed_origin(self, request):
        origin = request.headers.get("Origin", "")
        if not origin or request.path != self._PATH:
            return None
        canonical = {
            f"https://{h}" for h in settings.ALLOWED_HOSTS
            if h not in ("127.0.0.1", "localhost", "*")
            and h != getattr(settings, "UPLOAD_HOST", "")
        }
        return origin if origin in canonical else None

    def process_request(self, request):
        # Preflight: se responde antes de llegar a la vista (y antes de CSRF/auth).
        if request.method == "OPTIONS":
            origin = self._allowed_origin(request)
            if origin:
                resp = HttpResponse(status=204)
                resp["Access-Control-Allow-Origin"] = origin
                resp["Access-Control-Allow-Credentials"] = "true"
                resp["Access-Control-Allow-Methods"] = "POST, OPTIONS"
                resp["Access-Control-Allow-Headers"] = "X-CSRFToken, Content-Type"
                resp["Access-Control-Max-Age"] = "86400"
                resp["Vary"] = "Origin"
                return resp
        return None

    def process_response(self, request, response):
        origin = self._allowed_origin(request)
        if origin:
            response["Access-Control-Allow-Origin"] = origin
            response["Access-Control-Allow-Credentials"] = "true"
            response["Vary"] = "Origin"
        return response
