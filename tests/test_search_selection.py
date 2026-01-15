
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
        
        # Patch synchronous loader
        # Patch synchronous loader
        from app.ui.blueprints.workers import NoteLoaderWorker
        from unittest.mock import patch
        
        class SyncLoader(NoteLoaderWorker):
            def __init__(self, db_path, note_id):
                 super().__init__(db_path, note_id)
            def start(self, priority=None):
                self.run()
                
        # Patch the class in the module where it is USED
        self.patcher = patch('app.ui.blueprints.editor_area.NoteLoaderWorker', SyncLoader)
        self.patcher.start()

        
        # Patch QIcon in buscador to return non-null icon
        from PySide6.QtGui import QIcon, QPixmap
        from unittest.mock import patch
        
        class MockQIcon(QIcon):
            @staticmethod
            def fromTheme(name):
                # Return a valid non-null icon
                return QIcon(QPixmap(1, 1))
                
        self.icon_patcher = patch('app.ui.buscador.QIcon', MockQIcon)
        self.icon_patcher.start()
        
        # Add Data
        self.db.add_note("SelectionTest", None, "Content") 
        
    def tearDown(self):
        if hasattr(self, 'patcher'):
            self.patcher.stop()
        if hasattr(self, 'icon_patcher'):
            self.icon_patcher.stop()

        self.window.close()
        self.db.clear_database()
        if os.path.exists(self.db_name):
            os.remove(self.db_name)

    def test_search_icon_and_selection(self):
        # Bypass Debounce Timer for testing
        self.window.search_manager.perform_smart_search("SelectionTest")
        
        model = self.window.sidebar.tree_view.model()
        self.assertEqual(model.rowCount(), 1)
        item = model.item(0)
        
        # 1. Verify Icon (Not Null)
        self.assertFalse(item.icon().isNull())
        
        # 2. Verify Selection
        # Explicitly select the item in the view
        index = model.indexFromItem(item)
        self.window.sidebar.tree_view.setCurrentIndex(index)
        
        # Check if on_selection_changed was called and updated current_note_id
        # requires logic to run inside MainWindow
        self.assertEqual(self.window.editor_area.current_note_id, item.note_id)
        self.assertEqual(self.window.editor_area.title_edit.toPlainText(), "SelectionTest")


if __name__ == "__main__":
    unittest.main()
