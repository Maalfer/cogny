
import unittest
import os
from unittest.mock import MagicMock
from PySide6.QtWidgets import QApplication, QTreeView
from PySide6.QtCore import QSortFilterProxyModel
from app.database.manager import DatabaseManager
from app.ui.buscador import SearchManager

class TestSearchFunctionality(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create App instance for QObjects
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        # Use temp file for DB to persist across connections in DatabaseManager
        import tempfile
        self.db_fd, self.db_path = tempfile.mkstemp()
        os.close(self.db_fd) # Close handle so sqlite can open it by name
        
        self.db = DatabaseManager(self.db_path)
        
        # Populate with Test Data
        self.populate_db()
        
        # Mock UI components
        self.tree_view = MagicMock(spec=QTreeView)
        self.proxy_model = MagicMock(spec=QSortFilterProxyModel)
        
        self.search_manager = SearchManager(self.db, self.tree_view, self.proxy_model)

    def populate_db(self):
        # Add Notes
        self.db.add_note("Receta de Paella", None, "Ingredientes: Arroz, Azafran, Pollo, Conejo. La paella es tipica de Valencia.")
        self.db.add_note("Meeting Notes", None, "Discussed project timeline, python usage, and database optimization.")
        self.db.add_note("Lista de la Compra", None, "Leche, Huevos, Arroz, Pan.")
        self.db.add_note("Python Tips", None, "Use list comprehensions for cleaner code.")

    def test_exact_match(self):
        # Test searching for a specific word present in title
        results = self.search_manager.search_db_smart("Paella")
        self.assertTrue(len(results) > 0)
        titles = [r[1] for r in results]
        self.assertIn("Receta de Paella", titles)

    def test_partial_match_logic(self):
        # Test searching for a word prefix (e.g., "optimiz" -> optimization)
        results = self.search_manager.search_db_smart("optimiz")
        self.assertTrue(len(results) > 0)
        titles = [r[1] for r in results]
        self.assertIn("Meeting Notes", titles)

    def test_multiple_tokens_and_logic(self):
        # Test searching for two words that appear in the same document
        # "python" and "code" are in "Python Tips"
        results = self.search_manager.search_db_smart("python code")
        titles = [r[1] for r in results]
        self.assertIn("Python Tips", titles)
        
        # "Discussed" and "timeline" in "Meeting Notes"
        results = self.search_manager.search_db_smart("Discussed timeline")
        titles = [r[1] for r in results]
        self.assertIn("Meeting Notes", titles)

    def test_google_like_or_fallback(self):
        # Test searching for multiple words where only SOME might match (OR logic fallback / relevance)
        # "Arroz" is in Paella and Compra. "Timeline" is in Meeting.
        # If I search "Arroz Timeline", I should get all 3 if implementation is essentially OR.
        results = self.search_manager.search_db_smart("Arroz Timeline")
        titles = [r[1] for r in results]
        self.assertIn("Receta de Paella", titles)
        self.assertIn("Lista de la Compra", titles)
        self.assertIn("Meeting Notes", titles)

    def test_snippet_generation(self):
        # Verify that we get a snippet
        results = self.search_manager.search_db_smart("Azafran")
        self.assertTrue(len(results) > 0)
        snippet = results[0][2] # id, title, snip, rank
        self.assertIsNotNone(snippet)
        self.assertIn("<b>", snippet) # Verify highlighting tags from snippet() function used in manager
        
    def test_empty_search(self):
        results = self.search_manager.search_db_smart("")
        self.assertEqual(len(results), 0)
        
        results = self.search_manager.search_db_smart("   ")
        self.assertEqual(len(results), 0)

    def tearDown(self):
        # Cleanup temp file
        if hasattr(self, 'db_path') and os.path.exists(self.db_path):
             os.remove(self.db_path)
             pass

if __name__ == '__main__':
    unittest.main()
