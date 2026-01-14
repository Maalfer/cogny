import unittest
from PySide6.QtWidgets import QApplication, QMenu
from PySide6.QtCore import Qt, QModelIndex, QPoint



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
        self.window.sidebar.model.add_note("Root Note", None)
        
        # Select it
        index = self.window.sidebar.model.index(0, 0)
        proxy_index = self.window.sidebar.proxy_model.mapFromSource(index)
        self.window.sidebar.tree_view.setCurrentIndex(proxy_index)
        
        # Call add_sibling_note directly
        # We need to mock the input dialog or it will block
        # With ModernInput, we can mock get_text?
        # Or just checking if it runs up to the dialog or if the menu error is gone.
        # The menu error was AFTER the dialog. So we need to bypass dialog.
        
        # Monkey patch ModernInput.get_text
        from app.ui.widgets import ModernInput
        
        original_get_text = ModernInput.get_text
        ModernInput.get_text = lambda parent, title, label, text="": ("Sibling Note", True)
        
        try:
            self.window.sidebar.add_sibling_note()
            # If it had the 'menu.exec_' error, it would raise NameError here
        except NameError as e:
            self.fail(f"add_sibling_note raised NameError: {e}")
        finally:
             ModernInput.get_text = original_get_text
             
    def test_context_menu_logic(self):
        """Test that context menu shows correct options for Folder vs Note."""
        # 1. Test Folder
        # Create explicit folder
        self.window.sidebar.model.add_note("Explicit Folder", None, is_folder=True)
        folder_id = [k for k in self.window.sidebar.model.note_items.keys() if self.window.sidebar.model.note_items[k].text() == "Explicit Folder"][0]
        folder_item = self.window.sidebar.model.note_items[folder_id]
        
        # Select Folder
        folder_idx = folder_item.index()
        proxy_folder = self.window.sidebar.proxy_model.mapFromSource(folder_idx)
        self.window.sidebar.tree_view.setCurrentIndex(proxy_folder)
        
        # Mock QMenu.addAction to inspect
        actions = []
        original_exec = QMenu.exec
        
        # We also need to mock exec because show_context_menu calls it
        QMenu.exec = lambda self, pos: None
        
        original_addAction = QMenu.addAction
        def mock_addAction(self, action):
            actions.append(action.text())
            original_addAction(self, action)
            
        QMenu.addAction = mock_addAction
        
        try:
            # Trigger context menu
            # We assume position 0,0 maps to index if we make sure viewport logic works, 
            # but simplest is calling show_context_menu with a point that maps to the selected index?
            # Or simpler: Bypass validation logic inside show_context_menu?
            # NO, show_context_menu uses indexAt(pos). Validating that is hard in unit test without UI render.
            # However, we can trick it by mocking indexAt?
            # Or we can refactor show_context_menu to accept explicit index? No, it's slot.
            
            # Monkey Patch indexAt
            original_indexAt = self.window.sidebar.tree_view.indexAt
            self.window.sidebar.tree_view.indexAt = lambda pos: proxy_folder
            
            self.window.sidebar.show_context_menu(QPoint(0,0))
            
            # Verify Actions for Folder
            print("Actions for Folder:", actions)
            self.assertIn("Crear nota en esta carpeta", actions)
            self.assertNotIn("Exportar a PDF", actions)
            
            # Reset
            actions.clear()
            self.window.sidebar.tree_view.indexAt = original_indexAt
            
            # 2. Test Note
            self.window.sidebar.model.add_note("Regular Note", None, is_folder=False)
            note_id = [k for k in self.window.sidebar.model.note_items.keys() if self.window.sidebar.model.note_items[k].text() == "Regular Note"][0]
            note_item = self.window.sidebar.model.note_items[note_id]
            note_idx = note_item.index()
            proxy_note = self.window.sidebar.proxy_model.mapFromSource(note_idx)
            
            # Monkey Patch indexAt for Note
            self.window.sidebar.tree_view.indexAt = lambda pos: proxy_note
            
            self.window.sidebar.show_context_menu(QPoint(0,0))
            
            print("Actions for Note:", actions)
            self.assertIn("Exportar a PDF", actions)
            self.assertIn("Crear nota (mismo nivel)", actions)
            
            # Restore
            self.window.sidebar.tree_view.indexAt = original_indexAt
            
        finally:
            QMenu.addAction = original_addAction
            QMenu.exec = original_exec
