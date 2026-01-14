
import unittest
import sys
import os
import shutil
# from PySide6.QtWidgets import QApplication

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database.manager import DatabaseManager
from app.importers.obsidian import ObsidianImporter

class TestObsidianImport(unittest.TestCase):
    # @classmethod
    # def setUpClass(cls):
    #     if not QApplication.instance():
    #         cls.app = QApplication([])
    #     else:
    #         cls.app = QApplication.instance()

    def setUp(self):
        self.db_name = "test_import.cdb"
        self.db = DatabaseManager(self.db_name)
        self.db.clear_database()
        
        # Test Data Path
        self.vault_path = os.path.abspath("tests/data/mock_vault")
        
        # Ensure Mock Data Exists (Robustness)
        if not os.path.exists(self.vault_path):
            os.makedirs(os.path.join(self.vault_path, "Folder1"), exist_ok=True)
            with open(os.path.join(self.vault_path, "Note1.md"), 'w') as f:
                f.write("# Note 1\nContent with **Markdown**.")
            with open(os.path.join(self.vault_path, "Folder1", "SubNote1.md"), 'w') as f:
                f.write("Sub-note content.")
            with open(os.path.join(self.vault_path, "image.png"), 'w') as f:
                 f.write("Dummy Image Data")
            with open(os.path.join(self.vault_path, "NoteWithImage.md"), 'w') as f:
                 f.write("![Img](image.png)")

    def tearDown(self):
        self.db.clear_database()
        if os.path.exists(self.db_name):
            os.remove(self.db_name)
        # Cleanup mock data
        if os.path.exists(self.vault_path):
            try:
                shutil.rmtree(self.vault_path)
            except:
                pass

    def test_import_structure(self):
        importer = ObsidianImporter(self.db)
        importer.import_vault(self.vault_path)
        
        # 1. Verify Folder Logic
        # "Folder1" should be a note with children
        # Note1.md is just a note
        
        # Check counts
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM notes")
        count = cursor.fetchone()[0]
        # Expect: Note1, NoteWithImage, Folder1, SubNote1 = 4 notes? 
        # Folder1 is a directory, so it becomes a note.
        # SubNote1 is child of Folder1.
        self.assertGreaterEqual(count, 4)
        
        # 2. Verify Hierarchy
        cursor.execute("SELECT id, is_folder FROM notes WHERE title = 'Folder1'")
        folder_data = cursor.fetchone()
        folder_id = folder_data[0]
        self.assertTrue(bool(folder_data[1]), "Folder1 should have is_folder=1")
        
        cursor.execute("SELECT parent_id FROM notes WHERE title = 'SubNote1'")
        subnote_parent = cursor.fetchone()[0]
        
        self.assertEqual(folder_id, subnote_parent)
        
        # 3. Verify Image Logic
        cursor.execute("SELECT COUNT(*) FROM images")
        img_count = cursor.fetchone()[0]
        self.assertEqual(img_count, 1)
        
        # 4. Verify Content Replacement
        cursor.execute("SELECT content FROM notes WHERE title = 'NoteWithImage'")
        content = cursor.fetchone()[0]
        
        # Strict check: Ensure format is exactly <img src="image://db/NUMBER" /> 
        # This format is critical for MainWindow to detect and preserve it.
        import re
        self.assertTrue(re.search(r'<img src="image://db/\d+"\s*/>', content), 
                        f"Content does not contain valid image tag. Content: {content}")
        
        # 5. Verify FTS
        # Search for "Markdown" (in Note1)
        results = self.db.search_notes_fts("Markdown")
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0][1], "Note1")
        
        conn.close()

if __name__ == "__main__":
    unittest.main()
