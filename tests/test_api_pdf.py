"""API v1 — exportar a PDF y gestionar temas con una clave de API.

El render en sí (Chromium con JS vía Playwright, `apps.notes.pdf_headless`) no
se ejercita aquí: es un proceso externo lento y ya se verificó a mano de punta
a punta (nota real con tabla/código/imagen/embed/KaTeX/Mermaid, claro y
oscuro, con y sin tema, apaisado, clave de sólo lectura). Aquí se prueba el
CABLEADO — rutas, permisos, códigos de error — que sí puede romperse sin que
un cambio futuro se dé cuenta, sustituyendo `render_note_to_html` por un doble
de pruebas. La gestión de temas reutiliza `apps.notes.themes` tal cual (ya
cubierto por `test_pdf_themes.py`): aquí sólo se prueba que el endpoint de la
API llega a esa misma lógica y respeta el permiso de la clave.
"""
from unittest.mock import patch

from apps.notes import pdf_headless
from apps.notes.models import PdfTheme, PdfThemeImage

from .test_api_v1 import ApiTestCase

PLANTILLA = "<style>h1{color:red}</style>{{ contenido }}"


class NotesPdfApiTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.write_note("Nota.md", "# Hola\n\nContenido.\n")

    def test_nota_inexistente_da_404(self):
        resp = self.api("get", "/api/v1/notes/pdf?path=No%20existe.md")
        self.assertEqual(resp.status_code, 404)

    def test_tema_inexistente_da_404_y_no_llega_a_renderizar(self):
        with patch.object(pdf_headless, "render_note_to_html") as render:
            resp = self.api("get", "/api/v1/notes/pdf?path=Nota.md&theme=9999")
        self.assertEqual(resp.status_code, 404)
        self.assertIn("tema", resp.json()["error"])
        render.assert_not_called()

    def test_theme_0_es_sin_tema_no_un_404(self):
        # `theme=0` llega como texto de querystring: antes se comparaba con
        # `if theme_raw:`, que trata la cadena "0" como verdadera y busca (sin
        # éxito) un PdfTheme de pk 0 — 404 espurio. Debe comportarse como si
        # no se hubiera mandado `theme`, igual que en la sesión web.
        with patch.object(pdf_headless, "render_note_to_html", return_value="<p>hola</p>"):
            resp = self.api("get", "/api/v1/notes/pdf?path=Nota.md&theme=0")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")

    def test_post_no_esta_permitido(self):
        # Exportar es lectura (GET): con POST sería una escritura innecesaria
        # y una clave de sólo lectura no podría usarlo aunque sólo lea.
        self.assertEqual(self.api("post", "/api/v1/notes/pdf", {"path": "Nota.md"}).status_code, 405)

    def test_exporta_con_una_clave_de_solo_lectura(self):
        _key, raw_ro = self._make_readonly_key()
        with patch.object(pdf_headless, "render_note_to_html", return_value="<p>hola</p>"):
            resp = self.api("get", "/api/v1/notes/pdf?path=Nota.md", raw=raw_ro)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")

    def test_render_headless_fallido_da_502(self):
        with patch.object(pdf_headless, "render_note_to_html",
                          side_effect=pdf_headless.HeadlessRenderError("tiempo agotado")):
            resp = self.api("get", "/api/v1/notes/pdf?path=Nota.md")
        self.assertEqual(resp.status_code, 502)

    def test_nota_vacia_tras_renderizar_no_genera_pdf(self):
        with patch.object(pdf_headless, "render_note_to_html", return_value="   "):
            resp = self.api("get", "/api/v1/notes/pdf?path=Nota.md")
        self.assertEqual(resp.status_code, 400)

    def test_exporta_de_verdad_con_el_render_headless_simulado(self):
        with patch.object(pdf_headless, "render_note_to_html",
                          return_value="<h1>Hola</h1><p>Contenido.</p>") as render:
            resp = self.api("get", "/api/v1/notes/pdf?path=Nota.md&landscape=1&dark=1")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")
        self.assertGreater(len(resp.content), 100)
        self.assertTrue(resp.content.startswith(b"%PDF"))
        # `landscape` se le pasa al render headless (decide el ensanchado de
        # bloques), no sólo al Chromium que imprime.
        render.assert_called_once()
        self.assertTrue(render.call_args.kwargs.get("landscape"))

    def _make_readonly_key(self):
        from apps.accounts.models import ApiKey
        return ApiKey.objects.create_key(self.user, "solo-lectura", read_only=True)


