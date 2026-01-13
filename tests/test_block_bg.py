
import sys
from PySide6.QtWidgets import QApplication
from app.ui.editor import NoteEditor
from app.ui.highlighter import MarkdownHighlighter
from app.database.manager import DatabaseManager
from PySide6.QtGui import QColor, QBrush
from PySide6.QtCore import Qt

def test_block_formats():
    # Mock DB
    db = DatabaseManager(":memory:")
    
    if not QApplication.instance():
        app = QApplication(sys.argv)
    else:
        app = QApplication.instance()
        
    editor = NoteEditor(db)
    
    # Inject Highlighter (normally done by MainWindow)
    highlighter = MarkdownHighlighter(editor.document())
    highlighter.set_theme("Dark") # Ensure it has theme
    editor.highlighter = highlighter
    
    # Insert code block
    cursor = editor.textCursor()
    cursor.insertText("Normal Text\n")
    cursor.insertText("```python\nimport os\n```\n")
    cursor.insertText("More Normal Text")
    
    # Apply Dark Theme (Triggers apply_theme -> update_code_block_visuals)
    editor.apply_theme("Dark")
    
    # Process events to allow highlighter to run (queued)
    app.processEvents()
    
    # Force update just in case state wasn't ready
    editor.update_code_block_visuals()
    
    doc = editor.document()
    
    # Block 0: Normal
    b0 = doc.findBlockByNumber(0)
    bg0 = b0.blockFormat().background()
    print(f"Block 0 Style: {bg0.style()} (Expected NoBrush)")
    if bg0.style() != Qt.NoBrush:
        print("FAIL: Normal text has background.")
        return False
    
    # Block 1 start
    b1 = doc.findBlockByNumber(1) # ```python
    print(f"Block 1 text: '{b1.text()}' State: {b1.userState()}")
    
    bg1 = b1.blockFormat().background()
    color1 = bg1.color().name()
    print(f"Block 1 Color: {color1}")
    
    # Dark Theme Background for code: #2d2d2d
    if color1.lower() != "#2d2d2d":
        print(f"FAIL: Expected #2d2d2d, got {color1}")
        return False
        
    # Switch to Light Theme
    editor.highlighter.set_theme("Light") # Manually sync highlighter
    editor.apply_theme("Light")
    
    bg1_light = b1.blockFormat().background()
    color1_light = bg1_light.color().name()
    print(f"Block 1 Light Color: {color1_light}")
    
    # Light Theme Background: #EEF1F4
    if color1_light.lower() != "#eef1f4":
        print(f"FAIL: Theme switch didn't update background. Got {color1_light}")
        return False

    print("SUCCESS")
    return True

if __name__ == "__main__":
    test_block_formats()
