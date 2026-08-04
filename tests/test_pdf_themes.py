"""Temas de exportación a PDF: CRUD, imágenes, relleno de la plantilla y hoja.

La impresión en sí (Chromium headless) no se ejercita aquí: se prueban las
piezas que sí son de este proyecto —validación, ficheros y el documento que se
le da a imprimir—, que es donde puede romperse algo.
"""
import io

from apps.accounts.models import User
from apps.notes import pdf, themes
from apps.notes.models import PdfTheme, PdfThemeImage

from .base import VaultTestCase

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><rect width="10" height="10"/></svg>'
PLANTILLA = "<style>h1{color:red}</style><header>Acme</header>{{ contenido }}"


def _upload(data: bytes, name: str):
    f = io.BytesIO(data)
    f.name = name
    return f


class ThemeCrudTests(VaultTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.make_user())

    def _create(self, **extra):
        payload = {"name": "Acme", "html": PLANTILLA}
        payload.update(extra)
        return self.json_post("/api/notes/themes/save", payload)

    def test_crear_y_listar_un_tema(self):
        resp = self._create()
        self.assertEqual(resp.status_code, 200)
        theme = resp.json()["theme"]
        self.assertEqual(theme["name"], "Acme")
        self.assertEqual(theme["html"], PLANTILLA)
        listado = self.client.get("/api/notes/themes").json()
        self.assertEqual([t["id"] for t in listado["themes"]], [theme["id"]])
        # El listado NO lleva el HTML (son hasta 120 KB por tema); se pide aparte.
        self.assertNotIn("html", listado["themes"][0])
        self.assertIn("{{ contenido }}", listado["starter"])

    def test_el_html_de_un_tema_se_pide_por_id(self):
        theme_id = self._create().json()["theme"]["id"]
        resp = self.client.get(f"/api/notes/themes?id={theme_id}")
        self.assertEqual(resp.json()["theme"]["html"], PLANTILLA)
        self.assertEqual(self.client.get("/api/notes/themes?id=9999").status_code, 404)

    def test_una_plantilla_sin_contenido_no_se_guarda(self):
        # Sin el marcador el PDF saldría con la cabecera pero sin la nota.
        resp = self._create(html="<header>Acme</header>")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("{{ contenido }}", resp.json()["error"])
        self.assertEqual(PdfTheme.objects.count(), 0)

    def test_el_nombre_es_obligatorio(self):
        self.assertEqual(self._create(name="   ").status_code, 400)
        self.assertEqual(PdfTheme.objects.count(), 0)

    def test_una_plantilla_desmesurada_se_rechaza(self):
        resp = self._create(html="<!--" + "x" * themes.MAX_HTML_CHARS + "-->{{ contenido }}")
        self.assertEqual(resp.status_code, 400)

    def test_actualizar_un_tema_no_crea_otro(self):
        theme_id = self._create().json()["theme"]["id"]
        resp = self._create(id=theme_id, name="Acme Europa")
        self.assertEqual(resp.json()["theme"]["id"], theme_id)
        self.assertEqual(PdfTheme.objects.count(), 1)
        self.assertEqual(PdfTheme.objects.get().name, "Acme Europa")

    def test_un_tema_inexistente_no_se_actualiza_a_ciegas(self):
        self.assertEqual(self._create(id=9999).status_code, 404)

    def test_borrar_un_tema_se_lleva_sus_imagenes(self):
        theme_id = self._create().json()["theme"]["id"]
        self.client.post("/api/notes/themes/image/upload",
                         {"id": theme_id, "name": "logo", "file": _upload(PNG, "logo.png")})
        path = themes.image_path(PdfThemeImage.objects.get())
        self.assertTrue(path.exists())
        self.assertEqual(self.json_post("/api/notes/themes/delete", {"id": theme_id}).status_code, 200)
        self.assertFalse(PdfTheme.objects.exists())
        self.assertFalse(PdfThemeImage.objects.exists())
        self.assertFalse(path.exists())


