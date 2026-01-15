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

    def toggle_read_later(self, note_id: int) -> bool:
        """
        Toggle the is_read_later flag for a note.
        Returns the new state (True/False).
        """
        with self.transaction() as conn:
            cursor = conn.cursor()
            # Get current state
            cursor.execute("SELECT is_read_later FROM notes WHERE id = ?", (note_id,))
            row = cursor.fetchone()
            if not row:
                return False
            
            # Since column might be NULL in old rows if we didn't defaulting Update, 
            # treat None as False.
            current_state = bool(row[0])
            new_state = not current_state
            
            cursor.execute(
                "UPDATE notes SET is_read_later = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (1 if new_state else 0, note_id)
            )
            return new_state

    def get_read_later_notes(self) -> List[Tuple]:
        """Get all notes marked for reading later."""
        with contextlib.closing(self._get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, title, updated_at 
                FROM notes 
                WHERE is_read_later = 1 
                ORDER BY updated_at DESC
            """)
            return cursor.fetchall()
