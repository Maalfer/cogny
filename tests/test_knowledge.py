"""Bóveda pública `/conocimiento`.

Lo que se comprueba aquí, por orden de importancia:

1. Que apagada no existe, y encendida no deja escribir nada.
2. Que la única puerta de entrada es el enlace maestro: sin uno válido no se
   pasa, y revocarlo echa también a quien ya había entrado con él.
3. Que el permiso firmado sobrevive a la navegación una vez canjeado el
   enlace (no hay que repetirlo en cada página).
"""
from django.db import IntegrityError, transaction

from apps.accounts.models import User
from apps.knowledge.access import COOKIE_NAME
from apps.knowledge.models import MasterLink, PublicVault

from .base import VaultTestCase

READER = "/conocimiento/"
API = "/conocimiento/api"


class PublicVaultClosedTests(VaultTestCase):
    def test_apagada_la_boveda_publica_no_existe(self):
        self.write_note("nota.md", "hola")
        for url in (READER, API + "/tree", API + "/note?path=nota.md", API + "/search?q=hola"):
            self.assertEqual(self.client.get(url).status_code, 404, url)

    def test_apagada_un_enlace_maestro_tampoco_vale(self):
        link = MasterLink.objects.create(name="x")
        self.assertEqual(self.client.get(f"/conocimiento/m/{link.token}/").status_code, 404)


class PublicVaultOpenTests(VaultTestCase):
    """Encendida: sin un enlace maestro canjeado, nadie entra."""

    def setUp(self):
        super().setUp()
        cfg = PublicVault.get()
        cfg.enabled = True
        cfg.save()
        self.write_note("Linux/Permisos.md", "# Permisos\nchmod y chown")

    def test_sin_permiso_no_se_entra(self):
        resp = self.client.get(READER)
        self.assertEqual(resp.status_code, 403)
        self.assertTemplateUsed(resp, "knowledge/blocked.html")
        self.assertNotIn(COOKIE_NAME, resp.cookies)

    def test_la_api_rechaza_en_json_no_con_la_pagina_de_bloqueo(self):
        resp = self.client.get(API + "/tree")
        self.assertEqual(resp.status_code, 403)
        self.assertIn("error", resp.json())

    def test_un_permiso_falsificado_no_cuela(self):
        self.client.cookies[COOKIE_NAME] = "esto-no-viene-firmado-por-nosotros"
        self.assertEqual(self.client.get(READER).status_code, 403)


class MasterLinkTests(VaultTestCase):
    def setUp(self):
        super().setUp()
        cfg = PublicVault.get()
        cfg.enabled = True
        cfg.save()
        self.write_note("Linux/Permisos.md", "# Permisos\nchmod y chown")
        self.link = MasterLink.objects.create(name="Ponentes")

    def test_el_enlace_maestro_entra_y_firma_el_permiso(self):
        resp = self.client.get(f"/conocimiento/m/{self.link.token}/")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], READER)
        self.assertIn(COOKIE_NAME, resp.cookies)

    def test_el_permiso_aguanta_la_navegacion_siguiente(self):
        """Sin esto, habría que repetir el enlace maestro en cada página."""
        self.client.get(f"/conocimiento/m/{self.link.token}/")
        self.assertEqual(self.client.get(READER).status_code, 200)
        tree = self.client.get(API + "/tree").json()["tree"]
        self.assertEqual([n["name"] for n in tree], ["Linux"])

    def test_se_lee_una_nota_y_se_busca(self):
        self.client.get(f"/conocimiento/m/{self.link.token}/")
        note = self.client.get(API + "/note?path=Linux/Permisos.md").json()
        self.assertEqual(note["name"], "Permisos")
        self.assertIn("chmod", note["content"])
        hits = self.client.get(API + "/search?q=chown").json()["results"]
        self.assertEqual([h["path"] for h in hits], ["Linux/Permisos.md"])

    def test_no_se_puede_salir_de_la_boveda(self):
        self.client.get(f"/conocimiento/m/{self.link.token}/")
        resp = self.client.get(API + "/note?path=../../etc/passwd")
        self.assertEqual(resp.status_code, 400)

    def test_la_superficie_publica_no_tiene_por_donde_escribir(self):
        """Ni siquiera con el método correcto: estas vistas son sólo GET."""
        self.client.get(f"/conocimiento/m/{self.link.token}/")
        for url in (API + "/note", API + "/tree", API + "/search"):
            self.assertEqual(self.client.post(url, {}).status_code, 405, url)
        # Y las rutas de escritura de la web con sesión siguen pidiendo login
        # aunque la bóveda pública esté encendida.
        self.assertEqual(self.client.post(
            "/api/notes/save", data="{}", content_type="application/json").status_code, 302)

    def test_los_adjuntos_se_sirven_endurecidos(self):
        self.client.get(f"/conocimiento/m/{self.link.token}/")
        (self.vault_dir / "Adjuntos").mkdir()
        (self.vault_dir / "Adjuntos" / "diagrama.svg").write_text("<svg/>", encoding="utf-8")
        resp = self.client.get(API + "/asset?path=Adjuntos/diagrama.svg")
        self.assertEqual(resp.status_code, 200)
        # Un SVG servido en línea ejecuta JavaScript en nuestro propio origen.
        self.assertIn("attachment", resp["Content-Disposition"])
        self.assertEqual(resp["X-Content-Type-Options"], "nosniff")

    def test_las_notas_no_se_bajan_por_la_ruta_de_adjuntos(self):
        self.client.get(f"/conocimiento/m/{self.link.token}/")
        self.assertEqual(self.client.get(API + "/asset?path=Linux/Permisos.md").status_code, 404)

    def test_el_enlace_maestro_puede_abrir_una_nota_concreta(self):
        resp = self.client.get(f"/conocimiento/m/{self.link.token}/?n=nota.md")
        self.assertEqual(resp["Location"], "/conocimiento/?n=nota.md")

    def test_cuenta_las_visitas(self):
        self.client.get(f"/conocimiento/m/{self.link.token}/")
        self.link.refresh_from_db()
        self.assertEqual(self.link.visits, 1)
        self.assertIsNotNone(self.link.last_used_at)

    def test_revocarlo_echa_tambien_a_quien_ya_habia_entrado(self):
        self.client.get(f"/conocimiento/m/{self.link.token}/")
        self.assertEqual(self.client.get(READER).status_code, 200)
        self.link.revoked = True
        self.link.save(update_fields=["revoked"])
        self.assertEqual(self.client.get(READER).status_code, 403)
        self.assertEqual(self.client.get(f"/conocimiento/m/{self.link.token}/").status_code, 404)

    def test_un_uuid_inventado_no_vale(self):
        self.assertEqual(self.client.get(
            "/conocimiento/m/1e6b1b4e-0000-4000-8000-000000000000/").status_code, 404)


