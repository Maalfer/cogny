
import sys
from PySide6.QtWidgets import QApplication
from app.ui.editor import NoteEditor
from app.database.manager import DatabaseManager

def test_margins():
    # Mock DB
    db = DatabaseManager("test.cdb")
    
    app = QApplication.instance() or QApplication(sys.argv)
    
    editor = NoteEditor(db)
    editor.apply_theme("Dark")
    
    doc = editor.document()
    root_frame = doc.rootFrame()
    fmt = root_frame.frameFormat()
    
    margin_left = fmt.leftMargin()
    print(f"Left Margin: {margin_left}")
    
    if margin_left == 60:
        print("SUCCESS: Native margin applied.")
        return True
    else:
        print(f"FAIL: Expected 60, got {margin_left}")
        return False

if __name__ == "__main__":
    test_margins()
