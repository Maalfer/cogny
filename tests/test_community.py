"""Bóveda comunitaria `/comunidad`.

Lo que se comprueba aquí, por orden de importancia:

1. Que sin sesión de propietario ni enlace válido, no se entra a nada.
2. Que un enlace válido da lectura Y escritura completas (crear, editar,
   renombrar, mover, borrar) — a diferencia de `/conocimiento`.
3. Que todo eso ocurre en `COMMUNITY_VAULT_ROOT` y NUNCA en `VAULT_ROOT`: la
   bóveda comunitaria no puede tocar ni un byte de la privada.
4. Que revocar un enlace echa también a quien ya había entrado con él.
5. Que gestionar enlaces (crear/revocar) es sólo del propietario.
"""
from pathlib import Path
from unittest.mock import patch

from django.test import override_settings

from apps.accounts.models import User
from apps.community.access import COOKIE_NAME
from apps.community.models import CommunityLink
from apps.notes import pdf as notes_pdf

from .base import VaultTestCase

VAULT_PAGE = "/comunidad/"
API = "/comunidad/api"


class CommunityTestCase(VaultTestCase):
    """Añade una `COMMUNITY_VAULT_ROOT` propia, separada de `vault_dir`."""

    def setUp(self):
        super().setUp()
        self.community_dir = self.tmp_root / "community_vault"
        self.community_dir.mkdir()
        patcher = override_settings(COMMUNITY_VAULT_ROOT=self.community_dir)
        patcher.enable()
        self.addCleanup(patcher.disable)

    def write_community_note(self, rel: str, content: str = "hola") -> Path:
        target = self.community_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target


class NoAccessTests(CommunityTestCase):
    def test_sin_enlace_ni_sesion_no_se_entra(self):
        self.write_community_note("nota.md")
        # Páginas (community_view): 404, como /conocimiento cuando está apagada.
        self.assertEqual(self.client.get(VAULT_PAGE).status_code, 404)
        # API JSON (community_api): 403, con cuerpo de error.
        for url in (API + "/tree", API + "/file?path=nota.md", API + "/search?q=hola"):
            self.assertEqual(self.client.get(url).status_code, 403, url)
        resp = self.client.post(API + "/create", {"name": "x", "parent": ""},
                                content_type="application/json")
        self.assertEqual(resp.status_code, 403)

    def test_un_uuid_inventado_no_vale(self):
        self.assertEqual(self.client.get(
            "/comunidad/enlace/1e6b1b4e-0000-4000-8000-000000000000/").status_code, 404)


class OwnerSessionTests(CommunityTestCase):
    """El propietario entra directo, sin necesitar ningún enlace."""

    def test_el_propietario_entra_sin_enlace(self):
        self.client.force_login(self.make_user())
        self.assertEqual(self.client.get(VAULT_PAGE).status_code, 200)
        self.assertEqual(self.client.get(API + "/tree").status_code, 200)

    def test_un_usuario_no_propietario_sin_enlace_no_entra(self):
        self.client.force_login(self.make_user("invitado", role=User.ROLE_VIEWER))
        self.assertEqual(self.client.get(VAULT_PAGE).status_code, 404)