class AdminEndpointTests(VaultTestCase):
    """La configuración es cosa del propietario y de nadie más."""

    def setUp(self):
        super().setUp()
        self.owner = self.make_user()

    def test_el_anonimo_no_toca_la_configuracion(self):
        self.assertEqual(self.client.get("/api/knowledge/config").status_code, 302)
        self.assertEqual(self.json_post("/api/knowledge/config/save",
                                        {"enabled": True}).status_code, 302)
        self.assertFalse(PublicVault.get().enabled)

    def test_un_invitado_no_toca_la_configuracion(self):
        self.client.force_login(self.make_user("lector", role=User.ROLE_VIEWER))
        self.assertEqual(self.client.get("/api/knowledge/config").status_code, 403)
        self.assertEqual(self.json_post("/api/knowledge/config/save",
                                        {"enabled": True}).status_code, 403)
        self.assertEqual(self.client.get("/api/knowledge/links").status_code, 403)
        self.assertFalse(PublicVault.get().enabled)

    def test_el_propietario_enciende_y_apaga(self):
        self.client.force_login(self.owner)
        resp = self.json_post("/api/knowledge/config/save", {"enabled": True})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(PublicVault.get().enabled)
        self.json_post("/api/knowledge/config/save", {"enabled": False})
        self.assertFalse(PublicVault.get().enabled)

    def test_la_duracion_del_permiso_tiene_limites(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.json_post("/api/knowledge/config/save",
                                        {"grant_days": 0}).status_code, 400)
        self.assertEqual(self.json_post("/api/knowledge/config/save",
                                        {"grant_days": 400}).status_code, 400)
        self.assertEqual(self.json_post("/api/knowledge/config/save",
                                        {"grant_days": 7}).status_code, 200)
        self.assertEqual(PublicVault.get().grant_days, 7)

    def test_crear_y_revocar_enlaces_maestros(self):
        self.client.force_login(self.owner)
        created = self.json_post("/api/knowledge/links/create", {"name": "Ponentes"})
        self.assertEqual(created.status_code, 201)
        link_id = created.json()["link"]["id"]
        self.assertIn("/conocimiento/m/", created.json()["link"]["url"])
        self.assertEqual(len(self.client.get("/api/knowledge/links").json()["links"]), 1)

        self.assertEqual(self.json_post("/api/knowledge/links/revoke",
                                        {"id": link_id}).status_code, 200)
        self.assertEqual(self.client.get("/api/knowledge/links").json()["links"], [])
        # Se marca, no se borra: la fila es lo que invalida la cookie ya repartida.
        self.assertTrue(MasterLink.objects.get(pk=link_id).revoked)

    def test_solo_puede_haber_una_configuracion(self):
        """`save()` clava la pk, así que una segunda fila no llega a existir:
        revienta en el INSERT en vez de dejar dos políticas de acceso vivas y
        que gane la que pille primero el `filter()` de turno."""
        PublicVault.get()
        with self.assertRaises(IntegrityError), transaction.atomic():
            PublicVault.objects.create(enabled=True)
        self.assertEqual(PublicVault.objects.count(), 1)
