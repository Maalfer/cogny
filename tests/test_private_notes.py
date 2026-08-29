"""Notas privadas: invisibles desde `/conocimiento`, iguales en Cogny con sesión.

Lo que se comprueba, por orden de importancia:

1. Marcarla oculta la nota del árbol, la nota misma y la búsqueda públicos —
   pero NO de la web con sesión, donde sigue viéndose (con `private: true`).
2. Sólo el propietario puede marcar/desmarcar (mismo criterio que la
   configuración de la propia bóveda pública).
3. Renombrar/mover/borrar mantiene el registro consistente: la marca sigue a
   la nota, y borrar no deja una ruta fantasma marcada para siempre.
"""
from apps.accounts.models import User
from apps.knowledge.models import PublicVault

from .base import VaultTestCase

API = "/conocimiento/api"


class PrivateNoteVisibilityTests(VaultTestCase):
    def setUp(self):
        super().setUp()
        cfg = PublicVault.get()
        cfg.enabled = True
        cfg.save()
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
