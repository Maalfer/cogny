
import sys
from PySide6.QtWidgets import QApplication
from app.ui.editor import NoteEditor
from app.database.manager import DatabaseManager

class MockDB:
    def get_image(self, iid): return None # Missing image

def test_zoom_broken():
    app = QApplication.instance() or QApplication(sys.argv)
    
    db = MockDB()
    editor = NoteEditor(db)
    editor.show()
    
    # Insert Broken Image
    editor.setHtml('<img src="image://db/999" alt="Broken" />')
    
    app.processEvents()
    
    print("Initial Scale:", getattr(editor, "image_scale", 1.0))
    
    try:
        editor.pageZoomIn()
        print("Zoom In OK")
    except Exception as e:
        print(f"FAIL: Zoom In Error: {e}")
        return False
        
    return True

if __name__ == "__main__":
    if test_zoom_broken():
        sys.exit(0)
    else:
        sys.exit(1)
