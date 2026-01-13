
import unittest
import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtGui import QIcon

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.ui.main_window import MainWindow
from app.database.manager import DatabaseManager

class TestSearchSelection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        self.db_name = "test_selection.cdb"
        self.db = DatabaseManager(self.db_name)
        self.db.clear_database()
        self.window = MainWindow(self.db_name)
        
        # Add Data
        self.db.add_note("SelectionTest", None, "Content") 
        
    def tearDown(self):
        self.window.close()
        self.db.clear_database()
        if os.path.exists(self.db_name):
            os.remove(self.db_name)

    def test_search_icon_and_selection(self):
        self.window.on_search_text_changed("SelectionTest")
        
        model = self.window.tree_view.model()
        self.assertEqual(model.rowCount(), 1)
        item = model.item(0)
        
        # 1. Verify Icon (Not Null)
        self.assertFalse(item.icon().isNull())
        
        # 2. Verify Selection
        # Explicitly select the item in the view
        index = model.indexFromItem(item)
        self.window.tree_view.setCurrentIndex(index)
        
        # Check if on_selection_changed was called and updated current_note_id
        # requires logic to run inside MainWindow
        self.assertEqual(self.window.current_note_id, item.note_id)
        self.assertEqual(self.window.title_edit.toPlainText(), "SelectionTest")

if __name__ == "__main__":
    unittest.main()
