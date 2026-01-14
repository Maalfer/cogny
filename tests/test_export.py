import unittest
import os
import shutil
import tempfile
import sqlite3
from app.database.manager import DatabaseManager
from app.exporters.obsidian_exporter import ObsidianExporter

class TestObsidianExport(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_notes.cdb")
        self.export_path = os.path.join(self.test_dir, "export_output")
        self.db = DatabaseManager(self.db_path)
        self.exporter = ObsidianExporter(self.db)

    def tearDown(self):
        self.db._get_connection().close()
        shutil.rmtree(self.test_dir)

    def test_export_structure_and_images(self):
        # 1. Setup Data
        # Root Note
        root_id = self.db.add_note("Root Note", None, "Root Content")
        
        # Clean Image (dummy bytes)
        img_data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        img_id = self.db.add_image(root_id, img_data)
        
        # Note with Image
        # Note: Content uses HTML tag for image as per importer/exporter logic
        img_tag = f'<img src="image://db/{img_id}" />'
        child_content = f"Has Image: {img_tag}"
        self.db.add_note("Child with Image", root_id, child_content)
        
        # Folder Note (Empty content, has children)
        folder_id = self.db.add_note("Folder", root_id, "")
        self.db.add_note("Inside Folder", folder_id, "Nested Content")

        # 2. Run Export
        self.exporter.export_vault(self.export_path)

        # 3. Verify Structure
        # Check Images Dir
        img_file = os.path.join(self.export_path, "images", f"image_{img_id}.png")
        self.assertTrue(os.path.exists(img_file), "Image file should ensure exist")
        
        # Check Root Note
        root_file = os.path.join(self.export_path, "Root Note.md")
        self.assertTrue(os.path.exists(root_file))
        
        # Check Folder structure
        # "Root Note" had children ("Child with Image", "Folder") -> So "Root Note" is a folder too?
        # Wait, if "Root Note" has children, logic makes a folder "Root Note" AND a file "Root Note.md" side-by-side?
        # My logic: 
        # Iterate root children: "Root Note" (id=1). 
        # "Root Note" has children (id=2, id=3).
        # -> Create Folder "export/Root Note"
        # -> Create File "export/Root Note.md"
        # -> Recurse into "Root Note" folder.
        
        # Checking "Child with Image" (id=2)
        # It is inside "Root Note" folder.
        child_file = os.path.join(self.export_path, "Root Note", "Child with Image.md")
        self.assertTrue(os.path.exists(child_file), f"File should be at {child_file}")
        
        with open(child_file, 'r') as f:
            content = f.read()
            # Verify Image Link
            # Relative path: Child is in "Root Note/", Image is in "images/"
            # Path should be "../images/image_{id}.png"
            expected_link = f"![image_{img_id}.png](../images/image_{img_id}.png)"
            self.assertIn(expected_link, content)
            
        # Check "Folder" (id=3)
        # It is inside "Root Note". It has children (id=4). Content empty.
        # Should result in Directory "Root Note/Folder".
        # Should NOT result in "Root Note/Folder.md" because content is empty.
        folder_path = os.path.join(self.export_path, "Root Note", "Folder")
        self.assertTrue(os.path.isdir(folder_path))
        self.assertFalse(os.path.exists(folder_path + ".md"))
        
        # Check "Inside Folder" (id=4)
        nested_file = os.path.join(folder_path, "Inside Folder.md")
        self.assertTrue(os.path.exists(nested_file))

if __name__ == '__main__':
    unittest.main()
