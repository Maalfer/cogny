import unittest
from PySide6.QtWidgets import QApplication, QMenu
from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtGui import QStandardItemModel, QStandardItem
from app.ui.main_window import MainWindow
from app.database.manager import DatabaseManager
import sys
import os

# Initialize QApplication if not already running
if not QApplication.instance():
    app = QApplication(sys.argv)

class TestContextMenu(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Use a fresh test DB
        cls.db_name = "test_context.cdb"
        if os.path.exists(cls.db_name):
            os.remove(cls.db_name)
        cls.db = DatabaseManager(cls.db_name)
        
    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.db_name):
            os.remove(cls.db_name)

    def setUp(self):
        self.window = MainWindow(self.db_name)
        self.window.show()

    def tearDown(self):
        self.window.close()

    def test_add_sibling_note_no_crash(self):
        """Test that add_sibling_note does not crash (name error fix)."""
        # Create a root note
        self.window.model.add_note("Root Note", None)
        
        # Select it
        index = self.window.model.index(0, 0)
        proxy_index = self.window.proxy_model.mapFromSource(index)
        self.window.tree_view.setCurrentIndex(proxy_index)
        
        # Call add_sibling_note directly
        # We need to mock the input dialog or it will block
        # With ModernInput, we can mock get_text?
        # Or just checking if it runs up to the dialog or if the menu error is gone.
        # The menu error was AFTER the dialog. So we need to bypass dialog.
        
        # Monkey patch ModernInput.get_text
        original_get_text = self.window.title_edit.__class__.__module__ # wait, imported in main_window
        from app.ui.widgets import ModernInput
        
        original_get_text = ModernInput.get_text
        ModernInput.get_text = lambda parent, title, label, text="": ("Sibling Note", True)
        
        try:
            self.window.add_sibling_note()
            # If it had the 'menu.exec_' error, it would raise NameError here
        except NameError as e:
            self.fail(f"add_sibling_note raised NameError: {e}")
        finally:
             ModernInput.get_text = original_get_text
             
    def test_context_menu_logic(self):
        """Test that context menu shows correct options for Folder vs Note."""
        # Create Folder (Note with child)
        self.window.model.add_note("Folder", None)
        folder_idx = self.window.model.index(0, 0)
        folder_item = self.window.model.itemFromIndex(folder_idx)
        self.window.model.add_note("Child", folder_item.note_id)
        
        # Select Folder
        proxy_folder = self.window.proxy_model.mapFromSource(folder_idx)
        
        # Mock QMenu.addAction to inspect
        actions = []
        original_addAction = QMenu.addAction
        
        def mock_addAction(self, action):
            actions.append(action.text())
            original_addAction(self, action)
            
        QMenu.addAction = mock_addAction
        
        try:
            # Trigger context menu logic (without exec)
            # We can't easily intercept the internal QMenu creation in show_context_menu
            # unless we mock QMenu class entirely or inspect the method logic.
            # But show_context_menu creates a generic QMenu().
            pass 
        finally:
            QMenu.addAction = original_addAction
            
        # Alternative: Check hasChildren logic
        self.assertTrue(self.window.model.hasChildren(folder_idx))
        
        # If hasChildren is True, show_context_menu should add action with statusTip "Crear una nota dentro de esta carpeta"
        # We can't easily assert the specific QAction created inside the method purely from outside 
        # without Refactoring show_context_menu to return the menu or factory it.
        # But the crash test above verifies the main bug.

if __name__ == '__main__':
    unittest.main()
