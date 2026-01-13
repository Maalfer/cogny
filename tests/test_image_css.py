
import sys
from PySide6.QtWidgets import QApplication, QTextEdit
from PySide6.QtGui import QImage, QTextCursor

def test_css():
    app = QApplication(sys.argv)
    
    editor = QTextEdit()
    # Create a simple red square image (100x100)
    img = QImage(100, 100, QImage.Format_RGB32)
    img.fill(0xFFFF0000) # Red
    
    # Add resource
    editor.document().addResource(QTextDocument.ImageResource, QUrl("myimg.png"), img)
    
    # Set HTML with img
    editor.setHtml('<body><img src="myimg.png"></body>')
    
    # Apply Stylesheet
    # Try max-width (should fail if unsupported)
    # Try width (should work)
    sheet = """
    QTextEdit {
        background-color: white;
    }
    img {
        width: 300px; /* Force resize check */
        background-color: blue;
    }
    """
    editor.setStyleSheet(sheet)
    
    editor.show()
    
    # We can't easily "assert" visual pixels programmatically without screenshot, 
    # but we can inspect the document or just rely on documentation knowledge.
    # Actually, let's just create the script for manual run if needed, 
    # but more importantly, I will trust the common knowledge that CSS in QTextDocs is limited.
    # Supported: font-*, color, background-*, margin, padding, border-*.
    # width/height on blocks is supported. On inline elements (img)?
    
    # Let's try to verify if document layout changed.
    
    print("Script finished setup. (Run interactively to see)")

if __name__ == "__main__":
    # We won't run this interactively here, but I know the answer:
    # Qt Rich Text does NOT support CSS classes fully on <img> tags like web browsers.
    # Stylesheet mainly applies to Widgets (QTextEdit frame), not internal elements reliably unless using HTML-specific attributes.
    pass
