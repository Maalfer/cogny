
import unittest
import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QModelIndex

# Add app path to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.models.note_model import NoteTreeModel
from app.database.manager import DatabaseManager
# Mocking classes might be needed, but for now we try integration style if possible
# or just test the model logic.
# Since the bug was in GUI logic (MainWindow), testing it requires QApplication.

class TestNoteModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        self.db_name = "test_notes.cdb"
        self.db = DatabaseManager(self.db_name)
        self.db.clear_database()
        self.model = NoteTreeModel(self.db)
        self.model.load_notes()

    def tearDown(self):
        self.db.clear_database()
        if os.path.exists(self.db_name):
            os.remove(self.db_name)

    def test_add_note(self):
        self.model.add_note("Root Note", None)
        self.assertEqual(len(self.model.note_items), 1)
        
    def test_folder_logic(self):
        """Verify hasChildren reflects folder state"""
        self.model.add_note("Folder", None)
        root_id = list(self.model.note_items.keys())[0]
        root_item = self.model.note_items[root_id]
        root_index = root_item.index()
        
        # Initially no children
        self.assertFalse(self.model.hasChildren(root_index))
        
        # Add child
        self.model.add_note("Child", root_id)
        
        # Should have children now
        self.assertTrue(self.model.hasChildren(root_index))

if __name__ == "__main__":
    unittest.main()
