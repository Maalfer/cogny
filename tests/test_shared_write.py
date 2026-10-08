"""Enlace compartido con escritura: `/s/<token>/save`.

El enlace de sólo lectura y el editable comparten token y puerta de
contraseña; lo único que los separa es `SharedNote.can_write`. Lo que se
comprueba, por orden de importancia:

1. Sin `can_write` el endpoint de guardado NO existe (404) y la nota no cambia:
   que la marca por defecto sea "sólo lectura" no sirve de nada si el POST
   funciona igual.
2. Con `can_write` se escribe de verdad, y lo escrito es lo que ve la
   siguiente visita.
3. La contraseña protege también la escritura: sin pasar la puerta no se
   guarda, aunque se conozca el token.
4. Quitar el permiso más tarde cierra la puerta a quien ya tenía el enlace.
5. El enlace sigue siendo de UNA nota: no hay forma de tocar otra, ni de
   renombrar, borrar o leer la bóveda con él.
6. En modo escritura el mismo enlace también expone el API JSON de la nota y
   de sus adjuntos (`/s/<token>/note`, `/s/<token>/assets...`), pensado para
   dárselo a una IA que gestione la nota por HTTP sin sesión.
"""
import io
import json

from apps.notes.models import SharedNote

from .base import VaultTestCase


