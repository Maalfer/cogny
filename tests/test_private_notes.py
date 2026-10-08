"""Notas y carpetas privadas: invisibles desde `/conocimiento`, iguales en
Cogny con sesión.

Lo que se comprueba, por orden de importancia:

0. Una CARPETA marcada esconde todo lo que cuelga de ella —incluidas las notas
   que se creen dentro DESPUÉS— y al desmarcarla no se publica lo que ya
   tenía marca propia (`PrivateFolderTests`).

1. Marcarla oculta la nota del árbol, la nota misma y la búsqueda públicos —
   pero NO de la web con sesión, donde sigue viéndose (con `private: true`).
2. Sólo el propietario puede marcar/desmarcar (mismo criterio que la
   configuración de la propia bóveda pública).
3. Renombrar/mover/borrar mantiene el registro consistente: la marca sigue a
   la nota, y borrar no deja una ruta fantasma marcada para siempre.
4. Un adjunto que sólo enlaza una nota privada tampoco queda servible por
   URL directa — la privacidad no se queda a medias en la primera imagen.
5. Dos peticiones que mutan `.private.json` a la vez (dos togglees, o un
   toggle y un borrado) no se pisan entre sí — dos hilos reales, no un mock.
"""
import io
import threading

from apps.accounts.models import User
from apps.knowledge.models import MasterLink, PublicVault

from .base import VaultTestCase

API = "/conocimiento/api"


def _enter_public_vault(client):
    """Canjea un enlace maestro de usar y tirar: única puerta de entrada a la
    bóveda pública ahora que no hay filtro por dominio/Referer."""
    link = MasterLink.objects.create(name="test")
    client.get(f"/conocimiento/m/{link.token}/")


class PrivateNoteVisibilityTests(VaultTestCase):
    def setUp(self):
        super().setUp()
        cfg = PublicVault.get()
        cfg.enabled = True
        cfg.save()
        _enter_public_vault(self.client)
        self.owner = self.make_user()
        self.client.force_login(self.owner)
        self.write_note("Linux/Publica.md", "contenido público")
        self.write_note("Linux/Secreta.md", "contenido a esconder")

    def _set_private(self, path: str, private: bool):
        return self.json_post("/api/notes/set-private", {"path": path, "private": private})

    def test_antes_de_marcar_se_ve_en_conocimiento(self):
        names = [n["name"] for n in self.client.get(API + "/tree").json()["tree"][0]["children"]]
        self.assertEqual(sorted(names), ["Publica", "Secreta"])

    def test_marcarla_la_oculta_del_arbol_publico_pero_no_del_de_sesion(self):
        self.assertEqual(self._set_private("Linux/Secreta.md", True).status_code, 200)

        public_names = [n["name"] for n in self.client.get(API + "/tree").json()["tree"][0]["children"]]
        self.assertEqual(public_names, ["Publica"])

        session_tree = self.client.get("/api/notes/tree").json()["tree"][0]["children"]
        session_names = {n["name"]: n.get("private") for n in session_tree}
        self.assertEqual(session_names, {"Publica": False, "Secreta": True})

    def test_marcarla_la_oculta_de_la_nota_y_de_la_busqueda_publicas(self):
        self._set_private("Linux/Secreta.md", True)

        resp = self.client.get(API + "/note?path=Linux/Secreta.md")
        self.assertEqual(resp.status_code, 404)

        hits = self.client.get(API + "/search?q=esconder").json()["results"]
        self.assertEqual(hits, [])
        # La otra nota, sin marcar, se sigue encontrando con normalidad.
        hits = self.client.get(API + "/search?q=público").json()["results"]
        self.assertEqual([h["path"] for h in hits], ["Linux/Publica.md"])

    def test_hacerla_publica_de_nuevo_la_devuelve(self):
        self._set_private("Linux/Secreta.md", True)
        self._set_private("Linux/Secreta.md", False)
        public_names = [n["name"] for n in self.client.get(API + "/tree").json()["tree"][0]["children"]]
        self.assertEqual(sorted(public_names), ["Publica", "Secreta"])
        self.assertEqual(self.client.get(API + "/note?path=Linux/Secreta.md").status_code, 200)

    def test_solo_el_propietario_puede_marcarla(self):
        editor = self.make_user(username="editora", role=User.ROLE_EDITOR)
        self.client.force_login(editor)
        resp = self._set_private("Linux/Secreta.md", True)
        self.assertEqual(resp.status_code, 403)
        # No ha cambiado nada: sigue visible en /conocimiento.
        public_names = [n["name"] for n in self.client.get(API + "/tree").json()["tree"][0]["children"]]
        self.assertIn("Secreta", public_names)

    def test_una_nota_privada_dentro_de_una_carpeta_no_oculta_las_demas(self):
        self._set_private("Linux/Secreta.md", True)
        tree = self.client.get(API + "/tree").json()["tree"]
        # La carpeta sigue existiendo (no es lo que se marca), sólo falta su hija privada.
        self.assertEqual([f["name"] for f in tree], ["Linux"])
        self.assertEqual([n["name"] for n in tree[0]["children"]], ["Publica"])


