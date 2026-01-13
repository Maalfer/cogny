
import sys
from PySide6.QtWidgets import QApplication
from app.ui.editor import NoteEditor
from app.ui.highlighter import MarkdownHighlighter
from app.database.manager import DatabaseManager
from PySide6.QtGui import QColor, QBrush
from PySide6.QtCore import Qt

def test_clean_backgrounds():
    db = DatabaseManager(":memory:")
    
    if not QApplication.instance():
        app = QApplication(sys.argv)
    else:
        app = QApplication.instance()
        
    editor = NoteEditor(db)
    highlighter = MarkdownHighlighter(editor.document())
    highlighter.set_theme("Dark")
    editor.highlighter = highlighter
    
    editor.setPlainText("```python\nimport os\n```")
    editor.apply_theme("Dark")
    app.processEvents()
    
    doc = editor.document()
    block = doc.findBlockByNumber(1) # import os
    
    # Check Block Format Background (Should be Dark Gray)
    block_bg = block.blockFormat().background().color().name().lower()
    print(f"Block BG: {block_bg}")
    if block_bg != "#2d2d2d":
        print("FAIL: Block background missing.")
        return False
        
    # Check Char Format Background (Should be NoBrush/Transparent)
    formats = block.layout().formats()
    for r in formats:
        char_bg = r.format.background().style()
        print(f"Char BG Style for '{block.text()[r.start:r.start+r.length]}': {char_bg}")
        if char_bg != Qt.NoBrush:
             print("FAIL: Char background persists!")
             return False
             
        char_color = r.format.foreground().color().name().upper()
        print(f"Char Color: {char_color}")
        if char_color == "#D4D4D4": # Default Gray
             # Wait, import should be blue
             if "import" in block.text()[r.start:r.start+r.length]:
                  print("FAIL: Keyword is gray!")
                  return False

    print("SUCCESS: Clean background and colored text.")
    return True

if __name__ == "__main__":
    if test_clean_backgrounds():
        sys.exit(0)
    else:
        sys.exit(1)
