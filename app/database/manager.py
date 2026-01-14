import sqlite3
from typing import List, Optional, Tuple

class DatabaseManager:
    def __init__(self, db_path: str = "notes.cdb"):
        self.db_path = db_path
        self.init_db()

    def _get_connection(self):
        # Increased timeout to 30s to allow for concurrent operations without "database is locked"
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        
        # Performance & Concurrency Tuning
        conn.execute("PRAGMA journal_mode=WAL;") # Write-Ahead Logging allows concurrent readers
        conn.execute("PRAGMA synchronous=NORMAL;") # Faster, slightly less safe than FULL, but standard for desktop apps
        conn.row_factory = sqlite3.Row # Access columns by name (faster C implementation than dict)
        
        return conn

    def init_db(self):
        """Initialize the database tables."""
        conn = self._get_connection()
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
            conn.commit()

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
        
        # Performance Indices
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_parent_title ON notes(parent_id, title);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_note ON images(note_id);")
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
        
        conn.commit()
        conn.close()

    def add_image(self, note_id: int, data: bytes) -> int:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO images (note_id, data) VALUES (?, ?)", (note_id, data))
        image_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return image_id

    def get_image(self, image_id: int) -> Optional[bytes]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT data FROM images WHERE id = ?", (image_id,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None

    def cleanup_images(self, note_id: int, present_ids: list[int]):
        """Delete images belonging to note_id that are NOT in present_ids."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if not present_ids:
            # Delete all images for this note
            cursor.execute("DELETE FROM images WHERE note_id = ?", (note_id,))
        else:
            # Delete images NOT in the list
            placeholders = ','.join(['?'] * len(present_ids))
            query = f"DELETE FROM images WHERE note_id = ? AND id NOT IN ({placeholders})"
            params = [note_id] + present_ids
            cursor.execute(query, params)
            
        conn.commit()
        conn.close()

    def add_attachment(self, note_id: int, filename: str, data: bytes) -> int:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO attachments (note_id, filename, data) VALUES (?, ?, ?)", (note_id, filename, data))
        att_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return att_id

    def get_attachment(self, att_id: int) -> Optional[Tuple[str, bytes]]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT filename, data FROM attachments WHERE id = ?", (att_id,))
        row = cursor.fetchone()
        conn.close()
        return row if row else None

    def cleanup_attachments(self, note_id: int, present_ids: list[int]):
        """Delete attachments belonging to note_id that are NOT in present_ids."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if not present_ids:
            cursor.execute("DELETE FROM attachments WHERE note_id = ?", (note_id,))
        else:
            placeholders = ','.join(['?'] * len(present_ids))
            query = f"DELETE FROM attachments WHERE note_id = ? AND id NOT IN ({placeholders})"
            params = [note_id] + present_ids
            cursor.execute(query, params)
            
        conn.commit()
        conn.close()

    def delete_attachment(self, att_id: int):
        """Delete an attachment by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM attachments WHERE id = ?", (att_id,))
        conn.commit()
        conn.close()

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

    def add_note(self, title: str, parent_id: Optional[int] = None, content: str = "", is_folder: bool = False) -> int:
        """Add a new note and return its ID."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO notes (title, parent_id, content, is_folder) VALUES (?, ?, ?, ?)",
                (title, parent_id, content, 1 if is_folder else 0)
            )
            note_id = cursor.lastrowid
            conn.commit()
            return note_id
        finally:
            conn.close()

    def update_note_title(self, note_id: int, title: str):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE notes SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (title, note_id)
            )
            conn.commit()
        finally:
            conn.close()

    def update_note(self, note_id: int, title: str, content: str):
        """Update a note's title and content."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE notes SET title = ?, content = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (title, content, note_id)
            )
            conn.commit()
        finally:
            conn.close()

    def delete_note(self, note_id: int):
        """Delete a note and its children."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        conn.commit()
        conn.close()

    def get_note(self, note_id: int) -> Optional[Tuple]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM notes WHERE id = ?", (note_id,))
        row = cursor.fetchone()
        conn.close()
        return row

    def get_children(self, parent_id: Optional[int] = None) -> List[Tuple]:
        """Get all notes that are direct children of parent_id."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if parent_id is None:
                cursor.execute("SELECT id, title, is_folder FROM notes WHERE parent_id IS NULL")
            else:
                cursor.execute("SELECT id, title, is_folder FROM notes WHERE parent_id = ?", (parent_id,))
            rows = cursor.fetchall()
            return rows
        finally:
            conn.close()
    
    def move_note_to_parent(self, note_id: int, new_parent_id: Optional[int]):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE notes SET parent_id = ? WHERE id = ?", (new_parent_id, note_id))
        conn.commit()
        conn.close()

    def get_note_by_title(self, title: str) -> Optional[Tuple]:
        """Get the first note matching the given title."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM notes WHERE title = ?", (title,))
        row = cursor.fetchone()
        conn.close()
        return row

    def get_detailed_statistics(self) -> dict:
        """Calculate detailed statistics for the vault."""
        stats = {
            "total_notes": 0,
            "total_subnotes": 0,
            "total_images": 0,
            "total_code_fragments": 0,
            "total_words": 0,
            "total_letters": 0
        }
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 1. Counts
        cursor.execute("SELECT COUNT(*) FROM notes")
        stats["total_notes"] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM notes WHERE parent_id IS NOT NULL")
        stats["total_subnotes"] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM images")
        stats["total_images"] = cursor.fetchone()[0]
        
        # 2. Content Analysis
        cursor.execute("SELECT content FROM notes")
        rows = cursor.fetchall()
        
        import re
        
        for row in rows:
            content = row[0]
            if not content:
                continue
                
            # Count Code Blocks
            # Look for ``` start tags (standard markdown style)
            # Since content is HTML, they might be plain text or wrapped.
            # We search for the pattern.
            code_blocks = len(re.findall(r"```", content))
            # Blocks have start and end, so strictly strictly divisible by 2?
            # Or just count occurrences / 2?
            # Or count "starts"? Text editor logic counts starts.
            # User wants "fragments". 
            # If we assume correctly formatted, ```...``` is one fragment.
            # So occurrences / 2 works if valid.
            # Let's count *starts* approximately (odd occurrences?).
            # Actually, `editor.py` counts starts: txt.startswith("```").
            # But here we act on the whole text.
            # Let's count *pairs*?
            # Ideally: len(re.findall(r"```[\s\S]*?```", content))
            # But simpler: count ``` and integer divide by 2.
            stats["total_code_fragments"] += (code_blocks // 2)

            # Strip HTML for words/letters
            # Remove tags
            text_only = re.sub(r'<[^>]+>', ' ', content)
            
            # Words
            words = text_only.split()
            stats["total_words"] += len(words)
            
            # Letters (non-whitespace)
            # Remove all whitespace from text_only
            letters = re.sub(r'\s+', '', text_only)
            stats["total_letters"] += len(letters)
            
        conn.close()
        return stats

    def get_all_notes(self) -> List[Tuple]:
        """Get all notes for search processing. (Legacy/Backup)"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM notes")
        rows = cursor.fetchall()
        conn.close()
        return rows

    def search_notes_fts(self, query: str) -> List[Tuple]:
        """Search notes using FTS5 match. (Legacy simple prefix search)"""
        # ... existing logic wrapped or reused ...
        sanitized = query.replace('"', '""').strip()
        if not sanitized:
             return []
        fts_query = f'"{sanitized}"*' 
        return self.advanced_search(fts_query)

    def advanced_search(self, fts_query: str) -> List[Tuple]:
        """
        Execute a raw FTS5 query.
        Returns: [(note_id, title, snippet)]
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
             # We use snippet() function for context
             # snippet(table, column_index, start_marker, end_marker, ellipses, max_tokens)
             # Column 2 is content (0=title, 1=content? No, schema: rowid, title, content? FTS table is virtual.)
             # notes_fts columns: title, content.
             # snippet(notes_fts, 1, '<b>', '</b>', '...', 20) -> Snippet of content column
             
             sql = """
                 SELECT rowid, title, snippet(notes_fts, 1, '<b>', '</b>', '...', 15) as snip, rank
                 FROM notes_fts 
                 WHERE notes_fts MATCH ? 
                 ORDER BY rank
             """
             cursor.execute(sql, (fts_query,))
             rows = cursor.fetchall()
             return rows
        except sqlite3.OperationalError as e:
             print(f"FTS Error: {e}")
             return []
        finally:
             conn.close()
