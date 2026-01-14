
import unittest
import sys
import os
from PySide6.QtWidgets import QApplication
from app.database.manager import DatabaseManager
from app.ui.blueprints.editor_area import EditorArea

if not QApplication.instance():
    app = QApplication(sys.argv)

class TestEditorLoading(unittest.TestCase):
    def setUp(self):
        self.db_name = "test_editor.cdb"
        if os.path.exists(self.db_name):
            os.remove(self.db_name)
        self.db = DatabaseManager(self.db_name)
        self.editor_area = EditorArea(self.db)

    def tearDown(self):
        if os.path.exists(self.db_name):
            os.remove(self.db_name)

    def test_load_note_vs_folder(self):
        # 1. Add Note (is_folder=False)
        note_id = self.db.add_note("My Note", None, is_folder=False)
        
        # Load it
        self.editor_area.load_note(note_id)
        
        # Check ReadOnly
        self.assertFalse(self.editor_area.text_editor.isReadOnly(), "Note should be editable")
        self.assertFalse(self.editor_area.title_edit.isReadOnly(), "Note Title should be editable")
        
        # 2. Add Folder (is_folder=True)
        folder_id = self.db.add_note("My Folder", None, is_folder=True)
        
        # Load it
        self.editor_area.load_note(folder_id)
        
        # Check ReadOnly
        self.assertTrue(self.editor_area.text_editor.isReadOnly(), "Folder should be read-only")
        self.assertTrue(self.editor_area.title_edit.isReadOnly(), "Folder Title should be read-only")
        
        # Verify specific placeholder text if we want to be sure
        # html = self.editor_area.text_editor.toHtml()
        # self.assertIn("Carpeta:", html)

if __name__ == '__main__':
    unittest.main()
