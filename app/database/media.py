from typing import Optional, Tuple
import contextlib
import os
import uuid

class MediaMixin:
    def add_image(self, note_id: int, data: bytes) -> int:
        # Side-effect: Write to Vault
        if hasattr(self, 'vault_path') and self.vault_path:
            images_dir = os.path.join(self.vault_path, "images")
            # Generate a consistent name? Or random? 
            # Obsidian uses pasted-image-timestamp usually. We'll use UUID for safety.
            filename = f"{uuid.uuid4()}.png"
            file_path = os.path.join(images_dir, filename)
            try:
                with open(file_path, "wb") as f:
                    f.write(data)
            except Exception as e:
                print(f"Failed to write image to vault: {e}")

        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO images (note_id, data) VALUES (?, ?)", (note_id, data))
            return cursor.lastrowid

    def get_image(self, image_id: int) -> Optional[bytes]:
        with contextlib.closing(self._get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT data FROM images WHERE id = ?", (image_id,))
            row = cursor.fetchone()
            return row[0] if row else None

    def cleanup_images(self, note_id: int, present_ids: list[int]):
        """Delete images belonging to note_id that are NOT in present_ids."""
        with self.transaction() as conn:
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

    def add_attachment(self, note_id: int, filename: str, data: bytes) -> int:
        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO attachments (note_id, filename, data) VALUES (?, ?, ?)", (note_id, filename, data))
            return cursor.lastrowid

    def get_attachment(self, att_id: int) -> Optional[Tuple[str, bytes]]:
        with contextlib.closing(self._get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT filename, data FROM attachments WHERE id = ?", (att_id,))
            row = cursor.fetchone()
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