class ThemeImageTests(VaultTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.make_user())
        self.theme = themes.save_theme({"name": "Acme", "html": PLANTILLA})

    def _upload_img(self, data, filename, name="logo"):
        return self.client.post("/api/notes/themes/image/upload",
                                {"id": self.theme.pk, "name": name,
                                 "file": _upload(data, filename)})

    def test_se_sube_la_imagen_y_queda_en_disco(self):
        resp = self._upload_img(PNG, "logo.png")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([i["name"] for i in resp.json()["theme"]["images"]], ["logo"])
        self.assertTrue(themes.image_path(PdfThemeImage.objects.get()).exists())

    def test_el_svg_se_reconoce_por_el_contenido(self):
        self._upload_img(SVG, "logo.txt")     # extensión mentirosa a propósito
        self.assertEqual(PdfThemeImage.objects.get().ext, "svg")

    def test_lo_que_no_es_imagen_se_rechaza(self):
        self.assertEqual(self._upload_img(b"MZ ejecutable", "logo.png").status_code, 400)
        self.assertFalse(PdfThemeImage.objects.exists())

    def test_repetir_el_nombre_sustituye_y_no_duplica(self):
        self._upload_img(PNG, "logo.png")
        antes = themes.image_path(PdfThemeImage.objects.get())
        self._upload_img(SVG, "logo.svg")
        self.assertEqual(PdfThemeImage.objects.count(), 1)
        self.assertFalse(antes.exists())          # el fichero viejo no se queda tirado
        self.assertEqual(PdfThemeImage.objects.get().ext, "svg")

    def test_el_nombre_de_la_imagen_no_escapa_del_directorio(self):
        # El nombre es sólo la etiqueta de `{{ img:… }}`: el fichero se guarda
        # por id, así que una ruta se queda en su último tramo y no escribe
        # fuera. Se comprueba porque el nombre lo elige quien sube el archivo.
        resp = self._upload_img(PNG, "logo.png", name="../../fuera")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(PdfThemeImage.objects.get().name, "fuera")
        self.assertFalse((self.tmp_root / "fuera.png").exists())
        self.assertTrue(themes.image_path(PdfThemeImage.objects.get())
                        .is_relative_to(themes.themes_root()))

    def test_un_nombre_con_caracteres_raros_se_rechaza(self):
        resp = self._upload_img(PNG, "logo.png", name="lo go/../$")
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(PdfThemeImage.objects.exists())

    def test_borrar_una_imagen_borra_el_fichero(self):
        self._upload_img(PNG, "logo.png")
        image = PdfThemeImage.objects.get()
        path = themes.image_path(image)
        resp = self.json_post("/api/notes/themes/image/delete", {"image": image.pk})
        self.assertEqual(resp.json()["theme"]["images"], [])
        self.assertFalse(path.exists())

    def test_la_imagen_se_sirve_sin_poder_ejecutarse(self):
        self._upload_img(SVG, "logo.svg")
        image = PdfThemeImage.objects.get()
        resp = self.client.get(f"/api/notes/themes/image?image={image.pk}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "image/svg+xml")
        self.assertIn("sandbox", resp["Content-Security-Policy"])
        self.assertEqual(resp["X-Content-Type-Options"], "nosniff")


class ThemePermissionTests(VaultTestCase):
    def setUp(self):
        super().setUp()
        self.theme = themes.save_theme({"name": "Acme", "html": PLANTILLA})
        self.client.force_login(self.make_user(username="lector", role=User.ROLE_VIEWER))

    def test_solo_lectura_puede_listar_para_exportar(self):
        resp = self.client.get("/api/notes/themes")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()["themes"]), 1)

    def test_solo_lectura_no_toca_los_temas(self):
        for url, payload in (("/api/notes/themes/save", {"name": "Otro", "html": PLANTILLA}),
                             ("/api/notes/themes/delete", {"id": self.theme.pk}),
                             ("/api/notes/themes/preview", {"html": PLANTILLA}),
                             ("/api/notes/themes/image/delete", {"image": 1})):
            self.assertEqual(self.json_post(url, payload).status_code, 403, url)
        resp = self.client.post("/api/notes/themes/image/upload",
                                {"id": self.theme.pk, "file": _upload(PNG, "logo.png")})
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(PdfTheme.objects.count(), 1)


