"""API pública v1: autenticación por clave, permisos y contrato de los endpoints."""
import base64
import json

from apps.accounts.models import ApiKey, User

from .base import VaultTestCase


class ApiTestCase(VaultTestCase):
    """Cliente con clave de API en la cabecera."""

    def setUp(self):
        super().setUp()
        self.user = self.make_user()
        self.key, self.raw = ApiKey.objects.create_key(self.user, "tests")

    def api(self, method, url, payload=None, raw=None, **extra):
        kwargs = {"HTTP_AUTHORIZATION": f"Bearer {raw or self.raw}", **extra}
        if payload is not None:
            kwargs["data"] = json.dumps(payload)
            kwargs["content_type"] = "application/json"
        return getattr(self.client, method)(url, **kwargs)


class AuthTests(ApiTestCase):
    def test_sin_clave_es_401(self):
        resp = self.client.get("/api/v1/me")
        self.assertEqual(resp.status_code, 401)
        self.assertIn("error", resp.json())

    def test_clave_inventada_es_401(self):
        self.assertEqual(self.api("get", "/api/v1/me", raw="cgny_ffff_falsa").status_code, 401)

    def test_clave_revocada_deja_de_valer(self):
        self.key.revoked = True
        self.key.save(update_fields=["revoked"])
        self.assertEqual(self.api("get", "/api/v1/me").status_code, 401)

    def test_la_cookie_de_sesion_no_abre_la_api(self):
        """La API va exenta de CSRF: si admitiera la sesión, cualquier web podría
        usarla desde el navegador del usuario."""
        self.client.force_login(self.user)
        self.assertEqual(self.client.get("/api/v1/me").status_code, 401)

    def test_las_tres_formas_de_mandar_la_clave(self):
        self.assertEqual(self.client.get(
            "/api/v1/me", HTTP_AUTHORIZATION=f"Bearer {self.raw}").status_code, 200)
        self.assertEqual(self.client.get(
            "/api/v1/me", HTTP_X_API_KEY=self.raw).status_code, 200)
        self.assertEqual(self.client.get(f"/api/v1/me?api_key={self.raw}").status_code, 200)

    def test_me_describe_la_cuenta(self):
        data = self.api("get", "/api/v1/me").json()
        self.assertEqual(data["username"], self.user.username)
        self.assertTrue(data["can_write"])
        self.assertNotIn(self.raw, json.dumps(data))

    def test_metodo_no_permitido(self):
        self.assertEqual(self.api("post", "/api/v1/me", {}).status_code, 405)

    def test_ruta_inexistente_responde_json(self):
        resp = self.api("get", "/api/v1/lo-que-sea")
        self.assertEqual(resp.status_code, 404)
        self.assertIn("docs", resp.json())

    def test_cuerpo_json_roto(self):
        resp = self.client.post("/api/v1/notes", data="{roto",
                                content_type="application/json",
                                HTTP_AUTHORIZATION=f"Bearer {self.raw}")
        self.assertEqual(resp.status_code, 400)


class PermissionTests(ApiTestCase):
    def test_clave_de_solo_lectura(self):
        _, raw = ApiKey.objects.create_key(self.user, "lectura", read_only=True)
        self.assertEqual(self.api("get", "/api/v1/tree", raw=raw).status_code, 200)
        resp = self.api("post", "/api/v1/notes", {"path": "x.md"}, raw=raw)
        self.assertEqual(resp.status_code, 403)
        self.assertFalse((self.vault_dir / "x.md").exists())

    def test_una_clave_no_da_mas_permiso_que_su_cuenta(self):
        viewer = self.make_user(username="lector", role=User.ROLE_VIEWER)
        _, raw = ApiKey.objects.create_key(viewer, "de-un-viewer")
        self.assertEqual(self.api("get", "/api/v1/tree", raw=raw).status_code, 200)
        self.assertEqual(self.api("post", "/api/v1/notes", {"path": "x.md"}, raw=raw).status_code, 403)

    def test_los_endpoints_de_propietario_son_solo_del_propietario(self):
        editor = self.make_user(username="editor", role=User.ROLE_EDITOR)
        _, raw = ApiKey.objects.create_key(editor, "de-un-editor")
        self.assertEqual(self.api("get", "/api/v1/users", raw=raw).status_code, 403)
        self.assertEqual(self.api("get", "/api/v1/keys", raw=raw).status_code, 403)


