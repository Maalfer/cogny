
import unittest
import os
import tempfile
from PySide6.QtWidgets import QApplication
from app.models.note_model import NoteTreeModel
from app.database.manager import DatabaseManager
import sys

if not QApplication.instance():
    app = QApplication(sys.argv)

class TestBugNoteCreation(unittest.TestCase):
    def setUp(self):
        self.db_name = "test_bug.cdb"
        if os.path.exists(self.db_name):
            os.remove(self.db_name)
        self.db = DatabaseManager(self.db_name)
        self.model = NoteTreeModel(self.db)

    def tearDown(self):
        if os.path.exists(self.db_name):
            os.remove(self.db_name)

    def test_sidebar_creation_flow(self):
        from app.ui.blueprints.sidebar import Sidebar
        from app.ui.widgets import ModernInput

        # We need a MainWindow context for Sidebar? No, just QWidget parent usually.
        # Sidebar needs (db_manager, parent).
        sidebar = Sidebar(self.db)
        
        # Mock ModernInput.get_text
        original_get_text = ModernInput.get_text
        ModernInput.get_text = lambda parent, title, label, text="": ("Test Note UI", True)
        
        try:
            # 1. Add Root Note via Sidebar
            sidebar.add_root_note()
            
            # Verify
            # Get the note from model
            # Note: We need to find the ID. keys() is dict keys.
            keys = list(sidebar.model.note_items.keys())
            self.assertTrue(len(keys) > 0)
            note_id = keys[0]
            item = sidebar.model.note_items[note_id]
            self.assertEqual(item.text(), "Test Note UI")
            self.assertFalse(item.is_folder, "Root Note should not be a folder")
            
            # Verify Flags (Should NOT accept drops if it's a leaf note)
            idx = item.index()
            flags = sidebar.model.flags(idx)
            from PySide6.QtCore import Qt
            self.assertFalse(flags & Qt.ItemIsDropEnabled, "Leaf Note should NOT accept drops")
            
            # Verify Icon (Skip check in headless environment, assuming QStyle works)
            # icon_name = item.icon().name()
            # self.assertEqual(icon_name, "text-x-generic")

            # 2. Select this note (simulate selection)
            index = item.index()
            # We need to map to proxy if we want to use sidebar selection logic fully?
            # Or just set current index on view.
            proxy_idx = sidebar.proxy_model.mapFromSource(index)
            sidebar.tree_view.setCurrentIndex(proxy_idx)
            
            # 3. Add Sibling Note
            ModernInput.get_text = lambda parent, title, label, text="": ("Sibling Note UI", True)
            sidebar.add_sibling_note()
            
            # Verify sibling
            # Should appear in roots (since parent was None)
            # Inspect new item
            new_keys = [k for k in sidebar.model.note_items.keys() if k != note_id]
            self.assertEqual(len(new_keys), 1)
            sibling_id = new_keys[0]
            sibling_item = sidebar.model.note_items[sibling_id]
            
            self.assertFalse(sibling_item.is_folder, "Sibling Note should not be a folder")
            
            # Select sibling to add child to it
            sibling_idx = sibling_item.index()
            proxy_sibling_idx = sidebar.proxy_model.mapFromSource(sibling_idx)
            sidebar.tree_view.setCurrentIndex(proxy_sibling_idx)
    
            # 4. Add Child Note to Sibling
            ModernInput.get_text = lambda parent, title, label, text="": ("Child Note UI", True)
            sidebar.add_child_note()
            
            # Verify child
            sibling_item = sidebar.model.note_items[sibling_id]
            self.assertTrue(sibling_item.rowCount() > 0)
            child_item = sibling_item.child(0)
            self.assertFalse(child_item.is_folder, "Child Note should not be a folder")
            
            # 5. Create Folder
            ModernInput.get_text = lambda parent, title, label, text="": ("Test Folder", True)
            sidebar.add_root_folder()
            
            # Find folder id
            folder_id = [k for k in sidebar.model.note_items.keys() if sidebar.model.note_items[k].text() == "Test Folder"][0]
            folder_item = sidebar.model.note_items[folder_id]
            self.assertTrue(folder_item.is_folder)
            
            # Select Folder
            index = folder_item.index()
            proxy_idx = sidebar.proxy_model.mapFromSource(index)
            sidebar.tree_view.setCurrentIndex(proxy_idx)
            
            # 6. Add Sibling Note (next to folder)
            ModernInput.get_text = lambda parent, title, label, text="": ("Sibling of Folder", True)
            sidebar.add_sibling_note()
            
            # Verify
            sibling_folder_id = [k for k in sidebar.model.note_items.keys() if sidebar.model.note_items[k].text() == "Sibling of Folder"][0]
            sibling_folder_item = sidebar.model.note_items[sibling_folder_id]
            self.assertFalse(sibling_folder_item.is_folder, "Sibling of Folder should NOT be a folder")
            
        finally:
            ModernInput.get_text = original_get_text

if __name__ == '__main__':
    unittest.main()