class ThemeFillTests(VaultTestCase):
    """El relleno de marcadores y el documento que acaba imprimiéndose."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.make_user())

    def test_los_marcadores_se_sustituyen(self):
        out = themes.fill("<h1>{{ titulo }}</h1><i>{{ fecha }}</i>{{ contenido }}",
                          "<p>NOTA</p>", "Informe", {})
        self.assertIn("<h1>Informe</h1>", out)
        self.assertIn("<p>NOTA</p>", out)
        self.assertIn(" de ", out)          # la fecha en largo

    def test_el_titulo_se_escapa(self):
        out = themes.fill("{{ titulo }}{{ contenido }}", "", "<img onerror=x>", {})
        self.assertNotIn("<img", out)

    def test_las_imagenes_entran_como_data_uri(self):
        theme = themes.save_theme({"name": "Acme", "html": PLANTILLA})
        themes.add_image(theme, "logo", _django_upload(PNG, "logo.png"))
        out = themes.fill('<img src="{{ img:LOGO }}">{{ contenido }}', "", "t",
                          themes.image_map(theme))
        self.assertIn("data:image/png;base64,", out)   # el nombre no distingue mayúsculas

    def test_una_imagen_que_no_existe_no_deja_un_src_roto(self):
        out = themes.fill('<img src="{{ img:nada }}">{{ contenido }}', "", "t", {})
        self.assertIn('src=""', out)

    def test_los_marcadores_de_la_nota_no_se_resuelven(self):
        # Lo que escriba el usuario DENTRO de una nota es contenido, no plantilla.
        out = themes.fill("{{ contenido }}", "<p>{{ titulo }}</p>", "Secreto", {})
        self.assertNotIn("Secreto", out)

    def test_el_html_del_tema_pasa_por_el_saneador(self):
        # Aunque la plantilla la escriba el dueño, Chromium imprime desde
        # file:// : un src local sería lectura de ficheros del servidor.
        theme = themes.save_theme({"name": "Malo", "html": (
            '<script>alert(1)</script>'
            '<img src="file:///etc/passwd">'
            '<div style="background:url(file:///etc/passwd)">{{ contenido }}</div>')})
        doc = pdf._document("<p>hola</p>", theme=theme, title="t")
        self.assertNotIn("<script>", doc)
        self.assertNotIn("/etc/passwd", doc)
        self.assertIn("<p>hola</p>", doc)

    def test_sin_tema_el_documento_es_el_de_siempre(self):
        doc = pdf._document("<p>hola</p>")
        self.assertIn('<main class="markdown-body"><p>hola</p></main>', doc)
        self.assertIn("size:A4;", doc)

    def test_con_tema_la_nota_va_dentro_de_la_plantilla(self):
        theme = themes.save_theme({"name": "Acme", "html": PLANTILLA})
        doc = pdf._document("<p>hola</p>", theme=theme, title="t")
        self.assertIn("<header>Acme</header>", doc)
        self.assertIn('<main class="markdown-body"><p>hola</p></main>', doc)

    def test_el_apaisado_manda_sobre_el_tema(self):
        theme = themes.save_theme({"name": "Acme", "html": PLANTILLA})
        doc = pdf._document("<p>hola</p>", theme=theme, title="t", landscape=True)
        self.assertIn("size:A4 landscape", doc)
        self.assertIn('<body class="landscape">', doc)
        self.assertIn("column-count:2", doc)      # las dos columnas del apaisado

    def test_exportar_con_un_tema_que_ya_no_existe_es_404(self):
        resp = self.json_post("/api/notes/pdf", {"html": "<p>hola</p>", "title": "n", "theme": 9999})
        self.assertEqual(resp.status_code, 404)

    def test_la_plantilla_de_ejemplo_es_valida(self):
        # Se ofrece como punto de partida: si no pasara su propia validación,
        # el primer tema que creara alguien no se podría guardar.
        theme = themes.save_theme({"name": "Ejemplo", "html": themes.starter_html()})
        doc = pdf._document("<p>hola</p>", theme=theme, title="Informe")
        self.assertIn('<main class="markdown-body"><p>hola</p></main>', doc)
        self.assertIn("Informe", doc)


def _django_upload(data: bytes, name: str):
    from django.core.files.uploadedfile import SimpleUploadedFile
    return SimpleUploadedFile(name, data)
