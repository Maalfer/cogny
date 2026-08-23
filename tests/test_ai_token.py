"""Token de IA: lectura y escritura de UNA nota por HTTP, sin sesión.

Lo que se comprueba aquí, por orden de importancia:

1. Que gestionar tokens (crear/listar/revocar) es cosa de quien puede
   escribir en la bóveda, con sesión — igual que "Compartir nota".
2. Que el token en sí (GET/POST a `/n/<token>/`) lee y reescribe la nota
   correcta sin sesión, y sólo esa nota — nada de listar ni tocar otra.
3. Que caduca solo y que revocarlo lo mata al instante.
4. Que renombrar/mover/borrar la nota no deja el token roto ni, peor,
   apuntando por accidente a una nota distinta que herede la misma ruta.
"""
from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone

from apps.accounts.models import User
from apps.notes.models import NoteToken

from .base import VaultTestCase

API = "/api/notes/ai-token"


class AdminEndpointTests(VaultTestCase):
    def setUp(self):
        super().setUp()
        self.owner = self.make_user()
        self.write_note("nota.md", "hola")

    def test_el_anonimo_no_gestiona_tokens(self):
        self.assertEqual(self.client.get(API + "/list?path=nota.md").status_code, 302)
        self.assertEqual(self.json_post(API + "/create", {"path": "nota.md"}).status_code, 302)

    def test_un_invitado_de_solo_lectura_no_gestiona_tokens(self):
        self.client.force_login(self.make_user("lector", role=User.ROLE_VIEWER))
        self.assertEqual(self.client.get(API + "/list?path=nota.md").status_code, 403)
        self.assertEqual(self.json_post(API + "/create", {"path": "nota.md"}).status_code, 403)

    def test_crear_lista_y_revocar(self):
        self.client.force_login(self.owner)
        created = self.json_post(API + "/create", {"path": "nota.md"})
        self.assertEqual(created.status_code, 201)
        body = created.json()
        self.assertIn("/n/", body["url"])
        token = body["token"]

        listed = self.client.get(API + "/list?path=nota.md").json()["tokens"]
        self.assertEqual([t["token"] for t in listed], [token])

        self.assertEqual(self.json_post(API + "/revoke", {"token": token}).status_code, 200)
        self.assertEqual(self.client.get(API + "/list?path=nota.md").json()["tokens"], [])
        self.assertTrue(NoteToken.objects.get(token=token).revoked)

    def test_se_pueden_generar_varios_tokens_a_la_vez_para_la_misma_nota(self):
        self.client.force_login(self.owner)
        self.json_post(API + "/create", {"path": "nota.md"})
        self.json_post(API + "/create", {"path": "nota.md"})
        self.assertEqual(len(self.client.get(API + "/list?path=nota.md").json()["tokens"]), 2)

    def test_no_se_puede_generar_token_de_una_nota_inexistente(self):
        self.client.force_login(self.owner)
        r = self.json_post(API + "/create", {"path": "no-existe.md"})
        self.assertEqual(r.status_code, 404)


class TokenRedemptionTests(VaultTestCase):
    def setUp(self):
        super().setUp()
        self.owner = self.make_user()
        self.write_note("nota.md", "contenido original")
        self.client.force_login(self.owner)
        self.token = self.json_post(API + "/create", {"path": "nota.md"}).json()["token"]
        self.client.logout()  # el token debe funcionar SIN sesión

    def test_lee_la_nota_sin_sesion(self):
        r = self.client.get(f"/n/{self.token}/")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["path"], "nota.md")
        self.assertEqual(body["content"], "contenido original")

    def test_reescribe_la_nota_sin_sesion_ni_csrf(self):
        r = self.client.post(f"/n/{self.token}/", data='{"content": "reescrito por la IA"}',
                             content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual((self.vault_dir / "nota.md").read_text(), "reescrito por la IA")

    def test_no_se_puede_leer_ni_tocar_otra_nota_con_este_token(self):
        """El token sólo sabe de SU ruta: no hay parámetro de ruta en la URL
        con el que pedir otra cosa."""
        self.write_note("secreta.md", "no debería salir por aquí")
        r = self.client.get(f"/n/{self.token}/")
        self.assertNotIn("secreta", r.json()["content"])
        # Y no existe ningún endpoint de árbol/listado alcanzable con el token:
        # sólo GET/POST a esta misma URL.
        self.assertEqual(self.client.get(f"/n/{self.token}/tree").status_code, 404)

    def test_un_token_inventado_no_vale(self):
        self.assertEqual(self.client.get("/n/token-que-no-existe/").status_code, 404)

    def test_metodos_no_permitidos(self):
        self.assertEqual(self.client.delete(f"/n/{self.token}/").status_code, 405)

    def test_caduca_solo(self):
        NoteToken.objects.filter(token=self.token).update(
            expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.client.get(f"/n/{self.token}/").status_code, 404)

    def test_revocarlo_lo_mata_al_instante(self):
        self.client.force_login(self.owner)
        self.json_post(API + "/revoke", {"token": self.token})
        self.client.logout()
        self.assertEqual(self.client.get(f"/n/{self.token}/").status_code, 404)

    def test_nota_demasiado_grande_se_rechaza(self):
        with patch("apps.notes.vault.MAX_NOTE_BYTES", 10):
            r = self.client.post(f"/n/{self.token}/",
                                 data='{"content": "esto es mucho más de 10 bytes"}',
                                 content_type="application/json")
        self.assertEqual(r.status_code, 400)


class TokenFollowsTheNoteTests(VaultTestCase):
    """Renombrar/mover/borrar la nota no debe dejar el token roto ni,
    peor, sirviendo el contenido de una nota distinta que ocupe luego la
    misma ruta."""

    def setUp(self):
        super().setUp()
        self.owner = self.make_user()
        self.write_note("Carpeta/nota.md", "original")
        self.client.force_login(self.owner)
        self.token = self.json_post(API + "/create", {"path": "Carpeta/nota.md"}).json()["token"]

    def test_el_token_sigue_a_la_nota_al_renombrarla(self):
        self.json_post("/api/notes/rename", {"path": "Carpeta/nota.md", "name": "otra.md"})
        self.client.logout()
        r = self.client.get(f"/n/{self.token}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["path"], "Carpeta/otra.md")

    def test_el_token_sigue_a_la_nota_al_mover_su_carpeta(self):
        self.json_post("/api/notes/create", {"name": "Destino", "parent": "", "type": "folder"})
        self.json_post("/api/notes/move", {"path": "Carpeta", "target": "Destino"})
        self.client.logout()
        r = self.client.get(f"/n/{self.token}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["path"], "Destino/Carpeta/nota.md")

    def test_el_token_muere_si_se_borra_la_nota(self):
        self.json_post("/api/notes/delete", {"path": "Carpeta/nota.md"})
        self.client.logout()
        self.assertEqual(self.client.get(f"/n/{self.token}/").status_code, 404)

    def test_una_nota_nueva_en_la_misma_ruta_no_hereda_el_token_viejo(self):
        """Sin drop_shares() al borrar, un token "muerto" seguiría vivo en la
        BD apuntando a `path`; si luego se crea una nota nueva en esa misma
        ruta, el token viejo empezaría a servir contenido que nunca autorizó
        nadie a exponer con ese token."""
        self.json_post("/api/notes/delete", {"path": "Carpeta/nota.md"})
        self.write_note("Carpeta/nota.md", "contenido totalmente distinto, nota nueva")
        self.client.logout()
        self.assertEqual(self.client.get(f"/n/{self.token}/").status_code, 404)