class SharedWriteTests(VaultTestCase):
    def setUp(self):
        super().setUp()
        self.owner = self.make_user()
        self.client.force_login(self.owner)
        self.write_note("Carpeta/nota.md", "contenido original")
        self.write_note("Carpeta/otra.md", "la otra nota")

    def _share(self, can_write=False, password=""):
        return self.json_post("/api/notes/share/create", {
            "path": "Carpeta/nota.md", "can_write": can_write, "password": password,
        }).json()

    def _save(self, token, content, client=None):
        return (client or self.client_class()).post(
            f"/s/{token}/save", data=json.dumps({"content": content}),
            content_type="application/json")

    def _disk(self, rel="Carpeta/nota.md"):
        return (self.vault_dir / rel).read_text(encoding="utf-8")

    # ── 1. Sólo lectura ──

    def test_sin_permiso_de_escritura_el_guardado_no_existe(self):
        token = self._share()["token"]
        self.assertEqual(self._save(token, "intento de sobrescritura").status_code, 404)
        self.assertEqual(self._disk(), "contenido original")

    def test_por_defecto_el_enlace_es_de_solo_lectura(self):
        # Sin `can_write` en el cuerpo, ni siquiera como False: el enlace de
        # toda la vida no puede volverse editable por omisión.
        res = self.json_post("/api/notes/share/create", {"path": "Carpeta/nota.md"}).json()
        self.assertFalse(res["can_write"])
        self.assertFalse(SharedNote.objects.get(token=res["token"]).can_write)

    # ── 2. Escritura ──

    def test_con_permiso_se_escribe_y_se_ve_lo_escrito(self):
        token = self._share(can_write=True)["token"]
        anon = self.client_class()
        resp = self._save(token, "texto de quien tiene el enlace", client=anon)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["success"])
        self.assertEqual(self._disk(), "texto de quien tiene el enlace")
        self.assertContains(anon.get(f"/s/{token}/"), "texto de quien tiene el enlace")

    def test_la_pagina_editable_carga_el_editor_y_la_de_lectura_no(self):
        editable = self._share(can_write=True)["token"]
        page = self.client_class().get(f"/s/{editable}/")
        self.assertContains(page, "balucm.js")
        self.assertContains(page, "puedes editarla")

        SharedNote.objects.filter(token=editable).update(can_write=False)
        page = self.client_class().get(f"/s/{editable}/")
        self.assertNotContains(page, "balucm.js")
        self.assertContains(page, "sólo lectura")

    def test_un_cuerpo_que_no_es_texto_no_se_escribe(self):
        token = self._share(can_write=True)["token"]
        resp = self.client_class().post(f"/s/{token}/save", data=json.dumps({"content": 42}),
                                        content_type="application/json")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self._disk(), "contenido original")

    def test_una_nota_enorme_se_rechaza(self):
        from apps.notes import vault
        token = self._share(can_write=True)["token"]
        resp = self._save(token, "x" * (vault.MAX_NOTE_BYTES + 1))
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self._disk(), "contenido original")

    def test_get_no_vale_para_escribir(self):
        token = self._share(can_write=True)["token"]
        self.assertEqual(self.client_class().get(f"/s/{token}/save").status_code, 405)

    # ── 3. Contraseña ──

    def test_con_contrasena_no_se_escribe_sin_pasar_la_puerta(self):
        token = self._share(can_write=True, password="secreta")["token"]
        anon = self.client_class()
        self.assertEqual(self._save(token, "colado", client=anon).status_code, 404)
        self.assertEqual(self._disk(), "contenido original")

        # Con la contraseña puesta, la misma sesión ya sí escribe.
        anon.post(f"/s/{token}/", {"password": "secreta"})
        self.assertEqual(self._save(token, "ya dentro", client=anon).status_code, 200)
        self.assertEqual(self._disk(), "ya dentro")

    # ── 4. Revocar ──

    def test_quitar_el_permiso_cierra_la_puerta_a_quien_ya_tenia_el_enlace(self):
        token = self._share(can_write=True)["token"]
        anon = self.client_class()
        self.assertEqual(self._save(token, "primero", client=anon).status_code, 200)
        self._share(can_write=False)          # el dueño lo pasa a sólo lectura
        self.assertEqual(self._save(token, "segundo", client=anon).status_code, 404)
        self.assertEqual(self._disk(), "primero")

    def test_dejar_de_compartir_tambien_corta_la_escritura(self):
        token = self._share(can_write=True)["token"]
        self.json_post("/api/notes/share/revoke", {"path": "Carpeta/nota.md"})
        self.assertEqual(self._save(token, "fantasma").status_code, 404)
        self.assertEqual(self._disk(), "contenido original")

    def test_borrar_la_nota_no_deja_el_enlace_escribiendo_en_su_ruta(self):
        token = self._share(can_write=True)["token"]
        self.json_post("/api/notes/delete", {"path": "Carpeta/nota.md"})
        self.assertEqual(self._save(token, "resucitada").status_code, 404)
        self.assertFalse((self.vault_dir / "Carpeta/nota.md").exists())

    # ── 5. Sigue siendo UNA nota ──

    def test_el_enlace_no_alcanza_a_otra_nota(self):
        token = self._share(can_write=True)["token"]
        # No hay parámetro de ruta que valga: el token ya dice qué nota es.
        resp = self.client_class().post(
            f"/s/{token}/save",
            data=json.dumps({"content": "pisada", "path": "Carpeta/otra.md"}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._disk("Carpeta/otra.md"), "la otra nota")
        self.assertEqual(self._disk(), "pisada")

    def test_el_enlace_no_da_acceso_a_la_boveda(self):
        self._share(can_write=True)
        anon = self.client_class()
        for url in ("/api/notes/tree", "/api/notes/save", "/api/notes/delete"):
            self.assertIn(anon.get(url).status_code, (302, 403, 405), url)

    # ── Estado que consume el modal ──

    def test_status_y_list_dicen_si_el_enlace_es_editable(self):
        self._share(can_write=True)
        status = self.client.get("/api/notes/share/status?path=Carpeta/nota.md").json()
        self.assertTrue(status["can_write"])
        listed = self.client.get("/api/notes/share/list").json()["shares"]
        self.assertEqual([s["can_write"] for s in listed], [True])


# ── API de la nota editable (para una IA, sin sesión) ──
# Un enlace creado con `can_write` expone además el API JSON de la nota y de
# sus adjuntos: leer/reescribir contenido (`/s/<token>/note`), listar y subir
# (`/s/<token>/assets`) y descargar o borrar un adjunto concreto
# (`/s/<token>/assets/<name>`). El token en la URL ES la credencial, igual
# que en el resto de la superficie pública.


class SharedEditableApiTests(VaultTestCase):
    def setUp(self):
        super().setUp()
        self.owner = self.make_user()
        self.client.force_login(self.owner)
        self.write_note("Carpeta/nota.md", "contenido original")

    def _share(self, can_write=False, password=""):
        return self.json_post("/api/notes/share/create", {
            "path": "Carpeta/nota.md", "can_write": can_write, "password": password,
        }).json()

    def _fake_image(self, name="foto.png"):
        f = io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"0" * 64)
        f.name = name
        return f

    # ── Lectura/escritura del contenido ──

    def test_lee_la_nota_sin_sesion_como_json(self):
        token = self._share(can_write=True)["token"]
        anon = self.client_class()
        r = anon.get(f"/s/{token}/note")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["path"], "Carpeta/nota.md")
        self.assertEqual(body["content"], "contenido original")

    def test_reescribe_la_nota_sin_sesion_ni_csrf(self):
        token = self._share(can_write=True)["token"]
        anon = self.client_class()
        r = anon.post(f"/s/{token}/note", data='{"content": "reescrito por la IA"}',
                      content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual((self.vault_dir / "Carpeta/nota.md").read_text(),
                         "reescrito por la IA")

    def test_un_enlace_de_solo_lectura_no_expone_el_api(self):
        token = self._share(can_write=False)["token"]
        anon = self.client_class()
        self.assertEqual(anon.get(f"/s/{token}/note").status_code, 404)
        self.assertEqual(anon.post(f"/s/{token}/note",
                                   data='{"content": "colado"}',
                                   content_type="application/json").status_code, 404)
        self.assertEqual((self.vault_dir / "Carpeta/nota.md").read_text(),
                         "contenido original")

    def test_con_contrasena_no_se_lee_sin_pasar_la_puerta(self):
        token = self._share(can_write=True, password="secreta")["token"]
        anon = self.client_class()
        self.assertEqual(anon.get(f"/s/{token}/note").status_code, 404)
        anon.post(f"/s/{token}/", {"password": "secreta"})
        self.assertEqual(anon.get(f"/s/{token}/note").status_code, 200)

    def test_no_alcanza_a_otra_nota_ni_a_la_boveda(self):
        token = self._share(can_write=True)["token"]
        self.write_note("Carpeta/secreta.md", "no debería salir por aquí")
        anon = self.client_class()
        self.assertNotIn("secreta", anon.get(f"/s/{token}/note").json()["content"])
        self.assertEqual(anon.get(f"/s/{token}/tree").status_code, 404)

    def test_un_cuerpo_que_no_es_texto_no_se_escribe(self):
        token = self._share(can_write=True)["token"]
        r = self.client_class().post(f"/s/{token}/note", data='{"content": 42}',
                                     content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_metodos_no_permitidos(self):
        token = self._share(can_write=True)["token"]
        anon = self.client_class()
        self.assertEqual(anon.delete(f"/s/{token}/note").status_code, 405)
        self.assertEqual(anon.delete(f"/s/{token}/assets").status_code, 405)
        self.assertEqual(anon.post(f"/s/{token}/assets/x.png").status_code, 405)

    # ── Adjuntos ──

    def test_sube_un_adjunto_y_queda_en_adjuntos(self):
        token = self._share(can_write=True)["token"]
        r = self.client_class().post(f"/s/{token}/assets", {"file": self._fake_image()})
        self.assertEqual(r.status_code, 201)
        name = r.json()["name"]
        self.assertTrue((self.vault_dir / "Adjuntos" / name).is_file())

    def test_lista_lo_que_la_nota_referencia_en_el_texto(self):
        token = self._share(can_write=True)["token"]
        anon = self.client_class()
        name = anon.post(f"/s/{token}/assets", {"file": self._fake_image()}).json()["name"]
        anon.post(f"/s/{token}/note", data=f'{{"content": "hola ![[{name}]]"}}',
                  content_type="application/json")
        assets = anon.get(f"/s/{token}/assets").json()["assets"]
        self.assertEqual([a["name"] for a in assets], [name])
        self.assertEqual(assets[0]["ref"], name)

    def test_lista_tambien_lo_subido_aunque_la_nota_no_lo_mencione(self):
        token = self._share(can_write=True)["token"]
        anon = self.client_class()
        name = anon.post(f"/s/{token}/assets", {"file": self._fake_image()}).json()["name"]
        assets = anon.get(f"/s/{token}/assets").json()["assets"]
        self.assertEqual([a["name"] for a in assets], [name])
        self.assertIsNone(assets[0]["ref"])

    def test_descarga_y_borra_un_adjunto_propio(self):
        token = self._share(can_write=True)["token"]
        anon = self.client_class()
        name = anon.post(f"/s/{token}/assets", {"file": self._fake_image()}).json()["name"]
        self.assertEqual(anon.get(f"/s/{token}/assets/{name}").status_code, 200)
        self.assertEqual(anon.delete(f"/s/{token}/assets/{name}").status_code, 200)
        self.assertFalse((self.vault_dir / "Adjuntos" / name).exists())
        self.assertEqual(anon.get(f"/s/{token}/assets/{name}").status_code, 404)

    def test_no_alcanza_un_adjunto_de_otra_nota_aunque_coincida_el_nombre(self):
        self.write_note("Carpeta/otra.md", "otra nota")
        up = self.client.post("/api/notes/upload",
                              {"file": self._fake_image("compartido.png"),
                               "note": "Carpeta/otra.md"})
        name = up.json()["name"]
        token = self._share(can_write=True)["token"]
        anon = self.client_class()
        self.assertEqual(anon.get(f"/s/{token}/assets/{name}").status_code, 404)
        self.assertEqual(anon.delete(f"/s/{token}/assets/{name}").status_code, 404)
        self.assertTrue((self.vault_dir / "Adjuntos" / name).exists())

    def test_no_expone_adjuntos_de_un_enlace_de_solo_lectura(self):
        token = self._share(can_write=False)["token"]
        anon = self.client_class()
        self.assertEqual(anon.get(f"/s/{token}/assets").status_code, 404)
        self.assertEqual(anon.post(f"/s/{token}/assets",
                                   {"file": self._fake_image()}).status_code, 404)

    def test_un_adjunto_sin_dueno_registrado_tampoco_se_alcanza(self):
        (self.vault_dir / "Adjuntos").mkdir(exist_ok=True)
        (self.vault_dir / "Adjuntos" / "huerfano.png").write_bytes(b"x")
        token = self._share(can_write=True)["token"]
        self.assertEqual(
            self.client_class().get(f"/s/{token}/assets/huerfano.png").status_code, 404)
