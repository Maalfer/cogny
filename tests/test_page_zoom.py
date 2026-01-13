
import sys
import os
import tempfile
from PySide6.QtWidgets import QApplication
from app.ui.main_window import MainWindow
from PySide6.QtGui import QTextCursor, QTextDocument

def test_page_zoom_full():
    if not QApplication.instance():
        app = QApplication(sys.argv)
    else:
        app = QApplication.instance()
        
    fd, db_path = tempfile.mkstemp(suffix=".cdb")
    os.close(fd)
    
    try:
        window = MainWindow(db_path)
        window.show()
        
        editor = window.text_editor
        
        # 1. Insert Image
        # We need a valid image in DB or just insert an image with local URL?
        # The logic relies solely on isImageFormat().
        # It doesn't strictly need the image to LOAD successfully visually, just format existence.
        # But let's try to be clean.
        
        editor.textCursor().insertHtml('<img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUAAAAFCAYAAACNbyblAAAAHElEQVQI12P4//8/w38GIAXDIBKE0DHxgljNBAAO9TXL0Y4OHwAAAABJRU5ErkJggg==" width="600" />')
        app.processEvents()
        
        # 2. Check Initial Format
        doc = editor.document()
        cursor = QTextCursor(doc)
        cursor.movePosition(QTextCursor.Start)
        cursor.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor)
        fmt = cursor.charFormat()
        
        if not fmt.isImageFormat():
            print("FAIL: Image not inserted.")
            return False
            
        initial_width = fmt.toImageFormat().width()
        print(f"Initial Width: {initial_width}")
        
        # 3. Trigger Page Zoom In
        print("--- Triggering Page Zoom In ---")
        window.act_page_zoom_in.trigger()
        app.processEvents()
        
        # 4. Check New Width
        cursor.movePosition(QTextCursor.Start)
        cursor.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor)
        fmt_new = cursor.charFormat()
        new_width = fmt_new.toImageFormat().width()
        print(f"New Width: {new_width}")
        
        # Expected: 600 * 1.1 = 660
        if new_width > 600:
            print("SUCCESS: Image scaled up.")
            return True
        else:
            print(f"FAIL: Image width did not increase. Got {new_width}")
            return False
            
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)

if __name__ == "__main__":
    if test_page_zoom_full():
        sys.exit(0)
    else:
        sys.exit(1)