class RenderNoteToHtmlErrorHandlingTests(ApiTestCase):
    """`render_note_to_html` en sí (no la vista): que cualquier fallo de
    Playwright/su driver se convierta en `HeadlessRenderError` con un mensaje
    genérico — nunca en la excepción cruda escapando sin capturar, y nunca con
    el texto original de la excepción (que puede llevar la URL con el token
    firmado de un solo uso, ver el comentario en pdf_headless.py)."""

    def test_fallo_de_arranque_del_driver_no_se_escapa_sin_capturar(self):
        # `sync_playwright().__enter__()` puede dejar pasar la excepción
        # ORIGINAL de Python (típicamente FileNotFoundError) si el driver de
        # Node no arranca — no la envuelve en `playwright.sync_api.Error`.
        # Antes del fix sólo se capturaba `PlaywrightError`/`PlaywrightTimeoutError`,
        # así que esto se colaba hasta el `except OSError` genérico de
        # `api.auth.api_view`, que sí mete `str(exc)` (una ruta de fichero) en
        # la respuesta JSON.
        class _BrokenPlaywright:
            def __enter__(self):
                raise FileNotFoundError("/ruta/interna/al/driver/node")

            def __exit__(self, *a):
                return False

        with patch.object(pdf_headless, "sync_playwright", return_value=_BrokenPlaywright()):
            with self.assertRaises(pdf_headless.HeadlessRenderError) as ctx:
                pdf_headless.render_note_to_html(self.user, "Nota.md")
        self.assertNotIn("/ruta/interna/al/driver/node", str(ctx.exception))

    def test_error_de_conexion_no_filtra_la_url_con_el_token(self):
        # Playwright mete la URL navegada COMPLETA (token firmado incluido) en
        # el texto de sus excepciones de conexión — a diferencia de las de
        # timeout. Un fallo de conexión real (p.ej. INTERNAL_ORIGIN mal
        # configurado) no debe filtrar ese token en la respuesta de la API.
        class _FakeConnError(Exception):
            pass

        class _BrokenGoto:
            def __enter__(self):
                raise _FakeConnError(
                    "Page.goto: net::ERR_CONNECTION_REFUSED at "
                    "http://127.0.0.1:9/internal/pdf-headless/TOKEN-SECRETO/")

            def __exit__(self, *a):
                return False

        with patch.object(pdf_headless, "sync_playwright", return_value=_BrokenGoto()):
            with self.assertRaises(pdf_headless.HeadlessRenderError) as ctx:
                pdf_headless.render_note_to_html(self.user, "Nota.md")
        self.assertNotIn("TOKEN-SECRETO", str(ctx.exception))
        self.assertNotIn("pdf-headless", str(ctx.exception))