class LinkAccessTests(CommunityTestCase):
    def setUp(self):
        super().setUp()
        self.link = CommunityLink.objects.create(name="Amigos")
        self.write_community_note("Recetas/Tarta.md", "harina y azúcar")

    def _redeem(self):
        resp = self.client.get(f"/comunidad/enlace/{self.link.token}/")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], VAULT_PAGE)
        self.assertIn(COOKIE_NAME, resp.cookies)
        return resp

    def test_el_enlace_entra_y_lee_el_arbol(self):
        self._redeem()
        self.assertEqual(self.client.get(VAULT_PAGE).status_code, 200)
        tree = self.client.get(API + "/tree").json()["tree"]
        self.assertEqual([n["name"] for n in tree], ["Recetas"])

    def test_cuenta_las_visitas(self):
        self._redeem()
        self.link.refresh_from_db()
        self.assertEqual(self.link.visits, 1)
        self.assertIsNotNone(self.link.last_used_at)

    def test_el_permiso_aguanta_la_navegacion_siguiente(self):
        self._redeem()
        self.assertEqual(self.client.get(VAULT_PAGE).status_code, 200)
        self.assertEqual(self.client.get(API + "/tree").status_code, 200)

    def test_revocarlo_echa_tambien_a_quien_ya_habia_entrado(self):
        self._redeem()
        self.assertEqual(self.client.get(VAULT_PAGE).status_code, 200)
        self.link.revoked = True
        self.link.save(update_fields=["revoked"])
        self.assertEqual(self.client.get(VAULT_PAGE).status_code, 404)
        self.assertEqual(self.client.get(
            f"/comunidad/enlace/{self.link.token}/").status_code, 404)

    def test_un_permiso_falsificado_no_cuela(self):
        self.client.cookies[COOKIE_NAME] = "esto-no-viene-firmado-por-nosotros"
        self.assertEqual(self.client.get(VAULT_PAGE).status_code, 404)


