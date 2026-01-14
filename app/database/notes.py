from typing import List, Optional, Tuple
import contextlib

class NotesMixin:
    def add_note(self, title: str, parent_id: Optional[int] = None, content: str = "", is_folder: bool = False) -> int:
        """Add a new note and return its ID."""
        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO notes (title, parent_id, content, is_folder) VALUES (?, ?, ?, ?)",
                (title, parent_id, content, 1 if is_folder else 0)
            )
            return cursor.lastrowid

    def update_note_title(self, note_id: int, title: str):
        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE notes SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (title, note_id)
            )

    def update_note(self, note_id: int, title: str, content: str):
        """Update a note's title and content."""
        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE notes SET title = ?, content = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (title, content, note_id)
            )

    def delete_note(self, note_id: int):
        """Delete a note and its children."""
        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.execute("DELETE FROM notes WHERE id = ?", (note_id,))

    def get_note(self, note_id: int) -> Optional[Tuple]:
        with contextlib.closing(self._get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM notes WHERE id = ?", (note_id,))
            row = cursor.fetchone()
            return row

    def get_children(self, parent_id: Optional[int] = None) -> List[Tuple]:
        """Get all notes that are direct children of parent_id."""
        with contextlib.closing(self._get_connection()) as conn:
            cursor = conn.cursor()
            if parent_id is None:
                cursor.execute("SELECT id, title, is_folder FROM notes WHERE parent_id IS NULL")
            else:
                cursor.execute("SELECT id, title, is_folder FROM notes WHERE parent_id = ?", (parent_id,))
            rows = cursor.fetchall()
            return rows
    
    def move_note_to_parent(self, note_id: int, new_parent_id: Optional[int]):
        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE notes SET parent_id = ? WHERE id = ?", (new_parent_id, note_id))

    def get_note_by_title(self, title: str) -> Optional[Tuple]:
        """Get the first note matching the given title."""
        with contextlib.closing(self._get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM notes WHERE title = ?", (title,))
            row = cursor.fetchone()
            return row

    def get_all_notes(self) -> List[Tuple]:
        """Get all notes for search processing. (Legacy/Backup)"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM notes")
        rows = cursor.fetchall()
        conn.close()
        return rows
