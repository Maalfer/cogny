from typing import List, Optional, Tuple
import contextlib
import os
import re

class NotesMixin:
    def add_note(self, title: str, parent_id: Optional[int] = None, content: str = "", is_folder: bool = False) -> int:
        """Add a new note and return its ID."""
        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO notes (title, parent_id, content, is_folder) VALUES (?, ?, ?, ?)",
                (title, parent_id, content, 1 if is_folder else 0)
            )
            note_id = cursor.lastrowid
        
        # Side-effect: Save to file
        if not is_folder:
            self._save_note_to_file(title, content)
            
        return note_id

    def _save_note_to_file(self, title: str, content: str):
        if hasattr(self, 'vault_path') and self.vault_path:
            # Sanitize filename
            safe_title = "".join([c for c in title if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).strip()
            if not safe_title:
                safe_title = "Untitled"
            
            file_path = os.path.join(self.vault_path, f"{safe_title}.md")
            
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
            except Exception as e:
                print(f"Failed to save note to file: {e}")

    def update_note_title(self, note_id: int, title: str):
        # Todo: Handle renaming the file on disk? 
        # For now, just save the new file (duplicates old one) or ignore?
        # Better: get old title, rename. But that requires extra query. 
        # For simplicity in this iteration: Save new file.
        
        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE notes SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (title, note_id)
            )
        
        # We need content to save full file.
        content = self.get_note_content(note_id)
        if content is not None:
             self._save_note_to_file(title, content)

    def update_note(self, note_id: int, title: str, content: str, cached_html: str = None):
        """Update a note's title, content, and render cache."""
        with self.transaction() as conn:
            cursor = conn.cursor()
            if cached_html is not None:
                cursor.execute(
                    "UPDATE notes SET title = ?, content = ?, cached_html = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (title, content, cached_html, note_id)
                )
            else:
                 cursor.execute(
                    "UPDATE notes SET title = ?, content = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (title, content, note_id)
                )
        
        self._save_note_to_file(title, content)

    def delete_note(self, note_id: int):
        """Delete a note and its children."""
        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.execute("DELETE FROM notes WHERE id = ?", (note_id,))

    def get_note(self, note_id: int) -> Optional[Tuple]:
        return self.fetch_one("SELECT * FROM notes WHERE id = ?", (note_id,))

    def get_note_metadata(self, note_id: int) -> Optional[Tuple]:
        """Get note info without heavy content."""
        return self.fetch_one("SELECT id, title, is_folder, parent_id FROM notes WHERE id = ?", (note_id,))

    def get_note_content(self, note_id: int) -> Optional[str]:
        """Get only the content of a note."""
        row = self.fetch_one("SELECT content FROM notes WHERE id = ?", (note_id,))
        return row['content'] if row else None

    def get_note_cache(self, note_id: int) -> Optional[str]:
        """Get the cached HTML of a note."""
        row = self.fetch_one("SELECT cached_html FROM notes WHERE id = ?", (note_id,))
        return row['cached_html'] if row else None

    def get_children(self, parent_id: Optional[int] = None) -> List[Tuple]:
        """Get all notes that are direct children of parent_id."""
        if parent_id is None:
            return self.fetch_all("SELECT id, title, is_folder FROM notes WHERE parent_id IS NULL")
        else:
            return self.fetch_all("SELECT id, title, is_folder FROM notes WHERE parent_id = ?", (parent_id,))
    
    def move_note_to_parent(self, note_id: int, new_parent_id: Optional[int]):
        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE notes SET parent_id = ? WHERE id = ?", (new_parent_id, note_id))

    def get_note_by_title(self, title: str) -> Optional[Tuple]:
        """Get the first note matching the given title."""
        return self.fetch_one("SELECT * FROM notes WHERE title = ?", (title,))

    def get_all_notes(self) -> List[Tuple]:
        """Get all notes for search processing. (Legacy/Backup)"""
        return self.fetch_all("SELECT * FROM notes")

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
        return self.fetch_all("""
            SELECT id, title, updated_at 
            FROM notes 
            WHERE is_read_later = 1 
            ORDER BY updated_at DESC
        """)

    def update_note_cache(self, note_id: int, cached_html: str):
        """Update only the cached HTML of a note."""
        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE notes SET cached_html = ? WHERE id = ?",
                (cached_html, note_id)
            )
