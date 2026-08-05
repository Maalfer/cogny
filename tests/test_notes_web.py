"""Endpoints del vault que consume la web (sesión + CSRF)."""
import io
import json
import zipfile

from apps.accounts.models import User
from apps.notes.models import SharedNote

from .base import VaultTestCase


class AuthRequiredTests(VaultTestCase):
    def test_sin_sesion_no_se_entra(self):
        for url in ("/api/notes/tree", "/api/notes/storage", "/api/notes/share/list"):
            resp = self.client.get(url)
            self.assertIn(resp.status_code, (302, 403), url)

    def test_la_raiz_anonima_es_el_login(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "form", status_code=200)


class NotesCrudTests(VaultTestCase):
    def setUp(self):
        super().setUp()
        self.user = self.make_user()
        self.client.force_login(self.user)

    def test_crear_leer_guardar_y_borrar(self):
        resp = self.json_post("/api/notes/create", {"parent": "", "name": "Mi nota"})
        self.assertEqual(resp.status_code, 200)
        path = resp.json()["path"]
        self.assertEqual(path, "Mi nota.md")

        self.assertEqual(self.json_post("/api/notes/save",
                                        {"path": path, "content": "hola"}).status_code, 200)
        self.assertEqual(self.client.get(f"/api/notes/file?path={path}").json()["content"], "hola")

        self.assertEqual(self.json_post("/api/notes/delete", {"path": path}).status_code, 200)
        self.assertFalse((self.vault_dir / path).exists())

    def test_crear_dos_veces_no_pisa_la_primera(self):
        first = self.json_post("/api/notes/create", {"parent": "", "name": "Nota"}).json()["path"]
        second = self.json_post("/api/notes/create", {"parent": "", "name": "Nota"}).json()["path"]
        self.assertEqual(first, "Nota.md")
        self.assertEqual(second, "Nota 2.md")

    def test_renombrar_y_mover(self):
        self.write_note("origen.md")
        self.json_post("/api/notes/create", {"parent": "", "name": "Destino", "type": "folder"})
        resp = self.json_post("/api/notes/rename", {"path": "origen.md", "name": "nueva"})
        self.assertEqual(resp.json()["path"], "nueva.md")
        resp = self.json_post("/api/notes/move", {"path": "nueva.md", "target": "Destino"})
        self.assertEqual(resp.json()["path"], "Destino/nueva.md")

    def test_no_se_puede_salir_de_la_boveda(self):
        resp = self.json_post("/api/notes/save", {"path": "../fuera.md", "content": "x"})
        self.assertEqual(resp.status_code, 400)
        self.assertFalse((self.tmp_root / "fuera.md").exists())

    def test_solo_se_guardan_ficheros_md(self):
        resp = self.json_post("/api/notes/save", {"path": "script.py", "content": "x"})
        self.assertEqual(resp.status_code, 400)

    def test_cuerpo_json_invalido_da_400_no_500(self):
        resp = self.client.post("/api/notes/save", data="{no soy json",
                                content_type="application/json")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error"], "JSON inválido")

    def test_nota_demasiado_grande(self):
        resp = self.json_post("/api/notes/save", {"path": "n.md", "content": "x" * 5_000_001})
        self.assertEqual(resp.status_code, 400)

    def test_el_arbol_y_el_reorden(self):
        self.write_note("a.md")
        self.write_note("b.md")
        self.assertEqual(self.json_post("/api/notes/reorder",
                                        {"folder": "", "order": ["b.md", "a.md"]}).status_code, 200)
        names = [n["name"] for n in self.client.get("/api/notes/tree").json()["tree"]]
        self.assertEqual(names, ["b", "a"])

    def test_busqueda(self):
        self.write_note("uno.md", "contiene aguja aquí")
        self.write_note("dos.md", "nada")
        results = self.client.get("/api/notes/search?q=aguja").json()["results"]
        self.assertEqual([r["name"] for r in results], ["uno"])

    def test_estadisticas(self):
        self.write_note("uno.md", "12345")
        data = self.client.get("/api/notes/storage").json()
        self.assertTrue(data["success"])
        self.assertEqual(data["n_notes"], 1)


