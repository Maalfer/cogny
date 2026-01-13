
import sys
from PySide6.QtWidgets import QApplication
from app.ui.editor import NoteEditor
from app.database.manager import DatabaseManager
from app.ui.themes import ThemeManager

def test_layout_composition():
    if not QApplication.instance():
        app = QApplication(sys.argv)
    else:
        app = QApplication.instance()
        
    db = DatabaseManager(":memory:")
    editor = NoteEditor(db)
    
    # 1. Check Dynamic Margins (Centering)
    editor.resize(1000, 800)
    editor.update_margins()
    
    # Max width 900. 1000 - 900 = 100. Split in 2 = 50.
    vp_margins = editor.viewportMargins()
    print(f"Viewport Margins: {vp_margins.left()}")
    
    if vp_margins.left() != 50:
        print(f"FAIL: Centering margin incorrect. Got {vp_margins.left()}")
        return False
        
    # 2. Check CSS Padding (Internal Spacing)
    # We can't check CSS application easily on a widget without rendering, 
    # but we can check if it's in the style sheet string.
    
    style = ThemeManager.get_editor_style("Dark")
    if "padding-left: 60px;" in style:
        print("CSS Padding: Present")
    else:
        print("FAIL: CSS Padding missing.")
        return False

    print("SUCCESS: Layout composition correct (Centering + Padding).")
    return True

if __name__ == "__main__":
    if test_layout_composition():
        sys.exit(0)
    else:
        sys.exit(1)