class NotesTests(ApiTestCase):
    def test_ciclo_completo_de_una_nota(self):
        created = self.api("post", "/api/v1/notes",
                           {"path": "Ideas/nueva.md", "content": "hola"})
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["note"]["path"], "Ideas/nueva.md")

        read = self.api("get", "/api/v1/notes/content?path=Ideas/nueva.md")
        self.assertEqual(read.json()["content"], "hola")

        self.assertEqual(self.api("put", "/api/v1/notes/content",
                                  {"path": "Ideas/nueva.md", "content": "otra cosa"}).status_code, 200)
        self.assertEqual(self.api("delete", "/api/v1/notes",
                                  {"path": "Ideas/nueva.md"}).status_code, 200)
        self.assertFalse((self.vault_dir / "Ideas/nueva.md").exists())

    def test_crear_dos_veces_en_la_misma_ruta_es_409(self):
        self.api("post", "/api/v1/notes", {"path": "a.md"})
        self.assertEqual(self.api("post", "/api/v1/notes", {"path": "a.md"}).status_code, 409)

    def test_patch_append_y_find_replace(self):
        self.api("post", "/api/v1/notes", {"path": "n.md", "content": "línea uno"})
        self.api("patch", "/api/v1/notes/content", {"path": "n.md", "append": "línea dos"})
        self.assertEqual((self.vault_dir / "n.md").read_text(encoding="utf-8"),
                         "línea uno\nlínea dos")
        resp = self.api("patch", "/api/v1/notes/content",
                        {"path": "n.md", "find": "uno", "replace": "1"})
        self.assertEqual(resp.json()["note"]["replacements"], 1)
        self.assertIn("línea 1", (self.vault_dir / "n.md").read_text(encoding="utf-8"))

    def test_patch_que_no_encuentra_el_texto_es_404(self):
        self.api("post", "/api/v1/notes", {"path": "n.md", "content": "hola"})
        self.assertEqual(self.api("patch", "/api/v1/notes/content",
                                  {"path": "n.md", "find": "adiós", "replace": "x"}).status_code, 404)

    def test_no_se_puede_salir_de_la_boveda(self):
        for payload in ({"path": "../fuera.md", "content": "x"},
                        {"parent": "..", "name": "fuera"}):
            self.assertEqual(self.api("post", "/api/v1/notes", payload).status_code, 400)
        self.assertFalse((self.tmp_root / "fuera.md").exists())

    def test_listado_y_busqueda(self):
        self.write_note("Carpeta/uno.md", "aguja")
        self.write_note("dos.md", "pajar")
        listado = self.api("get", "/api/v1/notes").json()
        self.assertEqual(listado["count"], 2)
        encontrados = self.api("get", "/api/v1/search?q=aguja").json()
        self.assertEqual([r["name"] for r in encontrados["results"]], ["uno"])

    def test_duplicar_renombrar_y_mover(self):
        self.write_note("original.md", "contenido")
        self.api("post", "/api/v1/folders", {"path": "Destino"})
        copia = self.api("post", "/api/v1/notes/duplicate", {"path": "original.md"})
        self.assertEqual(copia.json()["note"]["path"], "original 2.md")
        self.assertEqual(self.api("post", "/api/v1/notes/rename",
                                  {"path": "original 2.md", "name": "copia"}).json()["path"],
                         "copia.md")
        self.assertEqual(self.api("post", "/api/v1/notes/move",
                                  {"path": "copia.md", "target": "Destino"}).json()["path"],
                         "Destino/copia.md")


class FilesTests(ApiTestCase):
    def test_subir_por_base64_y_descargar(self):
        resp = self.api("post", "/api/v1/files", {
            "name": "datos.txt",
            "content_base64": base64.b64encode(b"contenido").decode(),
        })
        self.assertEqual(resp.status_code, 201)
        path = resp.json()["file"]["path"]
        self.assertEqual(resp.json()["embed"], "![[datos.txt]]")
        descarga = self.api("get", f"/api/v1/files/content?path={path}")
        self.assertEqual(b"".join(descarga.streaming_content), b"contenido")

    def test_base64_invalido(self):
        resp = self.api("post", "/api/v1/files", {"name": "x.txt", "content_base64": "no-b64!!"})
        self.assertEqual(resp.status_code, 400)

    def test_borrar_una_nota_por_files_no_cuela(self):
        self.write_note("nota.md")
        resp = self.api("delete", "/api/v1/files", {"path": "nota.md"})
        self.assertEqual(resp.status_code, 400)
        self.assertTrue((self.vault_dir / "nota.md").exists())


class VaultTests(ApiTestCase):
    def test_stats(self):
        self.write_note("nota.md", "12345")
        data = self.api("get", "/api/v1/vault/stats").json()
        self.assertEqual(data["n_notes"], 1)
        self.assertEqual(data["total_bytes"], 5)

    def test_export(self):
        self.write_note("nota.md", "x")
        resp = self.api("get", "/api/v1/vault/export")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/zip")


class KeysTests(ApiTestCase):
    def test_crear_listar_y_revocar(self):
        creada = self.api("post", "/api/v1/keys", {"name": "otra"}).json()["key"]
        self.assertTrue(creada["key"].startswith("cgny_"))
        listado = self.api("get", "/api/v1/keys").json()["keys"]
        self.assertEqual(len(listado), 2)
        self.assertNotIn(creada["key"], json.dumps(listado))
        self.assertEqual(self.api("delete", f"/api/v1/keys/{creada['id']}").status_code, 200)
        self.assertTrue(ApiKey.objects.get(pk=creada["id"]).revoked)

    def test_el_hash_guardado_no_es_la_clave(self):
        self.assertNotIn(self.raw, ApiKey.objects.get(pk=self.key.pk).key_hash)


class DocsTests(ApiTestCase):
    def test_la_documentacion_es_publica(self):
        self.assertEqual(self.client.get("/api/docs/").status_code, 200)
        spec = self.client.get("/api/v1/openapi.json")
        self.assertEqual(spec.status_code, 200)
        self.assertIn("openapi", spec.json())

    def test_api_a_secas_lleva_a_la_documentacion(self):
        self.assertRedirects(self.client.get("/api/"), "/api/docs/")
