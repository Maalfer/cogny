import sqlite3
import os
import time
from typing import List, Dict, Optional, Tuple

class MetadataCache:
    """
    Manages a local SQLite database for caching vault metadata and Full-Text Search.
    Located at <vault_root>/.cogny/vault.db
    """
    
    def __init__(self, vault_path: str):
        self.vault_path = vault_path
        self.cogny_dir = os.path.join(vault_path, ".cogny")
        self.db_path = os.path.join(self.cogny_dir, "vault.db")
        self.conn = None
        
        self.ensure_cogny_dir()
        self.init_db()

    def ensure_cogny_dir(self):
        if not os.path.exists(self.cogny_dir):
            os.makedirs(self.cogny_dir, exist_ok=True)
            # Create a .gitignore to ignore the db if git is initialized
            gitignore_path = os.path.join(self.cogny_dir, ".gitignore")
            if not os.path.exists(gitignore_path):
                with open(gitignore_path, "w") as f:
                    f.write("*\n")

    def init_db(self):
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        
        cursor = self.conn.cursor()
        
        # 1. Files Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rel_path TEXT UNIQUE NOT NULL,
                mtime REAL,
                size INTEGER
            )
        """)
        
        # 2. Links Table (WikiLinks, Markdown Links)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_file_id INTEGER,
                target_path TEXT,
                link_type TEXT, -- 'wikilink' or 'markdown'
                line INTEGER,
                FOREIGN KEY(source_file_id) REFERENCES files(id) ON DELETE CASCADE
            )
        """)
        
        # 3. Tags Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER,
                tag TEXT,
                line INTEGER,
                FOREIGN KEY(file_id) REFERENCES files(id) ON DELETE CASCADE
            )
        """)
        
        # 4. Frontmatter Table (YAML Properties)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS frontmatter (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER,
                key TEXT,
                value TEXT,
                FOREIGN KEY(file_id) REFERENCES files(id) ON DELETE CASCADE
            )
        """)

        # 5. Headers Table (Structure)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS headers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER,
                level INTEGER,
                text TEXT,
                line INTEGER,
                FOREIGN KEY(file_id) REFERENCES files(id) ON DELETE CASCADE
            )
        """)

        # 6. Full Text Search (FTS5)
        # Check if FTS5 is supported (usually yes in standard Python builds)
        try:
            cursor.execute("CREATE VIRTUAL TABLE IF NOT EXISTS fts_content USING fts5(file_id UNINDEXED, content, title)")
        except Exception as e:
            print(f"Warning: FTS5 not supported, full-text search might be limited. Error: {e}")

        # Indices for Performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_path ON files(rel_path)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_links_target ON links(target_path)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tags_tag ON tags(tag)")

        self.conn.commit()

    def close(self):
        if self.conn:
            self.conn.close()

    # --- CRUD Operations ---

    def upsert_file(self, rel_path: str, mtime: float, size: int) -> int:
        """Insert or Update file record. Returns file_id."""
        cursor = self.conn.cursor()
        try:
            cursor.execute("INSERT INTO files (rel_path, mtime, size) VALUES (?, ?, ?) ON CONFLICT(rel_path) DO UPDATE SET mtime=?, size=?", 
                           (rel_path, mtime, size, mtime, size))
            file_id = cursor.lastrowid
            if file_id == 0: # If updated, lastrowid might be 0 involved depending on sqlite ver, fetch it
                cursor.execute("SELECT id FROM files WHERE rel_path=?", (rel_path,))
                file_id = cursor.fetchone()['id']
            
            # Clear old metadata for this file to prepare for re-indexing
            self._clear_file_metadata(cursor, file_id)
            self.conn.commit()
            return file_id
        except Exception as e:
            print(f"Error upserting file {rel_path}: {e}")
            return None

    def _clear_file_metadata(self, cursor, file_id: int):
        cursor.execute("DELETE FROM links WHERE source_file_id=?", (file_id,))
        cursor.execute("DELETE FROM tags WHERE file_id=?", (file_id,))
        cursor.execute("DELETE FROM frontmatter WHERE file_id=?", (file_id,))
        cursor.execute("DELETE FROM headers WHERE file_id=?", (file_id,))
        try:
            cursor.execute("DELETE FROM fts_content WHERE file_id=?", (file_id,))
        except: pass

    def remove_file(self, rel_path: str):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM files WHERE rel_path=?", (rel_path,))
        row = cursor.fetchone()
        if row:
            file_id = row['id']
            # Cascading deletes might handle this if PRAGMA foreign_keys=ON usually, 
            # but standard sqlite python might not enable it by default.
            # Explicit deletion is safer.
            self._clear_file_metadata(cursor, file_id)
            cursor.execute("DELETE FROM files WHERE id=?", (file_id,))
            self.conn.commit()

    def add_links(self, file_id: int, links: List[Tuple[str, str, int]]):
        """links: list of (target_path, type, line)"""
        if not links: return
        cursor = self.conn.cursor()
        cursor.executemany("INSERT INTO links (source_file_id, target_path, link_type, line) VALUES (?, ?, ?, ?)",
                           [(file_id, t, ltype, line) for t, ltype, line in links])
        self.conn.commit()

    def add_tags(self, file_id: int, tags: List[Tuple[str, int]]):
        """tags: list of (tag, line)"""
        if not tags: return
        cursor = self.conn.cursor()
        cursor.executemany("INSERT INTO tags (file_id, tag, line) VALUES (?, ?, ?)",
                           [(file_id, tag, line) for tag, line in tags])
        self.conn.commit()
    
    def add_frontmatter(self, file_id: int, fm_data: Dict[str, str]):
        if not fm_data: return
        cursor = self.conn.cursor()
        cursor.executemany("INSERT INTO frontmatter (file_id, key, value) VALUES (?, ?, ?)",
                           [(file_id, k, str(v)) for k, v in fm_data.items()])
        self.conn.commit()
        
    def add_headers(self, file_id: int, headers: List[Tuple[int, str, int]]):
        """headers: list of (level, text, line)"""
        if not headers: return
        cursor = self.conn.cursor()
        cursor.executemany("INSERT INTO headers (file_id, level, text, line) VALUES (?, ?, ?, ?)",
                           [(file_id, level, text, line) for level, text, line in headers])
        self.conn.commit()

    def update_fts(self, file_id: int, title: str, content: str):
        cursor = self.conn.cursor()
        try:
            cursor.execute("INSERT INTO fts_content (file_id, title, content) VALUES (?, ?, ?)", (file_id, title, content))
            self.conn.commit()
        except Exception as e:
            print(f"Error updating FTS: {e}")

    # --- Query Operations ---

    def get_file_id(self, rel_path: str) -> Optional[int]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM files WHERE rel_path=?", (rel_path,))
        row = cursor.fetchone()
        return row['id'] if row else None

    def get_all_files(self) -> Dict[str, float]:
        """Returns dict {rel_path: mtime} for all indexed files."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT rel_path, mtime FROM files")
        return {row['rel_path']: row['mtime'] for row in cursor.fetchall()}

    def search_text(self, query: str) -> List[Dict]:
        """Full text search returning list of {path, title, snippet}."""
        cursor = self.conn.cursor()
        try:
            # Using snippet() function from FTS5
            cursor.execute("""
                SELECT f.rel_path, fts.title, snippet(fts_content, 1, '<b>', '</b>', '...', 10) as snippet
                FROM fts_content fts
                JOIN files f ON f.id = fts.file_id
                WHERE fts_content MATCH ?
                ORDER BY rank
                LIMIT 50
            """, (query,))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'path': row['rel_path'],
                    'title': row['title'],
                    'snippet': row['snippet']
                })
            return results
        except Exception as e:
            print(f"Search error: {e}")
            return []
