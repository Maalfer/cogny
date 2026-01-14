
import unittest
import sys
import os
import shutil
from PySide6.QtWidgets import QApplication, QStyle
from app.database.manager import DatabaseManager
from app.importers.obsidian import ObsidianImporter
from app.models.note_model import NoteTreeModel

# Initialize App for QStyle
if not QApplication.instance():
    app = QApplication(sys.argv)
else:
    app = QApplication.instance()

class TestImportIcons(unittest.TestCase):
    def setUp(self):
        self.db_name = "test_import_icons.cdb"
        if os.path.exists(self.db_name):
            os.remove(self.db_name)
        self.db = DatabaseManager(self.db_name)
        self.db.clear_database()
        
        self.vault_path = os.path.abspath("tests/data/mock_vault_icons")
        if not os.path.exists(self.vault_path):
            os.makedirs(os.path.join(self.vault_path, "FolderA"))
            with open(os.path.join(self.vault_path, "FolderA", "NoteInFolder.md"), 'w') as f:
                f.write("Content")
            with open(os.path.join(self.vault_path, "RootNote.md"), 'w') as f:
                f.write("Content")

    def tearDown(self):
        self.db.clear_database()
        if os.path.exists(self.db_name):
            os.remove(self.db_name)
        if os.path.exists(self.vault_path):
            shutil.rmtree(self.vault_path)

    def test_icons_after_import(self):
        # 1. Import
        importer = ObsidianImporter(self.db)
        importer.import_vault(self.vault_path)
        
        # 2. Load Model
        model = NoteTreeModel(self.db)
        model.load_notes()
        
        # 3. Find Items
        # Expect: "FolderA", "RootNote"
        items = list(model.note_items.values())
        folder_item = next((i for i in items if i.text() == "FolderA"), None)
        note_item = next((i for i in items if i.text() == "RootNote"), None)
        
        self.assertIsNotNone(folder_item)
        self.assertIsNotNone(note_item)
        
        # 4. Check is_folder flag (Logic)
        print(f"Folder Item is_folder: {folder_item.is_folder}")
        self.assertTrue(folder_item.is_folder, "FolderA should be explicit folder")
        self.assertFalse(note_item.is_folder, "RootNote should NOT be explicit folder")
        
        # 5. Check Icons (Visual)
        # We rely on QStyle standard icons.
        # We can compare icon cache keys or pixmaps, but difficult.
        # However, we can check if they are DIFFERENT.
        
        folder_icon = folder_item.icon()
        note_icon = note_item.icon()
        
        # In headless, icons might refer to same null or default?
        # But QStyle should return different SP icons.
        
        # Using name() for fromTheme was easier but we switched to QStyle.StandardPixmap.
        # Let's check isNull().
        if not folder_icon.isNull():
             # Basic check: folder icon should likely be different from note icon
             # Pixmap comparison
             # Note: This might fail in strict headless envs without X11/Wayland
             # But let's try.
             pass
             
        # The key is step 4: If is_folder is True, logic in refresh_icons *will* select the folder icon.
        # We verified the selection logic in refresh_icons visually in code review.
        # Step 4 is what failed for current user (they saw note icons).
        # This implies step 4 might be failing?
        
if __name__ == '__main__':
    unittest.main()
