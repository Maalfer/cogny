import sys
import unittest
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QModelIndex
from app.ui.main_window import MainWindow
from app.database.manager import DatabaseManager

# Ensure one app instance
app = QApplication.instance() or QApplication(sys.argv)

class TestNoteApp(unittest.TestCase):
    def setUp(self):
        self.db_path = "test_env_notes.cdb"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
            
        # 1. Initialize Window
        self.window = MainWindow(self.db_path)
        
        # 2. Patch Worker to be Synchronous
        # We replace start() with a method that runs run() immediately in main thread?
        # NoteLoaderWorker run() emits finished signal.
        # But run() does DB IO.
        # Ideally we replace NoteLoaderWorker class on the instance or class.
        
        # Monkey Patch the class inside the method or globally?
        # Better: create a MockWorker that runs synchronously.
        
        original_loader_cls = self.window.NoteLoaderWorker
        
        class SyncLoader(original_loader_cls):
            def start(self, priority=None):
                self.run() # Run synchronously
                
        self.window.NoteLoaderWorker = SyncLoader

    def test_window_title(self):
        self.assertEqual(self.window.windowTitle(), "Cogny")
        
    def test_add_root_note(self):
        # Programmatically call add note logic since QInputDialog blocks
        # We can call model directly or mock the dialog. 
        # For valid integration test, let's call model directly like the dialog would.
        
        self.window.model.add_note("Root Note 1", None)
        
        # Verify in Model
        root = self.window.model.invisibleRootItem()
        self.assertEqual(root.rowCount(), 1)
        item = root.child(0)
        self.assertEqual(item.text(), "Root Note 1")
        
        # Verify in DB
        db = DatabaseManager(self.db_path)
        rows = db.get_children(None)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1], "Root Note 1")
        
    def test_hierarchy_and_content(self):
        # Create Root
        root_id = self.window.model.add_note("Root", None)
        
        # Create Child
        child_id = self.window.model.add_note("Child", root_id)
        
        # Verify Model Structure
        root_item = self.window.model.item(0) # Logic depends on order, but here we have 1
        self.assertEqual(root_item.text(), "Root")
        self.assertEqual(root_item.rowCount(), 1)
        child_item = root_item.child(0)
        self.assertEqual(child_item.text(), "Child")
        
        # Test Selection and Editing
        # Select Child
        index = self.window.model.indexFromItem(child_item)
        proxy_index = self.window.proxy_model.mapFromSource(index)
        self.window.tree_view.setCurrentIndex(proxy_index)
        
        # Check Editor Title (loaded from DB)
        self.assertEqual(self.window.title_edit.toPlainText(), "Child")
        
        # Edit Content
        self.window.text_editor.setPlainText("Hello World")
        self.window.title_edit.setPlainText("Child Renamed")
        
        # Save
        self.window.save_current_note()
        
        # Verify in DB
        db = DatabaseManager(self.db_path)
        note = db.get_note(child_id)
        self.assertEqual(note[2], "Child Renamed")
        # Check that content is HTML (contains tags)
        self.assertIn("<!DOCTYPE HTML", note[3])
        self.assertIn("Hello World", note[3])
        
    def test_image_table_exists(self):
        db = DatabaseManager(self.db_path)
        # Check if table exists by trying to select from it
        # (Empty initially)
        self.assertEqual(len(db.get_children(None)), 0)
        
        # Insert a dummy image
        img_id = db.add_image(1, b"fake_png_data")
        self.assertIsNotNone(img_id)
        
        # Retrieve it
        data = db.get_image(img_id)
        self.assertEqual(data, b"fake_png_data")
        
    def test_image_cleanup_on_save(self):
        # 1. Create Note
        note_id = self.window.model.add_note("Image Note", None)
        self.window.current_note_id = note_id
        
        # 2. Add specific image to DB manually (simulating paste)
        db = DatabaseManager(self.db_path)
        img_id = db.add_image(note_id, b"clean_me")
        
        # 3. Set content WITH image tag
        html_with_img = f'<html><body><img src="image://db/{img_id}" /></body></html>'
        self.window.text_editor.setHtml(html_with_img)
        self.window.save_current_note()
        
        # Verify it still exists
        self.assertIsNotNone(db.get_image(img_id))
        
        # 4. Remove image tag from content
        self.window.text_editor.setHtml("<html><body>No Image</body></html>")
        self.window.save_current_note()
        
        # Verify it is GONE
        self.assertIsNone(db.get_image(img_id))
        
    def test_autosave_on_switch(self):
        # 1. Create two notes
        note1_id = self.window.model.add_note("Note 1", None)
        note2_id = self.window.model.add_note("Note 2", None)
        
        # 2. Select Note 1 and Edit
        # Manually select Note 1
        note1_item = self.window.model.item(0) # Logic assumes 0 is note1
        # To be safe, find items. But assuming order is fine for test.
        # Actually, newly added notes are appended.
        # note1 is at row count-2, note2 at row count-1? 
        # get_children() returns list.
        # Let's rely on manual setting of current_note_id + on_selection_changed trigger simulation for unit test
        
        self.window.current_note_id = note1_id
        self.window.title_edit.setPlainText("Modified Note 1")
        # We need to simulate the editor content change
        self.window.text_editor.setHtml("Modified Content")
        
        # 3. Trigger switch to Note 2
        # We call save_current_note() indirectly? 
        # The feature is "Auto-save on Switch".
        # So we call on_selection_changed(new, old).
        # We need valid indices for that.
        # Let's just verify that IF on_selection_changed is called, it saves.
        
        # Create dummy index for Note 2 using model
        # note2_item ... we need to find it. 
        # Let's iterate model rows.
        root = self.window.model.invisibleRootItem()
        note2_item = None
        for i in range(root.rowCount()):
            it = root.child(i)
            if it.note_id == note2_id:
                note2_item = it
                break
        
        index2 = self.window.model.indexFromItem(note2_item)
        self.window.on_selection_changed(index2, QModelIndex())
        
        # Now Check DB for Note 1
        db = DatabaseManager(self.db_path)
        note1 = db.get_note(note1_id)
        self.assertEqual(note1[2], "Modified Note 1")
        self.assertIn("Modified Content", note1[3])

    def test_delete(self):
        root_id = self.window.model.add_note("To Delete", None)
        
        # Select
        root_item = self.window.model.item(0)
        index = self.window.model.indexFromItem(root_item)
        proxy_index = self.window.proxy_model.mapFromSource(index)
        self.window.tree_view.setCurrentIndex(proxy_index)
        
        # Helper to simulate delete without blocking popup
        # We can mock QMessageBox or just call the logic that triggers delete if we separated it.
        # Logic is inside delete_note().
        # We can monkeypatch QMessageBox.question
        
        from PySide6.QtWidgets import QMessageBox
        original_question = QMessageBox.question
        QMessageBox.question = lambda *args: QMessageBox.Yes
        
        try:
            self.window.delete_note()
        finally:
            QMessageBox.question = original_question
            
        # Verify Gone logic
        self.assertEqual(self.window.model.rowCount(), 0)
        
        db = DatabaseManager(self.db_path)
        self.assertEqual(len(db.get_children(None)), 0)

    def test_theme_manager(self):
        from app.ui.themes import ThemeManager
        from PySide6.QtGui import QPalette
        
        # Test Light Palette
        p_light = ThemeManager.get_palette("Light")
        self.assertIsInstance(p_light, QPalette)
        
        # Test Dark Palette
        p_dark = ThemeManager.get_palette("Dark")
        self.assertNotEqual(p_light.color(QPalette.Window), p_dark.color(QPalette.Window))
        
        # Test Styles
        s_light = ThemeManager.get_editor_style("Light")
        s_dark = ThemeManager.get_editor_style("Dark")
        self.assertIn("#FAFAFA", s_light)
        self.assertIn("#1e1e1e", s_dark)

    def test_attachments(self):
        # 1. Setup Note
        note_id = self.window.model.add_note("Att Note", None)
        self.window.current_note_id = note_id
        
        # 2. Add Attachment via DB directly (simulating UI flow)
        db = DatabaseManager(self.db_path)
        att_id = db.add_attachment(note_id, "test.txt", b"Content")
        self.assertIsNotNone(att_id)
        
        # 3. Simulate Editor Content
        html = f'<a href="attachment://{att_id}">test.txt</a>'
        self.window.text_editor.setHtml(html)
        self.window.save_current_note()
        
        # Verify stored in DB
        res = db.get_attachment(att_id)
        self.assertEqual(res[0], "test.txt")
        self.assertEqual(res[1], b"Content")
        
        # 4. Remove link and Save
        self.window.text_editor.setHtml("")
        self.window.save_current_note()
        
        res_deleted = db.get_attachment(att_id)
        self.assertIsNone(res_deleted)

    def test_obsidian_import(self):
        import shutil
        import tempfile
        from app.importers.obsidian import ObsidianImporter
        
        # 1. Create Mock Vault
        vault_dir = tempfile.mkdtemp()
        try:
            # Folder A
            os.mkdir(os.path.join(vault_dir, "Folder A"))
            
            # Image
            img_path = os.path.join(vault_dir, "test_img.png")
            with open(img_path, 'wb') as f:
                f.write(b"fake_image_bytes")
            
            # Note with Wikilink
            note_path = os.path.join(vault_dir, "Folder A", "Note A.md")
            with open(note_path, 'w') as f:
                f.write("# Header\n\n![[test_img.png]]\n\nText")
            
            # 2. Run Import
            db = DatabaseManager(self.db_path) 
            # (Note: self.window shares same DB path)
            importer = ObsidianImporter(db)
            importer.import_vault(vault_dir)
            
            # 3. Verify
            # Root note "Folder A"
            rows = db.get_children(None)
            # Depending on OS walk order, "Folder A" and "test_img.png" (if filtered out?)
            # Importer ignores non-md files for note creation unless they are folders.
            # "test_img.png" is a file, skipped.
            # "Folder A" is a folder, created.
            
            folder_note = None
            for r in rows:
                if r[1] == "Folder A":
                    folder_note = r
                    break
            self.assertIsNotNone(folder_note)
            
            # Child note "Note A"
            children = db.get_children(folder_note[0])
            self.assertEqual(len(children), 1)
            self.assertEqual(children[0][1], "Note A")
            
            # Content Check
            note_a = db.get_note(children[0][0])
            content = note_a[3]
            self.assertIn('<img src="image://db/', content)
            
            # Check Image Exists
            # Extract ID from content
            import re
            m = re.search(r'src="image://db/(\d+)"', content)
            self.assertIsNotNone(m)
            img_id = int(m.group(1))
            self.assertEqual(db.get_image(img_id), b"fake_image_bytes")

        finally:
            shutil.rmtree(vault_dir)

    def test_obsidian_import_attachments(self):
        """Test importing generic attachments (ZIP, PDF, etc.) from Obsidian."""
        import shutil
        import tempfile
        from app.importers.obsidian import ObsidianImporter
        
        # Create mock vault
        vault_dir = tempfile.mkdtemp()
        try:
            # 1. Create attachment file
            att_dir = os.path.join(vault_dir, "assets")
            os.makedirs(att_dir)
            att_path = os.path.join(att_dir, "data.zip")
            with open(att_path, "wb") as f:
                f.write(b"PK_MOCK_ZIP_DATA")
                
            # 2. Create Note with WikiLink to attachment
            note_path = os.path.join(vault_dir, "Project.md")
            with open(note_path, "w") as f:
                f.write("Here is the file: [[data.zip]]")
                
            # 3. Import
            importer = ObsidianImporter(self.window.text_editor.db) # Access DB via editor or create new manager
            # Wait, self.window doesn't expose DB easily? 
            # MainWindow has self.model.db, text_editor.db
            # Let's use clean DB manager
            db = DatabaseManager(self.db_path)
            importer = ObsidianImporter(db)
            importer.import_vault(vault_dir)
            
            # 4. Verify Note
            note = db.get_note_by_title("Project")
            self.assertIsNotNone(note)
            content = note[3] # content index
            
            # Verify Attachment in DB
            import sqlite3
            conn = sqlite3.connect(db.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT id, filename, data FROM attachments WHERE note_id=?", (note[0],))
            att_row = cursor.fetchone()
            self.assertIsNotNone(att_row, "Attachment not found in DB")
            self.assertEqual(att_row[1], "data.zip")
            self.assertEqual(att_row[2], b"PK_MOCK_ZIP_DATA")
            
            # Verify Content has attachment link
            # Expected: 📎 <a href="attachment://ID">data.zip</a>
            expected_link = f'attachment://{att_row[0]}'
            self.assertIn(expected_link, content)
            self.assertIn("data.zip", content)
            
        finally:
            shutil.rmtree(vault_dir)

    def test_obsidian_import_markdown_structure(self):
        """Test that Markdown structure (Headers, Lists, Code) is preserved."""
        import shutil
        import tempfile
        from app.importers.obsidian import ObsidianImporter
        
        vault_dir = tempfile.mkdtemp()
        try:
            # Create a complex Markdown note
            md_content = """# Main Encabezado
## Subheader
- List item 1
- List item 2

**Bold Text** and *Italic*

```python
print("Hello World")
```
"""
            note_path = os.path.join(vault_dir, "StructureTest.md")
            with open(note_path, "w") as f:
                f.write(md_content)
                
            # Import
            db = DatabaseManager(self.db_path)
            importer = ObsidianImporter(db)
            importer.import_vault(vault_dir)
            
            # Verify
            note = db.get_note_by_title("StructureTest")
            self.assertIsNotNone(note)
            saved_content = note[3]
            
            # Check unmodified elements exist
            self.assertIn("# Main Encabezado", saved_content)
            self.assertIn("## Subheader", saved_content)
            self.assertIn("- List item 1", saved_content)
            self.assertIn("**Bold Text**", saved_content)
            self.assertIn("```python", saved_content)
            self.assertIn('print("Hello World")', saved_content)
            
        finally:
            shutil.rmtree(vault_dir)

    def test_import_whitespace_preservation(self):
        """Test that imported raw markdown preserves indentation when loaded."""
        # 1. Manually insert raw markdown note into DB (simulating import)
        raw_content = "Code:\n\n    def foo():\n        return True"
        note_id = self.window.model.add_note("Whitespace Test", None)
        
        # We must bypass the editor save logic which saves as HTML.
        # Direct DB injection simulating Importer
        db = DatabaseManager(self.db_path)
        db.update_note(note_id, "Whitespace Test", raw_content)
        
        # 2. Select the note in UI
        # Find item
        root = self.window.model.invisibleRootItem()
        # It's likely the last one
        item_found = None
        for i in range(root.rowCount()):
             item = root.child(i)
             if item.note_id == note_id:
                 item_found = item
                 break
        
        self.assertIsNotNone(item_found)
        index = self.window.model.indexFromItem(item_found)
        proxy_index = self.window.proxy_model.mapFromSource(index)
        
        # 3. Trigger Load
        self.window.on_selection_changed(proxy_index, QModelIndex())
        
        # 4. Check Editor Content
        loaded_inv = self.window.text_editor.toPlainText()
        
        # Indentation (4 spaces) must be present
        self.assertIn("    def foo():", loaded_inv)
        self.assertIn("        return True", loaded_inv)

if __name__ == '__main__':
    unittest.main()
