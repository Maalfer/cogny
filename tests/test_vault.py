"""La capa de bóveda: rutas seguras, orden manual, escritura atómica, ZIPs."""
import zipfile

from apps.notes import vault
from apps.notes.vault import VaultError

from .base import VaultTestCase


class SafePathTests(VaultTestCase):
    """La única regla que separa la bóveda del resto del disco."""

    def test_acepta_rutas_normales(self):
        root = vault.root()
        self.assertEqual(vault.safe_path(root, "Carpeta/nota.md"), root / "Carpeta" / "nota.md")
        self.assertEqual(vault.safe_path(root, ""), root)
        self.assertEqual(vault.safe_path(root, "/nota.md"), root / "nota.md")

    def test_rechaza_escapar_de_la_boveda(self):
        root = vault.root()
        for evil in ("../secreto", "a/../../secreto", "..", "a/b/../../../etc/passwd",
                     "..\\..\\secreto"):
            with self.assertRaises(VaultError, msg=evil):
                vault.safe_path(root, evil)

    def test_rechaza_rutas_absurdamente_profundas(self):
        root = vault.root()
        with self.assertRaises(VaultError):
            vault.safe_path(root, "/".join(["x"] * (vault.MAX_PATH_DEPTH + 1)))

    def test_rechaza_symlink_que_apunta_fuera(self):
        root = vault.root()
        (root / "fuga").symlink_to("/etc")
        with self.assertRaises(VaultError):
            vault.safe_path(root, "fuga/passwd")

    def test_tipos_raros_no_revientan(self):
        root = vault.root()
        self.assertEqual(vault.safe_path(root, None), root)
        self.assertEqual(vault.safe_path(root, 42), root)


class SanitizeNameTests(VaultTestCase):
    def test_quita_separadores_y_control(self):
        self.assertEqual(vault.sanitize_name("a/b\\c"), "a-b-c")
        self.assertEqual(vault.sanitize_name('malo<>:"|?*.md'), "malo.md")
        self.assertEqual(vault.sanitize_name("  ..  "), "")

    def test_acota_longitud_y_tipos(self):
        self.assertEqual(len(vault.sanitize_name("x" * 500)), 120)
        self.assertEqual(vault.sanitize_name(None), "")
        self.assertEqual(vault.sanitize_name(7), "")


class AtomicWriteTests(VaultTestCase):
    def test_escribe_y_no_deja_temporales(self):
        target = self.vault_dir / "nota.md"
        vault.write_text_atomic(target, "contenido")
        self.assertEqual(target.read_text(encoding="utf-8"), "contenido")
        self.assertEqual([p.name for p in self.vault_dir.iterdir()], ["nota.md"])

    def test_sobrescribir_conserva_el_contenido_nuevo(self):
        target = self.vault_dir / "nota.md"
        vault.write_text_atomic(target, "v1")
        vault.write_text_atomic(target, "v2")
        self.assertEqual(target.read_text(encoding="utf-8"), "v2")


class OrderTests(VaultTestCase):
    def test_el_orden_manual_manda_y_el_resto_va_alfabetico(self):
        root = vault.root()
        for name in ("b.md", "a.md", "c.md"):
            self.write_note(name)
        vault.write_order(root, ["c.md", "b.md"])
        names = [item["name"] for item in vault.build_tree(root, root)]
        self.assertEqual(names, ["c", "b", "a"])

    def test_set_order_descarta_nombres_inventados(self):
        root = vault.root()
        self.write_note("a.md")
        vault.set_order(root, ["a.md", "no-existe.md", "../fuera"])
        self.assertEqual(vault.read_order(root), ["a.md"])

    def test_el_fichero_de_orden_no_aparece_en_el_arbol(self):
        root = vault.root()
        self.write_note("a.md")
        vault.write_order(root, ["a.md"])
        self.assertEqual([i["name"] for i in vault.build_tree(root, root)], ["a"])


class TreeTests(VaultTestCase):
    def test_distingue_carpetas_notas_y_archivos(self):
        root = vault.root()
        self.write_note("Carpeta/nota.md")
        (root / "imagen.png").write_bytes(b"\x89PNG")
        (root / ".oculto.md").write_text("x", encoding="utf-8")
        tree = {item["name"]: item for item in vault.build_tree(root, root)}
        self.assertEqual(tree["Carpeta"]["type"], "folder")
        self.assertEqual(tree["Carpeta"]["children"][0]["path"], "Carpeta/nota.md")
        self.assertEqual(tree["imagen.png"]["type"], "file")
        self.assertNotIn(".oculto", tree)


class StatsTests(VaultTestCase):
    def test_cuenta_notas_imagenes_y_carpetas(self):
        root = vault.root()
        self.write_note("Carpeta/nota.md", "12345")
        (root / "foto.png").write_bytes(b"0123456789")
        stats = vault.stats(root)
        self.assertEqual(stats["n_notes"], 1)
        self.assertEqual(stats["n_images"], 1)
        self.assertEqual(stats["n_folders"], 1)
        self.assertEqual(stats["total_bytes"], 15)


class ExportImportTests(VaultTestCase):
    def test_el_export_lleva_las_notas_y_salta_lo_oculto(self):
        root = vault.root()
        self.write_note("Carpeta/nota.md", "contenido")
        vault.write_order(root, ["Carpeta"])
        tmp, size = vault.export_zip(root)
        self.assertGreater(size, 0)
        with zipfile.ZipFile(tmp) as zf:
            self.assertEqual(zf.namelist(), ["Carpeta/nota.md"])

    def test_import_merge_conserva_lo_que_ya_habia(self):
        root = vault.root()
        self.write_note("vieja.md", "vieja")
        tmp, _ = vault.export_zip(root)
        self.write_note("otra.md", "otra")
        vault.import_zip(root, tmp, mode="merge")
        self.assertTrue((root / "vieja.md").exists())
        self.assertTrue((root / "otra.md").exists())

    def test_import_replace_sustituye(self):
        root = vault.root()
        self.write_note("solo-esta.md", "x")
        tmp, _ = vault.export_zip(root)
        self.write_note("sobrante.md", "y")
        vault.import_zip(root, tmp, mode="replace")
        self.assertTrue((root / "solo-esta.md").exists())
        self.assertFalse((root / "sobrante.md").exists())

    def test_rechaza_un_zip_con_rutas_que_escapan(self):
        root = vault.root()
        evil = self.tmp_root / "malicioso.zip"
        with zipfile.ZipFile(evil, "w") as zf:
            zf.writestr("../fuera.md", "boom")
        with open(evil, "rb") as fh, self.assertRaises(VaultError):
            vault.import_zip(root, fh)
        self.assertFalse((self.tmp_root / "fuera.md").exists())

    def test_rechaza_algo_que_no_es_un_zip(self):
        with self.assertRaises(VaultError):
            vault.import_zip(vault.root(), __import__("io").BytesIO(b"no soy un zip"))


class SearchTests(VaultTestCase):
    def test_exige_todos_los_terminos(self):
        root = vault.root()
        self.write_note("a.md", "gato y perro")
        self.write_note("b.md", "sólo gato")
        hits = [p.name for p, _ in vault.search_notes(root, ["gato", "perro"], 10, 10, 10)]
        self.assertEqual(hits, ["a.md"])

    def test_respeta_el_limite(self):
        root = vault.root()
        for i in range(5):
            self.write_note(f"n{i}.md", "aguja")
        hits = list(vault.search_notes(root, ["aguja"], 2, 10, 10))
        self.assertEqual(len(hits), 2)
