
import sys
import os
import unittest
import sqlite3

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database.manager import DatabaseManager

class TestExplicitFolders(unittest.TestCase):
    def setUp(self):
        self.db_path = "test_folders.cdb"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
            
        self.db = DatabaseManager(self.db_path)
        
    def tearDown(self):
        # db reference might be closed already if test creates new one?
        # DatabaseManager doesn't keep a persistent connection open in self context usually, 
        # it opens/closes per method. 
        # But if we did open one manualy in test...
        pass
        
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except:
                pass

    def test_create_and_retrieve_folder(self):
        print("Testing explicit folder creation...")
        # 1. Create a Folder
        folder_id = self.db.add_note("My Folder", None, is_folder=True)
        
        # 2. Verify in DB
        # Use internal method check
        conn = self.db._get_connection()
        cursor = conn.cursor() 
        cursor.execute("SELECT is_folder FROM notes WHERE id = ?", (folder_id,))
        is_folder = cursor.fetchone()[0]
        conn.close()
        
        self.assertEqual(is_folder, 1, "is_folder should be 1")
        print("Folder creation verified.")
        
    def test_folder_migration(self):
        print("Testing implicit folder migration...")
        # 1. Simulate OLD DB (No is_folder column)
        # Close current db manager actions
        del self.db
        if os.path.exists(self.db_path):
             os.remove(self.db_path)
             
        # Manually create old schema
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id INTEGER,
                title TEXT NOT NULL,
                content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (parent_id) REFERENCES notes (id) ON DELETE CASCADE
            )
        """)
        
        # Insert a parent note (Implicit Folder) 
        cursor.execute("INSERT INTO notes (title) VALUES (?)", ("Parent",))
        parent_id = cursor.lastrowid
        
        cursor.execute("INSERT INTO notes (title, parent_id) VALUES (?, ?)", ("Child", parent_id))
        child_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # 2. Initialize DatabaseManager (Should trigger migration)
        print("Initializing DatabaseManager on old DB...")
        self.db = DatabaseManager(self.db_path)
        
        # 3. Verify Parent is now is_folder=1
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT is_folder FROM notes WHERE id = ?", (parent_id,))
        result = cursor.fetchone()
        conn.close()
        
        self.assertEqual(result[0], 1, "Implicit folder should be migrated to explicit folder")
        print("Migration verified.")

if __name__ == "__main__":
    unittest.main()
