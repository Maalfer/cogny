
import sys
from PySide6.QtWidgets import QApplication
from app.ui.editor import NoteEditor
from app.database.manager import DatabaseManager
from PySide6.QtGui import QImage, QTextCursor

# Mock DB
class MockDB:
    def add_image(self, nid, data): return 1
    def get_image(self, iid): return b'' # Emptiness

def test_zoom_repro():
    app = QApplication.instance() or QApplication(sys.argv)
    
    # Setup
    db = MockDB()
    editor = NoteEditor(db)
    editor.show()
    
    # Insert Complex Content
    cursor = editor.textCursor()
    
    # 1. Image
    cursor.insertText("Image here: ")
    # Insert a dummy image char format manually or use insertFromMime... hard to mock fully without resource loading.
    # But `update_image_sizes` checks `isImageFormat()`.
    # Let's insert an image using standard HTML
    editor.setHtml("""
    <h1>Title</h1>
    <p>Text</p>
    <img src="image://db/1" width="600" />
    <table border="1">
       <tr><td>Cell 1</td><td>Cell 2</td></tr>
       <tr><td><img src="image://db/1" /></td><td>Text</td></tr>
    </table>
    <pre><code>
    Code Block
    </code></pre>
    <ul><li>List item</li></ul>
    """)
    
    # Force layout update
    app.processEvents()
    
    print("Initial Scale:", getattr(editor, "image_scale", 1.0))
    
    # Try Zoom
    print("Zooming In...")
    try:
        editor.pageZoomIn()
    except Exception as e:
        print(f"FAIL: Exception during Zoom In: {e}")
        return False
        
    print("New Scale:", getattr(editor, "image_scale", 1.0))
    if getattr(editor, "image_scale", 1.0) <= 1.0:
        print("FAIL: Scale did not increase.")
        return False
        
    # Check if image sizes changed?
    # We'd need to inspect the document.
    
    # Try Zoom Out
    print("Zooming Out...")
    try:
        editor.pageZoomOut()
    except Exception as e:
        print(f"FAIL: Exception during Zoom Out: {e}")
        return False
        
    print("SUCCESS: Zoom calls completed without crash.")
    return True

if __name__ == "__main__":
    if test_zoom_repro():
        sys.exit(0)
    else:
        sys.exit(1)
