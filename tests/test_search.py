
import unittest
import sys
import os
from PySide6.QtWidgets import QApplication, QTreeView
from PySide6.QtCore import Qt, QSortFilterProxyModel
from PySide6.QtGui import QStandardItemModel

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.ui.main_window import MainWindow
from app.database.manager import DatabaseManager

class TestSearchLogic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        self.db_name = "test_search.cdb"
        self.db = DatabaseManager(self.db_name)
        self.db.clear_database()
        # Mock MainWindow partially or just test the logic method if extracted?
        # Since logic is in MainWindow, we instantiate it.
        self.window = MainWindow(self.db_name)
        
        # Add Data
        # Note 1: 3 matches
        self.db.add_note("Apple Apple Apple", None) 
        # Note 2: 1 match
        self.db.add_note("Apple", None)
        # Note 3: 0 matches
        self.db.add_note("Banana", None)
        
    def tearDown(self):
        self.window.close()
        self.db.clear_database()
        if os.path.exists(self.db_name):
            os.remove(self.db_name)

    def test_ranked_search(self):
        # Perform Search
        self.window.on_search_text_changed("Apple")
        
        # Check Model
        model = self.window.tree_view.model()
        self.assertIsInstance(model, QStandardItemModel)
        
        # Should have 2 results (Banana excluded)
        self.assertEqual(model.rowCount(), 2)
        
        # Order: Note 1 (3 matches) > Note 2 (1 match)
        item0 = model.item(0)
        item1 = model.item(1)
        
        self.assertIn("Apple Apple Apple", item0.text())
        self.assertIn("Apple", item1.text())
        
    def test_clear_search(self):
        self.window.on_search_text_changed("Apple")
        self.assertFalse(self.window.tree_view.rootIsDecorated())
        
        self.window.on_search_text_changed("")
        self.assertTrue(self.window.tree_view.rootIsDecorated())
        self.assertIsInstance(self.window.tree_view.model(), QSortFilterProxyModel)

if __name__ == "__main__":
    unittest.main()
