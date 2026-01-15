import unittest
import os
import sys
import shutil
import zipfile
from unittest.mock import MagicMock

sys.path.append(os.getcwd())

from app.exporters.export_varios_pdf import MultiPDFExporter

class TestMultiPDFExport(unittest.TestCase):
    def setUp(self):
        self.mock_db = MagicMock()
        # Mocking get_note to return dummy content
        self.mock_db.get_note.side_effect = lambda note_id: {
            'title': f"Note_{note_id}", 
            'content': f"# Content for {note_id}"
        }
        
        # Mocking get_image (used by PDFExporter) to return dummy blob
        self.mock_db.get_image.return_value = b"fake_image_data"
        
        self.zip_path = "tests/test_multi_export.zip"

    def tearDown(self):
        if os.path.exists(self.zip_path):
            os.remove(self.zip_path)

    def test_multi_export_zip_structure(self):
        """Verify that MultiPDFExporter creates a valid ZIP with correct PDFs."""
        
        # Mock single_exporter to avoid actual PDF generation (slow/needs GUI deps potentially)
        # BUT we want to verifying integration.
        # However, running WeasyPrint headless IS supported.
        # So we can keep it real or mock it.
        # Let's keep it REAL for robust testing, assuming WeasyPrint works (verified in previous test).
        
        exporter = MultiPDFExporter(self.mock_db)
        
        notes_to_export = [
            (1, "Note One"),
            (100, "Note_Two"),  # Underscore name
            (99, "Note/Three") # Slash in name (should be sanitized)
        ]
        
        # Run Export
        success = exporter.export_multiple(notes_to_export, self.zip_path)
        
        self.assertTrue(success, "Export should return True")
        self.assertTrue(os.path.exists(self.zip_path), "ZIP file must exist")
        
        # Verify ZIP contents
        with zipfile.ZipFile(self.zip_path, 'r') as zf:
            file_names = zf.namelist()
            print(f"ZIP Contents: {file_names}")
            
            self.assertEqual(len(file_names), 3, "Should contain 3 PDF files")
            
            self.assertIn("Note One.pdf", file_names)
            self.assertIn("Note_Two.pdf", file_names)
            # "Note/Three" -> "NoteThree" or similar sanitization
            # My logic: "".join([c for c in title if c.isalpha() or c.isdigit() or c in (' ', '.', '-', '_')])
            # "Note/Three" -> "NoteThree" (slash removed)
            self.assertIn("NoteThree.pdf", file_names)

if __name__ == '__main__':
    unittest.main()
