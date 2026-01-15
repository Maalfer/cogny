import unittest
import os
import sys
from unittest.mock import MagicMock, patch

# Ensure src is in path if running from root
sys.path.append(os.getcwd())

from app.exporters.pdf_exporter import PDFExporter

class TestPDFExport(unittest.TestCase):
    def setUp(self):
        self.mock_db = MagicMock()
        # Mock get_image to return a valid minimal PNG blob (1x1 red pixel)
        self.png_blob = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT\x08\xd7c\xf8\xcf\xc0\x00\x00\x03\x01\x01\x00\x18\xdd\x8d\xb0\x00\x00\x00\x00IEND\xaeB`\x82'
        self.mock_db.get_image.return_value = self.png_blob
        self.output_path = "tests/test_pdf_output.pdf"

    def tearDown(self):
        if os.path.exists(self.output_path):
            os.remove(self.output_path)

    def test_export_simple_text(self):
        """Verify basic PDF generation works without errors."""
        exporter = PDFExporter(self.mock_db)
        exporter.export_to_pdf("Test Title", "Simple content", self.output_path)
        self.assertTrue(os.path.exists(self.output_path), "PDF file should be created for simple text")

    def test_export_with_image(self):
        """
        Verify that WeasyPrint correctly uses the custom URL fetcher to load images from the DB.
        This adapts the logic from debug_pdf_images.py into a regression test.
        """
        exporter = PDFExporter(self.mock_db)
        
        # Markdown content referring to image ID 123
        # Note: MarkdownRenderer will convert this to HTML <img src="image://db/123">
        content = 'Start Text <img src="image://db/123" /> End Text'
        
        exporter.export_to_pdf("Image Test", content, self.output_path)
        
        # 1. Check file exists
        self.assertTrue(os.path.exists(self.output_path), "PDF file should be created for image content")
        
        # 2. Verify DB interaction
        # If WeasyPrint used the fetcher, it MUST have queried the DB for ID 123.
        # This confirms the integration is working.
        self.mock_db.get_image.assert_called_with(123)

if __name__ == '__main__':
    unittest.main()
