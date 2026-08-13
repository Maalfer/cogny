"""Pizarra `/pizarra`.

Se comprueba, por orden de importancia:
1. Que sólo lectura (`viewer`) puede ver la galería y abrir una pizarra, pero
   no crear/renombrar/borrar/guardar.
2. El ciclo normal: crear, guardar una escena, listar con la miniatura, borrar.
3. Que un id que no existe da 404 y no un 500.
"""
import base64
import shutil
import tempfile
from pathlib import Path

from django.test import override_settings

from apps.accounts.models import User
from apps.whiteboard.models import Board

from .base import VaultTestCase

# PNG 1x1 válido — mínimo necesario para que `storage.write_thumb` lo acepte.
_PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42Y"
    "AAAAASUVORK5CYII="
)
_THUMB_DATA_URL = "data:image/png;base64," + base64.b64encode(_PNG_1X1).decode()


class WhiteboardTestCase(VaultTestCase):
    def setUp(self):
        super().setUp()
        self.wb_dir = Path(tempfile.mkdtemp(prefix="cogny-wb-test-"))
        self.addCleanup(shutil.rmtree, self.wb_dir, True)
        patcher = override_settings(WHITEBOARD_ROOT=self.wb_dir)
        patcher.enable()
        self.addCleanup(patcher.disable)


class ViewerCannotWriteTests(WhiteboardTestCase):
    def setUp(self):
        super().setUp()
        self.user = self.make_user(role=User.ROLE_VIEWER)
        self.client.force_login(self.user)
        self.board = Board.objects.create(name="Boceto")

    def test_puede_ver_la_galeria_y_la_pizarra(self):
        self.assertEqual(self.client.get("/pizarra/").status_code, 200)
        self.assertEqual(self.client.get(f"/pizarra/{self.board.id}/").status_code, 200)
        self.assertEqual(self.client.get("/api/pizarra/list").status_code, 200)

    def test_no_puede_crear_ni_guardar_ni_borrar(self):
        self.assertEqual(self.json_post("/api/pizarra/create", {}).status_code, 403)
        self.assertEqual(self.json_post("/api/pizarra/scene/save", {
            "id": str(self.board.id), "elements": [], "appState": {}, "files": {},
        }).status_code, 403)
        self.assertEqual(self.json_post("/api/pizarra/delete",
                                        {"id": str(self.board.id)}).status_code, 403)
        self.assertEqual(Board.objects.count(), 1)


class EditorFlowTests(WhiteboardTestCase):
    def setUp(self):
        super().setUp()
        self.user = self.make_user(role=User.ROLE_OWNER)
        self.client.force_login(self.user)

    def test_crear_guardar_listar_y_borrar(self):
        res = self.json_post("/api/pizarra/create", {"name": "Mi pizarra"}).json()
        self.assertTrue(res["success"])
        board_id = res["id"]

        save = self.json_post("/api/pizarra/scene/save", {
            "id": board_id,
            "elements": [{"id": "el1", "type": "rectangle"}],
            "appState": {"viewBackgroundColor": "#fff"},
            "files": {},
        }).json()
        self.assertTrue(save["success"])

        thumb = self.json_post("/api/pizarra/thumb/save", {
            "id": board_id, "dataUrl": _THUMB_DATA_URL,
        }).json()
        self.assertTrue(thumb["success"])

        listing = self.client.get("/api/pizarra/list").json()["boards"]
        self.assertEqual(len(listing), 1)
        self.assertEqual(listing[0]["name"], "Mi pizarra")
        self.assertIsNotNone(listing[0]["thumb_url"])

        self.assertEqual(self.client.get(listing[0]["thumb_url"]).status_code, 200)

        editor = self.client.get(f"/pizarra/{board_id}/")
        self.assertEqual(editor.status_code, 200)
        self.assertIn(b"rectangle", editor.content)

        delete = self.json_post("/api/pizarra/delete", {"id": board_id}).json()
        self.assertTrue(delete["success"])
        self.assertEqual(Board.objects.count(), 0)
        self.assertFalse((self.wb_dir / f"{board_id}.json").exists())
        self.assertFalse((self.wb_dir / f"{board_id}.png").exists())

    def test_renombrar_y_duplicar(self):
        board_id = self.json_post("/api/pizarra/create", {}).json()["id"]
        renamed = self.json_post("/api/pizarra/rename",
                                 {"id": board_id, "name": "Ideas"}).json()
        self.assertEqual(renamed["name"], "Ideas")

        dup = self.json_post("/api/pizarra/duplicate", {"id": board_id}).json()
        self.assertTrue(dup["success"])
        self.assertEqual(Board.objects.count(), 2)

    def test_un_id_inexistente_da_404_no_500(self):
        fake = "00000000-0000-0000-0000-000000000000"
        self.assertEqual(self.client.get(f"/pizarra/{fake}/").status_code, 404)
        self.assertEqual(self.json_post("/api/pizarra/rename",
                                        {"id": fake, "name": "x"}).status_code, 404)

    def test_un_id_con_formato_invalido_da_404_no_500(self):
        self.assertEqual(self.json_post("/api/pizarra/rename",
                                        {"id": "no-es-un-uuid"}).status_code, 404)

    def test_la_escena_no_admite_datos_con_forma_invalida(self):
        board_id = self.json_post("/api/pizarra/create", {}).json()["id"]
        resp = self.json_post("/api/pizarra/scene/save", {
            "id": board_id, "elements": "no-es-una-lista", "appState": {}, "files": {},
        })
        self.assertEqual(resp.status_code, 400)

    def test_una_miniatura_que_no_es_png_se_rechaza(self):
        board_id = self.json_post("/api/pizarra/create", {}).json()["id"]
        resp = self.json_post("/api/pizarra/thumb/save", {
            "id": board_id, "dataUrl": "data:image/png;base64,no-es-base64-valido",
        })
        self.assertEqual(resp.status_code, 400)
