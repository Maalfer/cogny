
import sys
import os
import unittest
from unittest.mock import MagicMock

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtWidgets import QApplication
from app.exporters.pdf_exporter import PDFExporter

# Ensure QApplication exists
app = QApplication.instance() or QApplication(sys.argv)

class TestPDFExportManual(unittest.TestCase):
    def setUp(self):
        self.db_mock = MagicMock()
        self.db_mock.get_image.return_value = None # No images for this test
        self.exporter = PDFExporter(self.db_mock)
        self.output_path = "test_export.pdf"
        
    def tearDown(self):
        if os.path.exists(self.output_path):
            os.remove(self.output_path)

    def test_export_complex_content(self):
        content = """
# Test Title

This is a **bold** text and *italic* text.

```python
def hello_world():
    print("Hello World")
```

| Header 1 | Header 2 |
|----------|----------|
| Cell 1   | Cell 2   |
        """
        
        print("Starting Export...")
        self.exporter.export_to_pdf("Test Note", content, self.output_path, theme_name="Dark")
        
        self.assertTrue(os.path.exists(self.output_path))
        size = os.path.getsize(self.output_path)
        print(f"Exported PDF size: {size} bytes")
        self.assertGreater(size, 0)
        print("Export Successful!")

if __name__ == "__main__":
    unittest.main()