class PrivateFolderTests(VaultTestCase):
    """Marcar una CARPETA esconde todo lo que cuelga de ella, sin marcar nota
    a nota: es la diferencia entre "oculto esta nota" y "esta rama entera no
    sale de casa", y tiene que aguantar que se creen notas dentro después."""

    def setUp(self):
        super().setUp()
        cfg = PublicVault.get()
        cfg.enabled = True
        cfg.save()
        _enter_public_vault(self.client)
        self.owner = self.make_user()
        self.client.force_login(self.owner)
        self.write_note("Trabajo/Informe.md", "cifras confidenciales")
        self.write_note("Trabajo/Clientes/Acme.md", "contrato de acme")
        self.write_note("Blog/Publica.md", "esto sí se enseña")

    def _set_private(self, path: str, private: bool):
        return self.json_post("/api/notes/set-private", {"path": path, "private": private})

    def _public_tree(self):
        return self.client.get(API + "/tree").json()["tree"]

    def test_marcar_la_carpeta_la_oculta_entera_del_arbol_publico(self):
        self.assertEqual(self._set_private("Trabajo", True).status_code, 200)
        self.assertEqual([f["name"] for f in self._public_tree()], ["Blog"])

    def test_lo_que_hay_dentro_deja_de_leerse_y_de_buscarse(self):
        self._set_private("Trabajo", True)
        # También la nota de la SUBcarpeta: la marca baja hasta el fondo.
        self.assertEqual(self.client.get(API + "/note?path=Trabajo/Informe.md").status_code, 404)
        self.assertEqual(
            self.client.get(API + "/note?path=Trabajo/Clientes/Acme.md").status_code, 404)
        self.assertEqual(self.client.get(API + "/search?q=acme").json()["results"], [])
        hits = self.client.get(API + "/search?q=enseña").json()["results"]
        self.assertEqual([h["path"] for h in hits], ["Blog/Publica.md"])

    def test_una_nota_creada_despues_dentro_nace_privada(self):
        self._set_private("Trabajo", True)
        self.assertEqual(
            self.json_post("/api/notes/create", {"parent": "Trabajo", "name": "Nueva"}).status_code,
            200)
        self.assertEqual(self.client.get(API + "/note?path=Trabajo/Nueva.md").status_code, 404)

    def test_con_sesion_se_ve_todo_y_se_distingue_marca_propia_de_heredada(self):
        self._set_private("Trabajo", True)
        tree = self.client.get("/api/notes/tree").json()["tree"]
        trabajo = next(f for f in tree if f["name"] == "Trabajo")
        self.assertTrue(trabajo["private"])
        self.assertFalse(trabajo["private_inherited"])
        # La nota de dentro no lleva marca PROPIA (nadie la puso), pero está
        # oculta: el frontend usa justo esa diferencia para no ofrecer un
        # "Hacer pública" que no publicaría nada.
        informe = next(n for n in trabajo["children"] if n["name"] == "Informe")
        self.assertFalse(informe["private"])
        self.assertTrue(informe["private_inherited"])
        clientes = next(f for f in trabajo["children"] if f["name"] == "Clientes")
        self.assertTrue(clientes["private_inherited"])
        self.assertTrue(clientes["children"][0]["private_inherited"])

    def test_hacer_publica_la_carpeta_no_publica_lo_que_ya_era_privado_aparte(self):
        self._set_private("Trabajo/Informe.md", True)
        self._set_private("Trabajo", True)
        self._set_private("Trabajo", False)
        # Vuelve la carpeta y la nota que nunca se marcó...
        self.assertEqual(
            self.client.get(API + "/note?path=Trabajo/Clientes/Acme.md").status_code, 200)
        # ...pero la que sí tenía marca propia sigue oculta.
        self.assertEqual(self.client.get(API + "/note?path=Trabajo/Informe.md").status_code, 404)

    def test_renombrar_la_carpeta_conserva_la_marca(self):
        self._set_private("Trabajo", True)
        resp = self.json_post("/api/notes/rename", {"path": "Trabajo", "name": "Curro"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([f["name"] for f in self._public_tree()], ["Blog"])
        self.assertEqual(self.client.get(API + "/note?path=Curro/Informe.md").status_code, 404)

    def test_sacar_una_nota_de_la_carpeta_privada_la_publica(self):
        self._set_private("Trabajo", True)
        resp = self.json_post("/api/notes/move", {"path": "Trabajo/Informe.md", "target": "Blog"})
        self.assertEqual(resp.status_code, 200)
        # Sin marca propia, fuera de la carpeta ya no hay nada que la oculte.
        self.assertEqual(self.client.get(API + "/note?path=Blog/Informe.md").status_code, 200)

    def test_adjunto_de_una_nota_dentro_de_carpeta_privada_no_se_sirve(self):
        up = self.client.post("/api/notes/upload",
                              {"file": _fake_image("img.png"), "note": "Trabajo/Informe.md"})
        self.assertEqual(up.status_code, 200)
        path = up.json()["path"]
        self.assertEqual(self.client.get(API + f"/asset?path={path}").status_code, 200)
        self._set_private("Trabajo", True)
        self.assertEqual(self.client.get(API + f"/asset?path={path}").status_code, 404)

    def test_solo_el_propietario_puede_marcar_una_carpeta(self):
        self.client.force_login(self.make_user(username="editora", role=User.ROLE_EDITOR))
        self.assertEqual(self._set_private("Trabajo", True).status_code, 403)
        self.assertEqual(sorted(f["name"] for f in self._public_tree()), ["Blog", "Trabajo"])

    def test_no_se_puede_marcar_la_raiz_de_la_boveda(self):
        resp = self._set_private("", True)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(sorted(f["name"] for f in self._public_tree()), ["Blog", "Trabajo"])


class PrivateNoteBookkeepingTests(VaultTestCase):
    """El registro de privacidad (`.private.json`) sigue a la nota, no se queda huérfano."""

    def setUp(self):
        super().setUp()
        self.owner = self.make_user()
        self.client.force_login(self.owner)
        self.write_note("nota.md", "contenido")
        self.json_post("/api/notes/set-private", {"path": "nota.md", "private": True})

    def test_renombrar_conserva_la_marca(self):
        resp = self.json_post("/api/notes/rename", {"path": "nota.md", "name": "renombrada"})
        self.assertEqual(resp.status_code, 200)
        tree = self.client.get("/api/notes/tree").json()["tree"]
        self.assertEqual(tree[0]["name"], "renombrada")
        self.assertTrue(tree[0]["private"])

    def test_mover_conserva_la_marca(self):
        self.json_post("/api/notes/create", {"parent": "", "name": "Destino", "type": "folder"})
        resp = self.json_post("/api/notes/move", {"path": "nota.md", "target": "Destino"})
        self.assertEqual(resp.status_code, 200)
        tree = self.client.get("/api/notes/tree").json()["tree"]
        destino = next(f for f in tree if f["name"] == "Destino")
        self.assertTrue(destino["children"][0]["private"])

    def test_mover_la_carpeta_contenedora_conserva_la_marca_de_la_nota_de_dentro(self):
        self.json_post("/api/notes/create", {"parent": "", "name": "Origen", "type": "folder"})
        self.json_post("/api/notes/move", {"path": "nota.md", "target": "Origen"})
        self.json_post("/api/notes/create", {"parent": "", "name": "Destino", "type": "folder"})
        resp = self.json_post("/api/notes/move", {"path": "Origen", "target": "Destino"})
        self.assertEqual(resp.status_code, 200)
        tree = self.client.get("/api/notes/tree").json()["tree"]
        destino = next(f for f in tree if f["name"] == "Destino")
        origen = destino["children"][0]
        self.assertTrue(origen["children"][0]["private"])

    def test_borrar_no_deja_una_ruta_fantasma_marcada(self):
        self.assertEqual(self.json_post("/api/notes/delete", {"path": "nota.md"}).status_code, 200)
        # Una nota nueva creada con el mismo nombre no hereda la marca del rastro
        # que dejó la borrada — sería una fuga de privacidad completamente
        # inesperada para quien sólo está creando una nota normal.
        resp = self.json_post("/api/notes/create", {"parent": "", "name": "nota"})
        self.assertEqual(resp.status_code, 200)
        tree = self.client.get("/api/notes/tree").json()["tree"]
        self.assertFalse(tree[0]["private"])


def _fake_image(name):
    f = io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"0" * 64)
    f.name = name
    return f


class PrivateNoteAssetTests(VaultTestCase):
    """Un adjunto que sólo enlaza una nota privada no debe quedar servible por
    URL directa en `/conocimiento` — ocultar el texto y dejar la imagen suelta
    sería una privacidad a medias."""

    def setUp(self):
        super().setUp()
        cfg = PublicVault.get()
        cfg.enabled = True
        cfg.save()
        _enter_public_vault(self.client)
        self.owner = self.make_user()
        self.client.force_login(self.owner)
        self.write_note("privada.md", "hola")
        self.write_note("publica.md", "hola")
        self.json_post("/api/notes/set-private", {"path": "privada.md", "private": True})

    def _upload_for(self, note_path):
        up = self.client.post("/api/notes/upload",
                              {"file": _fake_image("img.png"), "note": note_path})
        self.assertEqual(up.status_code, 200)
        return up.json()["path"]

    def test_adjunto_de_nota_privada_no_se_sirve(self):
        path = self._upload_for("privada.md")
        resp = self.client.get(API + f"/asset?path={path}")
        self.assertEqual(resp.status_code, 404)

    def test_adjunto_de_nota_publica_se_sigue_sirviendo(self):
        path = self._upload_for("publica.md")
        resp = self.client.get(API + f"/asset?path={path}")
        self.assertEqual(resp.status_code, 200)

    def test_adjunto_sin_dueno_registrado_se_sigue_sirviendo(self):
        # Simula un adjunto subido antes de que existiera el registro de
        # dueño (`_record_attachment_owner`): sin fila en `.owners.json`.
        path = self._upload_for("")
        resp = self.client.get(API + f"/asset?path={path}")
        self.assertEqual(resp.status_code, 200)


class PrivateFileLockingTests(VaultTestCase):
    """`.private.json` es un único fichero global que toca cualquier
    rename/move/delete/toggle de la bóveda — bajo escritura concurrente real
    (hilos, no mocks: gunicorn corre con varios hilos por worker) no debe
    perderse ninguna actualización."""

    def test_marcar_muchas_notas_a_la_vez_no_pierde_ninguna(self):
        from apps.notes import vault

        n = 25
        for i in range(n):
            self.write_note(f"nota{i}.md", "x")
        threads = [
            threading.Thread(target=vault.set_private, args=(self.vault_dir, f"nota{i}.md", True))
            for i in range(n)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(vault.read_private(self.vault_dir), {f"nota{i}.md" for i in range(n)})
