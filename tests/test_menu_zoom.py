
import sys
import os
import tempfile
from PySide6.QtWidgets import QApplication
from app.ui.main_window import MainWindow
from app.database.manager import DatabaseManager

def test_menu_zoom():
    if not QApplication.instance():
        app = QApplication(sys.argv)
    else:
        app = QApplication.instance()
        
    # Use temp file for DB to ensure persistence across connections
    # (Since DatabaseManager opens/closes connections, :memory: is lost)
    fd, db_path = tempfile.mkstemp(suffix=".cdb")
    os.close(fd)
    
    # try:
    window = MainWindow(db_path)
    window.show()
    
    editor = window.text_editor
    
    # 1. Initial State
    initial_size = editor.font().pointSize()
    print(f"Initial Size: {initial_size}")
    
    # 2. Check Actions Existence
    if not hasattr(window, "act_zoom_in"):
        print("FAIL: act_zoom_in missing")
        return False
        
    # 3. Simulate Trigger Zoom In
    print("--- Triggering Zoom In ---")
    window.act_zoom_in.trigger()
    app.processEvents()
    
    size_after_zoom_in = editor.font().pointSize()
    print(f"After Zoom In: {size_after_zoom_in}")
    
    if size_after_zoom_in <= initial_size:
        print("FAIL: Zoom In action did not increase font size.")
        return False
        
    # 4. Simulate Trigger Zoom Out
    print("--- Triggering Zoom Out ---")
    window.act_zoom_out.trigger()
    app.processEvents()
    
    size_after_zoom_out = editor.font().pointSize()
    print(f"After Zoom Out: {size_after_zoom_out}")
    
    if size_after_zoom_out >= size_after_zoom_in:
        print("FAIL: Zoom Out action did not decrease font size.")
        return False

    if os.path.exists(db_path):
        os.remove(db_path)
        
    print("SUCCESS: Menu actions control zoom.")
    return True

if __name__ == "__main__":
    if test_menu_zoom():
        sys.exit(0)
    else:
        sys.exit(1)