class LinkWriteTests(CommunityTestCase):
    """Con el enlace se puede crear, editar, renombrar, mover y borrar —
    y nada de eso toca jamás `VAULT_ROOT` (la bóveda privada)."""

    def setUp(self):
        super().setUp()
        self.link = CommunityLink.objects.create(name="Amigos")
        self.client.get(f"/comunidad/enlace/{self.link.token}/")

    def test_crear_nota_y_carpeta(self):
        r = self.json_post(API + "/create", {"name": "Notas", "parent": "", "type": "folder"})
        self.assertEqual(r.json()["success"], True)
        r = self.json_post(API + "/create", {"name": "primera", "parent": "Notas", "type": "note"})
        self.assertEqual(r.json()["path"], "Notas/primera.md")
        self.assertTrue((self.community_dir / "Notas" / "primera.md").exists())

    def test_editar_renombrar_mover_borrar(self):
        self.write_community_note("a.md", "contenido")
        self.json_post(API + "/save", {"path": "a.md", "content": "editado"})
        self.assertEqual((self.community_dir / "a.md").read_text(), "editado")

        self.json_post(API + "/create", {"name": "Carpeta", "parent": "", "type": "folder"})
        r = self.json_post(API + "/move", {"path": "a.md", "target": "Carpeta"})
        self.assertEqual(r.json()["path"], "Carpeta/a.md")

        r = self.json_post(API + "/rename", {"path": "Carpeta/a.md", "name": "b.md"})
        self.assertEqual(r.json()["path"], "Carpeta/b.md")

        r = self.json_post(API + "/delete", {"path": "Carpeta/b.md"})
        self.assertTrue(r.json()["success"])

    def test_no_se_puede_mover_la_carpeta_de_adjuntos(self):
        (self.community_dir / "Adjuntos").mkdir()
        self.json_post(API + "/create", {"name": "Otra", "parent": "", "type": "folder"})
        r = self.json_post(API + "/move", {"path": "Adjuntos", "target": "Otra"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("adjuntos", r.json()["error"])
        self.assertTrue((self.community_dir / "Adjuntos").is_dir())
        self.assertFalse((self.community_dir / "Carpeta" / "b.md").exists())

    def test_nunca_se_toca_la_boveda_privada(self):
        self.json_post(API + "/create", {"name": "Notas", "parent": "", "type": "folder"})
        self.json_post(API + "/create", {"name": "hola", "parent": "Notas", "type": "note"})
        self.json_post(API + "/save", {"path": "Notas/hola.md", "content": "contenido comunitario"})
        # La bóveda privada, en su propio directorio temporal, sigue vacía.
        self.assertEqual(list(self.vault_dir.iterdir()), [])
        # Y lo escrito cae exactamente donde debe.
        self.assertTrue((self.community_dir / "Notas" / "hola.md").exists())

    def test_no_se_puede_salir_de_la_boveda_comunitaria(self):
        resp = self.client.get(API + "/file?path=../../etc/passwd")
        self.assertEqual(resp.status_code, 400)


class AdminEndpointTests(CommunityTestCase):
    """Crear/revocar enlaces es cosa del propietario y de nadie más."""

    def setUp(self):
        super().setUp()
        self.owner = self.make_user()

    def test_el_anonimo_no_gestiona_enlaces(self):
        self.assertEqual(self.client.get("/api/community/links").status_code, 302)
        self.assertEqual(self.json_post("/api/community/links/create",
                                        {"name": "x"}).status_code, 302)

    def test_un_invitado_no_gestiona_enlaces(self):
        self.client.force_login(self.make_user("invitado", role=User.ROLE_VIEWER))
        self.assertEqual(self.client.get("/api/community/links").status_code, 403)
        self.assertEqual(self.json_post("/api/community/links/create",
                                        {"name": "x"}).status_code, 403)

    def test_el_propietario_crea_y_revoca_enlaces(self):
        self.client.force_login(self.owner)
        created = self.json_post("/api/community/links/create", {"name": "Amigos"})
        self.assertEqual(created.status_code, 201)
        link_id = created.json()["link"]["id"]
        self.assertIn("/comunidad/enlace/", created.json()["link"]["url"])
        self.assertEqual(len(self.client.get("/api/community/links").json()["links"]), 1)

        self.assertEqual(self.json_post("/api/community/links/revoke",
                                        {"id": link_id}).status_code, 200)
        self.assertEqual(self.client.get("/api/community/links").json()["links"], [])
        self.assertTrue(CommunityLink.objects.get(pk=link_id).revoked)

    def test_se_pueden_tener_varios_enlaces_activos_a_la_vez(self):
        self.client.force_login(self.owner)
        self.json_post("/api/community/links/create", {"name": "Ana"})
        self.json_post("/api/community/links/create", {"name": "Bruno"})
        names = {l["name"] for l in self.client.get("/api/community/links").json()["links"]}
        self.assertEqual(names, {"Ana", "Bruno"})


class CopyBetweenVaultsTests(CommunityTestCase):
    """Copiar una nota o carpeta entre la bóveda privada y la comunitaria.

    Sólo el propietario puede hacerlo, en cualquiera de los dos sentidos —
    ni un rol de sólo lectura de la privada, ni quien sólo tenga un enlace
    comunitario, pueden mover contenido de una bóveda a la otra."""

    def setUp(self):
        super().setUp()
        self.owner = self.make_user()

    def test_copiar_nota_de_privada_a_comunitaria(self):
        self.write_note("Recetas/Tarta.md", "# Tarta\nharina y azúcar")
        self.client.force_login(self.owner)
        r = self.json_post("/api/notes/copy-to-community", {"path": "Recetas/Tarta.md"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["path"], "Tarta.md")
        self.assertEqual((self.community_dir / "Tarta.md").read_text(), "# Tarta\nharina y azúcar")
        # El original sigue intacto en la privada: es una COPIA, no un move.
        self.assertTrue((self.vault_dir / "Recetas" / "Tarta.md").exists())

    def test_copiar_carpeta_de_comunitaria_a_privada(self):
        self.write_community_note("Manual/Intro.md", "hola")
        self.write_community_note("Manual/Sub/Detalle.md", "más")
        self.client.force_login(self.owner)
        r = self.json_post("/comunidad/api/copy-to-private", {"path": "Manual"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["path"], "Manual")
        self.assertTrue((self.vault_dir / "Manual" / "Intro.md").exists())
        self.assertTrue((self.vault_dir / "Manual" / "Sub" / "Detalle.md").exists())

    def test_copia_trae_las_imagenes_referenciadas(self):
        (self.vault_dir / "Adjuntos").mkdir()
        (self.vault_dir / "Adjuntos" / "foto.webp").write_bytes(b"imagen-original")
        self.write_note("nota.md", "mira ![[foto.webp]]")
        self.client.force_login(self.owner)
        r = self.json_post("/api/notes/copy-to-community", {"path": "nota.md"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual((self.community_dir / "nota.md").read_text(), "mira ![[foto.webp]]")
        self.assertEqual((self.community_dir / "Adjuntos" / "foto.webp").read_bytes(), b"imagen-original")

    def test_colision_de_nombre_de_nota_se_resuelve_sin_pisar_nada(self):
        self.write_note("a.md", "de la privada")
        self.write_community_note("a.md", "de la comunitaria, no se toca")
        self.client.force_login(self.owner)
        r = self.json_post("/api/notes/copy-to-community", {"path": "a.md"})
        self.assertEqual(r.json()["path"], "a 2.md")
        self.assertEqual((self.community_dir / "a.md").read_text(), "de la comunitaria, no se toca")
        self.assertEqual((self.community_dir / "a 2.md").read_text(), "de la privada")

    def test_colision_de_adjunto_con_contenido_distinto_se_renombra_y_reescribe_la_referencia(self):
        (self.vault_dir / "Adjuntos").mkdir()
        (self.vault_dir / "Adjuntos" / "foto.webp").write_bytes(b"version-privada")
        self.write_note("nota.md", "mira ![[foto.webp]]")
        (self.community_dir / "Adjuntos").mkdir()
        (self.community_dir / "Adjuntos" / "foto.webp").write_bytes(b"version-comunitaria-distinta")
        self.client.force_login(self.owner)
        r = self.json_post("/api/notes/copy-to-community", {"path": "nota.md"})
        self.assertEqual(r.status_code, 200)
        new_content = (self.community_dir / "nota.md").read_text()
        self.assertNotIn("![[foto.webp]]", new_content)
        self.assertRegex(new_content, r"!\[\[foto \d+\.webp\]\]")
        self.assertEqual((self.community_dir / "Adjuntos" / "foto.webp").read_bytes(),
                         b"version-comunitaria-distinta")  # la ya existente no se toca

    def test_un_embed_glob_no_filtra_ficheros_ajenos(self):
        """`![[*]]` no debe tratarse como patrón de `rglob`: antes de la
        corrección, buscar el adjunto usaba el propio nombre del embed como
        patrón glob, así que `![[*]]` coincidía con CUALQUIER fichero de la
        bóveda origen (incluida cualquier otra nota o adjunto sin relación) y
        lo copiaba a la comunitaria — fuga de información entre bóvedas."""
        (self.vault_dir / "Adjuntos").mkdir()
        (self.vault_dir / "Adjuntos" / "secreto.png").write_bytes(b"dato privado sensible")
        self.write_note("Privada/otra-nota-cualquiera.md", "contenido que no debe salir")
        self.write_note("nota.md", "mira esto ![[*]]")
        self.client.force_login(self.owner)
        r = self.json_post("/api/notes/copy-to-community", {"path": "nota.md"})
        self.assertEqual(r.status_code, 200)
        # Ningún fichero real se llama "*": la referencia se deja rota tal
        # cual (como cualquier embed que ya apuntara a la nada), y sobre todo
        # no se copia NADA a Adjuntos/ de la comunitaria.
        self.assertFalse((self.community_dir / "Adjuntos").exists())
        self.assertEqual((self.community_dir / "nota.md").read_text(), "mira esto ![[*]]")

    def test_mismo_tamano_pero_contenido_distinto_no_se_confunden(self):
        """Dos adjuntos del mismo tamaño en bytes pero con contenido distinto
        no deben tratarse como el mismo fichero (antes se comparaba sólo el
        tamaño, y una coincidencia de tamaño por azar dejaba la nota copiada
        apuntando a la imagen equivocada, ya existente en destino)."""
        (self.vault_dir / "Adjuntos").mkdir()
        (self.vault_dir / "Adjuntos" / "foto.webp").write_bytes(b"AAAAAAAAAA")
        self.write_note("nota.md", "mira ![[foto.webp]]")
        (self.community_dir / "Adjuntos").mkdir()
        (self.community_dir / "Adjuntos" / "foto.webp").write_bytes(b"BBBBBBBBBB")  # mismo tamaño
        self.client.force_login(self.owner)
        r = self.json_post("/api/notes/copy-to-community", {"path": "nota.md"})
        self.assertEqual(r.status_code, 200)
        new_content = (self.community_dir / "nota.md").read_text()
        self.assertNotIn("![[foto.webp]]", new_content)
        self.assertRegex(new_content, r"!\[\[foto \d+\.webp\]\]")
        self.assertEqual((self.community_dir / "Adjuntos" / "foto.webp").read_bytes(), b"BBBBBBBBBB")

    def test_solo_el_propietario_puede_copiar_a_la_comunitaria(self):
        self.write_note("a.md", "x")
        self.client.force_login(self.make_user("invitado", role=User.ROLE_VIEWER))
        self.assertEqual(self.json_post("/api/notes/copy-to-community",
                                        {"path": "a.md"}).status_code, 403)
        self.client.logout()
        self.assertEqual(self.json_post("/api/notes/copy-to-community",
                                        {"path": "a.md"}).status_code, 302)

    def test_un_enlace_comunitario_no_basta_para_copiar_a_la_privada(self):
        """Escribir en la privada sigue siendo sólo del dueño, aunque quien
        pide la copia tenga un enlace comunitario válido de verdad."""
        link = CommunityLink.objects.create(name="x")
        self.client.get(f"/comunidad/enlace/{link.token}/")
        self.write_community_note("a.md", "x")
        self.assertEqual(self.json_post("/comunidad/api/copy-to-private",
                                        {"path": "a.md"}).status_code, 302)
        self.assertFalse((self.vault_dir / "a.md").exists())


class CommunityPdfTests(CommunityTestCase):
    """Exportar a PDF desde la comunitaria: estilos base/oscuro, sin temas."""

    def setUp(self):
        super().setUp()
        self.owner = self.make_user()

    def test_sin_sesion_ni_enlace_no_se_exporta(self):
        r = self.json_post("/comunidad/api/pdf", {"html": "<p>hola</p>"})
        self.assertEqual(r.status_code, 403)

    def test_el_propietario_exporta_sin_tema(self):
        self.client.force_login(self.owner)
        with patch.object(notes_pdf, "render", return_value=b"%PDF-1.4 fake") as render:
            r = self.json_post(API + "/pdf", {"html": "<p>hola</p>", "dark": True, "landscape": True})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertIsNone(render.call_args.kwargs.get("theme"))
        self.assertTrue(render.call_args.kwargs.get("dark"))
        self.assertTrue(render.call_args.kwargs.get("landscape"))

    def test_un_enlace_comunitario_tambien_puede_exportar(self):
        link = CommunityLink.objects.create(name="x")
        self.client.get(f"/comunidad/enlace/{link.token}/")
        with patch.object(notes_pdf, "render", return_value=b"%PDF-1.4 fake"):
            r = self.json_post(API + "/pdf", {"html": "<p>hola</p>"})
        self.assertEqual(r.status_code, 200)

    def test_un_id_de_tema_en_el_payload_se_ignora_por_completo(self):
        """No hay forma de que la comunitaria toque `PdfTheme` — es una tabla
        global compartida con la bóveda privada, y aquí no se lee `theme`."""
        self.client.force_login(self.owner)
        with patch.object(notes_pdf, "render", return_value=b"%PDF-1.4 fake") as render:
            self.json_post(API + "/pdf", {"html": "<p>hola</p>", "theme": 999999})
        self.assertIsNone(render.call_args.kwargs.get("theme"))

    def test_html_vacio_no_exporta(self):
        self.client.force_login(self.owner)
        r = self.json_post(API + "/pdf", {"html": "   "})
        self.assertEqual(r.status_code, 400)