class PdfThemeApiTests(ApiTestCase):
    def _create(self, **extra):
        payload = {"name": "Acme", "html": PLANTILLA}
        payload.update(extra)
        return self.api("post", "/api/v1/pdf/themes", payload)

    def test_crear_listar_y_leer_un_tema(self):
        resp = self._create()
        self.assertEqual(resp.status_code, 201)
        theme = resp.json()["theme"]
        self.assertEqual(theme["html"], PLANTILLA)

        listado = self.api("get", "/api/v1/pdf/themes").json()
        self.assertEqual([t["id"] for t in listado["themes"]], [theme["id"]])
        self.assertNotIn("html", listado["themes"][0])
        self.assertIn("{{ contenido }}", listado["starter"])

        detalle = self.api("get", f"/api/v1/pdf/themes/{theme['id']}").json()
        self.assertEqual(detalle["theme"]["html"], PLANTILLA)

    def test_tema_sin_marcador_de_contenido_no_se_guarda(self):
        resp = self._create(html="<header>Acme</header>")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(PdfTheme.objects.count(), 0)

    def test_actualizar_conserva_los_campos_omitidos(self):
        theme_id = self._create().json()["theme"]["id"]
        resp = self.api("patch", f"/api/v1/pdf/themes/{theme_id}", {"name": "Acme Europa"})
        self.assertEqual(resp.status_code, 200)
        theme = resp.json()["theme"]
        self.assertEqual(theme["name"], "Acme Europa")
        self.assertEqual(theme["html"], PLANTILLA)   # no se mandó: se conserva
        self.assertEqual(PdfTheme.objects.count(), 1)

    def test_tema_inexistente_es_404_en_detalle_patch_y_delete(self):
        self.assertEqual(self.api("get", "/api/v1/pdf/themes/9999").status_code, 404)
        self.assertEqual(self.api("patch", "/api/v1/pdf/themes/9999", {"name": "x"}).status_code, 404)
        self.assertEqual(self.api("delete", "/api/v1/pdf/themes/9999").status_code, 404)

    def test_borrar_un_tema_se_lleva_sus_imagenes(self):
        theme_id = self._create().json()["theme"]["id"]
        upload = self._upload_png()
        self.client.post(f"/api/v1/pdf/themes/{theme_id}/images",
                         {"file": upload, "name": "logo"},
                         HTTP_AUTHORIZATION=f"Bearer {self.raw}")
        self.assertEqual(PdfThemeImage.objects.count(), 1)
        self.assertEqual(self.api("delete", f"/api/v1/pdf/themes/{theme_id}").status_code, 200)
        self.assertFalse(PdfThemeImage.objects.exists())

    def test_clave_de_solo_lectura_no_puede_crear_temas(self):
        from apps.accounts.models import ApiKey
        _key, raw_ro = ApiKey.objects.create_key(self.user, "solo-lectura", read_only=True)
        resp = self.api("post", "/api/v1/pdf/themes",
                        {"name": "Acme", "html": PLANTILLA}, raw=raw_ro)
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(PdfTheme.objects.count(), 0)

    def test_clave_de_solo_lectura_si_puede_listar(self):
        self._create()
        from apps.accounts.models import ApiKey
        _key, raw_ro = ApiKey.objects.create_key(self.user, "solo-lectura", read_only=True)
        resp = self.api("get", "/api/v1/pdf/themes", raw=raw_ro)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()["themes"]), 1)

    def _upload_png(self):
        import io
        f = io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
        f.name = "logo.png"
        return f


class PdfThemeImageApiTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        resp = self.api("post", "/api/v1/pdf/themes", {"name": "Acme", "html": PLANTILLA})
        self.theme_id = resp.json()["theme"]["id"]

    def _upload(self, name="logo.png", data=b"\x89PNG\r\n\x1a\n" + b"\x00" * 32):
        import io
        f = io.BytesIO(data)
        f.name = name
        resp = self.client.post(f"/api/v1/pdf/themes/{self.theme_id}/images",
                                {"file": f, "name": "logo"},
                                HTTP_AUTHORIZATION=f"Bearer {self.raw}")
        return resp

    def test_subir_descargar_y_borrar_una_imagen(self):
        resp = self._upload()
        self.assertEqual(resp.status_code, 201)
        image_id = PdfThemeImage.objects.get().pk

        get_resp = self.api("get", f"/api/v1/pdf/themes/{self.theme_id}/images/{image_id}")
        self.assertEqual(get_resp.status_code, 200)
        self.assertEqual(get_resp["Content-Security-Policy"], "default-src 'none'; style-src 'unsafe-inline'; sandbox")

        del_resp = self.api("delete", f"/api/v1/pdf/themes/{self.theme_id}/images/{image_id}")
        self.assertEqual(del_resp.status_code, 200)
        self.assertFalse(PdfThemeImage.objects.exists())

    def test_imagen_de_otro_tema_no_se_ve(self):
        self._upload()
        image_id = PdfThemeImage.objects.get().pk
        otro = self.api("post", "/api/v1/pdf/themes", {"name": "Otro", "html": PLANTILLA}).json()["theme"]["id"]
        resp = self.api("get", f"/api/v1/pdf/themes/{otro}/images/{image_id}")
        self.assertEqual(resp.status_code, 404)

    def test_sin_fichero_es_400(self):
        resp = self.api("post", f"/api/v1/pdf/themes/{self.theme_id}/images", {})
        self.assertEqual(resp.status_code, 400)
