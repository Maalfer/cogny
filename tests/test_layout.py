
import sys
from PySide6.QtWidgets import QApplication
from app.ui.editor import NoteEditor
from app.database.manager import DatabaseManager

def test_centered_layout():
    if not QApplication.instance():
        app = QApplication(sys.argv)
    else:
        app = QApplication.instance()
        
    db = DatabaseManager(":memory:")
    editor = NoteEditor(db)
    
    # Text Large Window (1200px)
    editor.resize(1200, 800)
    editor.update_margins()
    
    margins = editor.viewportMargins()
    print(f"Window 1200px -> Left Margin: {margins.left()}, Right Margin: {margins.right()}")
    
    # Expected: (1200 - 900) / 2 = 150
    if margins.left() != 150:
        print(f"FAIL: Expected 150 margin for 1200px width, got {margins.left()}")
        return False
        
    # Test Small Window (800px)
    editor.resize(800, 600)
    editor.update_margins()
    
    margins_small = editor.viewportMargins()
    print(f"Window 800px -> Left Margin: {margins_small.left()}")
    
    # Expected: Small padding (30)
    if margins_small.left() != 30:
        print(f"FAIL: Expected 30 margin for 800px width, got {margins_small.left()}")
        return False

    print("SUCCESS: Dynamic margins working.")
    return True

if __name__ == "__main__":
    if test_centered_layout():
        sys.exit(0)
    else:
        sys.exit(1)
