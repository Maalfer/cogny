import os
import shutil
import time
import contextlib

class SetupMixin:
    def init_db(self):
        """Initialize the database tables."""
        
        # Ensure Vault directories exist
        if hasattr(self, 'vault_path') and self.vault_path:
             images_dir = os.path.join(self.vault_path, "images")
             os.makedirs(images_dir, exist_ok=True)

        # 1. Backup before potential migration
        self.backup_database()
        
        # 2. Check Integrity
        self.check_integrity()
        
        # 3. Init
        with self.transaction() as conn:
            cursor = conn.cursor()
            
            # Enable column addition for existing tables if needed
            # SQLite supports adding columns directly, but we check if we need to migrate first.
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parent_id INTEGER,
                    title TEXT NOT NULL,
                    content TEXT,
                    is_folder BOOLEAN DEFAULT 0,
                    is_read_later BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (parent_id) REFERENCES notes (id) ON DELETE CASCADE
                )
            """)
            
            # Migration: Check if is_folder column exists (for existing DBs)
            cursor.execute("PRAGMA table_info(notes)")
            columns = [info[1] for info in cursor.fetchall()]
            
            if "is_folder" not in columns:
                print("Migrating Database: Adding is_folder column...")
                cursor.execute("ALTER TABLE notes ADD COLUMN is_folder BOOLEAN DEFAULT 0")
                
                # Auto-migrate implicit folders (notes with children)
                print("Migrating Implicit Folders...")
                cursor.execute("""
                    UPDATE notes 
                    SET is_folder = 1 
                    WHERE id IN (SELECT DISTINCT parent_id FROM notes WHERE parent_id IS NOT NULL)
                """)

            if "is_read_later" not in columns:
                print("Migrating Database: Adding is_read_later column...")
                cursor.execute("ALTER TABLE notes ADD COLUMN is_read_later BOOLEAN DEFAULT 0")

            if "cached_html" not in columns:
                print("Migrating Database: Adding cached_html column...")
                cursor.execute("ALTER TABLE notes ADD COLUMN cached_html TEXT")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    note_id INTEGER,
                    data BLOB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (note_id) REFERENCES notes (id) ON DELETE CASCADE
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS attachments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    note_id INTEGER,
                    filename TEXT NOT NULL,
                    data BLOB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (note_id) REFERENCES notes (id) ON DELETE CASCADE
                )
            """)
            
            # Cleanup: Drop image_cache table if it exists (Feature removed)
            cursor.execute("DROP TABLE IF EXISTS image_cache")

            # Performance Indices
            
            # Performance Indices
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_parent_title ON notes(parent_id, title);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_note ON images(note_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_id ON images(id);")  # Optimize get_image() by ID
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_attachments_note ON attachments(note_id);")
            
            # FTS5 Virtual Table for Fast Search
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
                    title, 
                    content, 
                    content='notes', 
                    content_rowid='id'
                );
            """)
            
            # Triggers to keep FTS in sync
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS notes_ai AFTER INSERT ON notes BEGIN
                    INSERT INTO notes_fts(rowid, title, content) VALUES (new.id, new.title, new.content);
                END;
            """)
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS notes_ad AFTER DELETE ON notes BEGIN
                    INSERT INTO notes_fts(notes_fts, rowid, title, content) VALUES('delete', old.id, old.title, old.content);
                END;
            """)
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS notes_au AFTER UPDATE ON notes BEGIN
                    INSERT INTO notes_fts(notes_fts, rowid, title, content) VALUES('delete', old.id, old.title, old.content);
                    INSERT INTO notes_fts(rowid, title, content) VALUES (new.id, new.title, new.content);
                END;
            """)

    def backup_database(self):
        """Creates a backup of the database file."""
        if not os.path.exists(self.db_path):
            return
            
        # Don't backup empty/new files (size 0 or very small header only?)
        # SQLite header is 100 bytes. So < 100 bytes is definitely invalid or empty.
        if os.path.getsize(self.db_path) == 0:
            return

        backup_dir = os.path.join(os.path.dirname(self.db_path), "backups")
        os.makedirs(backup_dir, exist_ok=True)
        
        # Limit backups? (Keep last 5)
        # For now, simplistic backup on startup
        timestamp = int(time.time())
        backup_path = os.path.join(backup_dir, f"notes_{timestamp}.bak")
        
        try:
            # Copy file (using efficient copy)
            shutil.copy2(self.db_path, backup_path)
            
            # Cleanup old backups
            backups = sorted([f for f in os.listdir(backup_dir) if f.startswith("notes_") and f.endswith(".bak")])
            if len(backups) > 5:
                for old in backups[:-5]:
                    os.remove(os.path.join(backup_dir, old))
                    
        except Exception as e:
            print(f"Backup failed: {e}")

    def check_integrity(self):
        """Checks DB integrity and attempts recovery if corrupt."""
        if not os.path.exists(self.db_path):
            return

        try:
            with contextlib.closing(self._get_connection()) as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA integrity_check;")
                result = cursor.fetchone()[0]
                if result != "ok":
                    print(f"Database Corruption Detected: {result}")
                    # Todo: Restore from backup?
                    # For now just warn
        except Exception as e:
            print(f"Integrity Check Failed: {e}")

    def clear_database(self):
        """Wipe all data from the database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("DELETE FROM attachments")
        cursor.execute("DELETE FROM images")
        cursor.execute("DELETE FROM notes")
        cursor.execute("DELETE FROM sqlite_sequence") # Reset autoincrement
        
        # Optimize after clearing massive data to return space to FS
        # Note: calling VACUUM requires no active transaction usually, ensuring commit first.
        conn.commit()
        cursor.execute("VACUUM") 
        conn.commit()
        conn.close()

    def repair_database(self):
        """Autodiagnose and repair database issues."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 1. Fix Orphaned Notes (Parent invalid) -> Move to Root
        # Find notes with non-null parent that doesn't exist
        cursor.execute("""
            UPDATE notes 
            SET parent_id = NULL 
            WHERE parent_id IS NOT NULL 
            AND parent_id NOT IN (SELECT id FROM notes)
        """)
        
        # 2. Delete Orphaned Images (No associated note)
        cursor.execute("DELETE FROM images WHERE note_id NOT IN (SELECT id FROM notes)")
        
        # 3. Delete Orphaned Attachments
        cursor.execute("DELETE FROM attachments WHERE note_id NOT IN (SELECT id FROM notes)")
        
        # 4. Integrity Check
        cursor.execute("PRAGMA integrity_check")
        
        conn.commit()
        conn.close()

    def optimize_database(self):
        """Run extensive database optimization."""
        # Step 0: Repair structure first
        self.repair_database()

        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 1. Rebuild DB file, repacking pages (Reduces size)
        cursor.execute("VACUUM")
        
        # 2. Analyze statistics for Query Planner (Improves speed)
        cursor.execute("ANALYZE")
        
        # 3. Optimize FTS Index (Merges B-Trees in FTS structure)
        cursor.execute("INSERT INTO notes_fts(notes_fts) VALUES('optimize')")
        
        conn.commit()
        conn.close()