class UploadTests(VaultTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.make_user())

    def test_un_adjunto_cualquiera_va_a_adjuntos(self):
        f = io.BytesIO(b"%PDF-1.4 falso")
        f.name = "documento.pdf"
        resp = self.client.post("/api/notes/upload", {"file": f})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["path"], "Adjuntos/documento.pdf")

    def test_el_nombre_del_fichero_no_puede_escapar(self):
        f = io.BytesIO(b"datos")
        f.name = "../../fuera.txt"
        resp = self.client.post("/api/notes/upload", {"file": f})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["path"].startswith("Adjuntos/"))
        self.assertFalse((self.tmp_root / "fuera.txt").exists())


class ExportImportTests(VaultTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.make_user())

    def test_export_devuelve_un_zip_con_las_notas(self):
        self.write_note("nota.md", "contenido")
        resp = self.client.get("/api/notes/export")
        self.assertEqual(resp.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(b"".join(resp.streaming_content))) as zf:
            self.assertEqual(zf.namelist(), ["nota.md"])

    def test_import_de_un_zip_valido(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("importada.md", "hola")
        buf.seek(0)
        buf.name = "vault.zip"
        resp = self.client.post("/api/notes/import", {"file": buf, "mode": "merge"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual((self.vault_dir / "importada.md").read_text(encoding="utf-8"), "hola")

    def test_import_de_algo_que_no_es_zip(self):
        buf = io.BytesIO(b"no soy un zip")
        buf.name = "x.zip"
        resp = self.client.post("/api/notes/import", {"file": buf})
        self.assertEqual(resp.status_code, 400)


class SharingTests(VaultTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.make_user())
        self.write_note("Carpeta/nota.md", "# Título\n\ncontenido compartido")

    def test_compartir_y_ver_sin_sesion(self):
        resp = self.json_post("/api/notes/share/create", {"path": "Carpeta/nota.md"})
        token = resp.json()["token"]
        anon = self.client_class()
        self.assertContains(anon.get(f"/s/{token}/"), "contenido compartido")

    def test_el_mismo_enlace_se_reutiliza(self):
        first = self.json_post("/api/notes/share/create", {"path": "Carpeta/nota.md"}).json()
        second = self.json_post("/api/notes/share/create", {"path": "Carpeta/nota.md"}).json()
        self.assertEqual(first["token"], second["token"])

    def test_con_contrasena_pide_la_contrasena(self):
        token = self.json_post("/api/notes/share/create",
                               {"path": "Carpeta/nota.md", "password": "secreta"}).json()["token"]
        anon = self.client_class()
        self.assertNotContains(anon.get(f"/s/{token}/"), "contenido compartido")
        self.assertContains(anon.post(f"/s/{token}/", {"password": "secreta"}),
                            "contenido compartido")

    def test_mover_la_nota_no_rompe_el_enlace(self):
        token = self.json_post("/api/notes/share/create",
                               {"path": "Carpeta/nota.md"}).json()["token"]
        self.json_post("/api/notes/move", {"path": "Carpeta/nota.md", "target": ""})
        self.assertEqual(SharedNote.objects.get(token=token).path, "nota.md")
        self.assertContains(self.client_class().get(f"/s/{token}/"), "contenido compartido")

    def test_borrar_la_nota_revoca_el_enlace(self):
        token = self.json_post("/api/notes/share/create",
                               {"path": "Carpeta/nota.md"}).json()["token"]
        self.json_post("/api/notes/delete", {"path": "Carpeta/nota.md"})
        self.assertFalse(SharedNote.objects.filter(token=token).exists())
        self.assertEqual(self.client_class().get(f"/s/{token}/").status_code, 404)

    def test_borrar_la_carpeta_revoca_los_enlaces_de_dentro(self):
        self.json_post("/api/notes/share/create", {"path": "Carpeta/nota.md"})
        self.json_post("/api/notes/delete", {"path": "Carpeta"})
        self.assertEqual(SharedNote.objects.count(), 0)

    def test_consultar_el_estado_no_publica_la_nota(self):
        """`share/status` es de sólo lectura: abrir el modal de "Compartir"
        (que primero consulta el estado) no debe crear el enlace por sí solo,
        sólo pulsar "Guardar" (`share/create`) lo hace."""
        resp = self.client.get("/api/notes/share/status?path=Carpeta/nota.md").json()
        self.assertFalse(resp["shared"])
        self.assertEqual(SharedNote.objects.count(), 0)


class SharedAssetOwnershipTests(VaultTestCase):
    """El enlace público sólo debe resolver imágenes/PDFs que la propia nota
    subió para sí misma — nunca adjuntos ajenos, vivan donde vivan."""

    def setUp(self):
        super().setUp()
        self.editor = self.make_user(username="editor_t", role=User.ROLE_EDITOR)
        self.client.force_login(self.editor)

    def _share(self, path, password=""):
        return self.json_post("/api/notes/share/create",
                              {"path": path, "password": password}).json()["token"]

    def test_caso_legitimo_el_adjunto_subido_para_la_nota_si_se_ve(self):
        self.write_note("Publico/nota.md", "hola")
        up = self.client.post("/api/notes/upload",
                              {"file": _fake_image("foto.jpg"), "note": "Publico/nota.md"})
        name = up.json()["name"]
        self.write_note("Publico/nota.md", f"hola\n![[{name}]]")
        token = self._share("Publico/nota.md")
        anon = self.client_class()
        body = anon.get(f"/s/{token}/").content.decode()
        self.assertIn("asset?p=", body)

    def test_no_se_filtra_un_archivo_fuera_de_adjuntos_por_ruta_literal(self):
        self.write_note("Documentos/secreto.jpg", "PRIVADO")
        self.write_note("Publico/nota.md", "hola\n![alt](Documentos/secreto.jpg)")
        token = self._share("Publico/nota.md")
        anon = self.client_class()
        body = anon.get(f"/s/{token}/").content.decode()
        self.assertNotIn("asset?p=", body)

    def test_no_se_filtra_un_adjunto_de_otra_nota_sin_relacion(self):
        self.write_note("Privado/finanzas.md", "notas")
        up = self.client.post("/api/notes/upload",
                              {"file": _fake_image("factura.jpg"), "note": "Privado/finanzas.md"})
        name = up.json()["name"]
        self.write_note("Publico/nota.md", f"hola\n![[{name}]]")
        token = self._share("Publico/nota.md")
        anon = self.client_class()
        body = anon.get(f"/s/{token}/").content.decode()
        self.assertNotIn("asset?p=", body)

    def test_no_se_filtra_un_adjunto_previo_al_control_de_dueno(self):
        # Simula un adjunto subido antes de este fix: aterriza en Adjuntos/
        # pero sin pasar por save_upload(note_path=...), así que no queda
        # registrado ningún dueño.
        self.write_note("Adjuntos/viejo.jpg", "PREVIO")
        self.write_note("Publico/nota.md", "hola\n![[viejo.jpg]]")
        token = self._share("Publico/nota.md")
        anon = self.client_class()
        body = anon.get(f"/s/{token}/").content.decode()
        self.assertNotIn("asset?p=", body)


def _fake_image(name):
    f = io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"0" * 64)
    f.name = name
    return f


class ReadOnlyRoleTests(VaultTestCase):
    """El rol de sólo lectura se aplica en el servidor, no sólo escondiendo botones."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.make_user(username="invitado", role=User.ROLE_VIEWER))
        self.write_note("nota.md", "original")

    def test_puede_leer(self):
        self.assertEqual(self.client.get("/api/notes/tree").status_code, 200)
        self.assertEqual(self.client.get("/api/notes/file?path=nota.md").status_code, 200)

    def test_no_puede_escribir_ni_borrar(self):
        for url, payload in (
            ("/api/notes/save", {"path": "nota.md", "content": "pisado"}),
            ("/api/notes/create", {"parent": "", "name": "nueva"}),
            ("/api/notes/delete", {"path": "nota.md"}),
            ("/api/notes/rename", {"path": "nota.md", "name": "otra"}),
            ("/api/notes/share/create", {"path": "nota.md"}),
        ):
            self.assertEqual(self.json_post(url, payload).status_code, 403, url)
        self.assertEqual((self.vault_dir / "nota.md").read_text(encoding="utf-8"), "original")

    def test_no_puede_listar_los_enlaces_compartidos(self):
        """El token de un enlace público abre la nota sin autenticar: listar
        enlaces exige el mismo permiso que crearlos/revocarlos, no basta con
        estar logueado."""
        self.assertEqual(self.client.get("/api/notes/share/list").status_code, 403)

    def test_no_puede_tocar_las_claves_de_api(self):
        self.assertEqual(self.client.get("/api/apikeys/list").status_code, 403)
        self.assertEqual(self.json_post("/api/apikeys/create", {"name": "x"}).status_code, 403)

    def test_no_puede_gestionar_accesos(self):
        self.assertEqual(self.client.get("/api/users/list").status_code, 403)
        self.assertEqual(self.json_post("/api/users/create", {
            "username": "otro", "password": "clave-larga-1", "role": "editor"}).status_code, 403)
        self.assertEqual(User.objects.count(), 1)


class AccountTests(VaultTestCase):
    def setUp(self):
        super().setUp()
        self.user = self.make_user()
        self.client.force_login(self.user)

    def test_la_pagina_de_ajustes_se_pinta(self):
        """Ajustes dejó de ser un modal global y ahora es una página propia."""
        resp = self.client.get("/settings/")
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "accounts/settings.html")
        html = resp.content.decode()
        # El propietario ve las tres secciones y el hueco donde el JS pinta.
        self.assertIn('id="settings-theme-picker"', html)
        self.assertIn('id="shared-links-list"', html)
        self.assertIn('id="apikeys-list"', html)
        # Y ya no queda rastro del modal en el layout común.
        self.assertNotIn('id="settings-modal"', html)

    def test_los_ajustes_piden_sesion(self):
        self.client.logout()
        resp = self.client.get("/settings/")
        # La raíz es quien enseña el login al anónimo (ver `core.views.root`).
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], "/?next=/settings/")

    def test_un_invitado_no_ve_las_claves_de_api_en_ajustes(self):
        self.client.force_login(self.make_user("lector", role=User.ROLE_VIEWER))
        html = self.client.get("/settings/").content.decode()
        self.assertIn('id="shared-links-list"', html)
        self.assertNotIn('id="apikeys-list"', html)

    def test_cambiar_tema(self):
        self.assertEqual(self.json_post("/api/profile/set-theme", {"theme": "gold"}).status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.theme, "gold")
        self.assertEqual(self.json_post("/api/profile/set-theme",
                                        {"theme": "inventado"}).status_code, 400)

    def test_el_propietario_crea_un_invitado_de_solo_lectura(self):
        resp = self.json_post("/api/users/create", {
            "username": "lector", "password": "clave-larga-1", "role": "viewer"})
        self.assertEqual(resp.status_code, 201)
        self.assertFalse(User.objects.get(username="lector").can_write)

    def test_no_se_puede_crear_un_invitado_propietario(self):
        resp = self.json_post("/api/users/create", {
            "username": "colado", "password": "clave-larga-1", "role": "owner"})
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(User.objects.filter(username="colado").exists())

    def test_el_propietario_no_se_puede_borrar_a_si_mismo(self):
        resp = self.json_post("/api/users/delete", {"id": self.user.pk})
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_crear_y_revocar_una_clave_de_api(self):
        created = self.json_post("/api/apikeys/create", {"name": "Claude"}).json()["key"]
        self.assertTrue(created["secret"].startswith("cgny_"))
        self.assertNotIn(created["secret"], json.dumps(
            self.client.get("/api/apikeys/list").json()))
        self.assertEqual(self.json_post("/api/apikeys/revoke",
                                        {"id": created["id"]}).status_code, 200)
        self.assertEqual(self.client.get("/api/apikeys/list").json()["keys"], [])
