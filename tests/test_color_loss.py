
import sys
from PySide6.QtWidgets import QApplication
from app.ui.editor import NoteEditor
from app.ui.highlighter import MarkdownHighlighter
from app.database.manager import DatabaseManager
from PySide6.QtCore import Qt

def test_color_loss():
    db = DatabaseManager(":memory:")
    
    if not QApplication.instance():
        app = QApplication(sys.argv)
    else:
        app = QApplication.instance()
        
    editor = NoteEditor(db)
    
    # Setup Highlighter matching main_window
    highlighter = MarkdownHighlighter(editor.document())
    highlighter.set_theme("Dark")
    editor.highlighter = highlighter
    
    editor.show()
    
    # Insert code
    editor.setPlainText("```python\nimport os\n```")
    
    # Apply theme (Triggers update_code_block_visuals)
    editor.apply_theme("Dark")
    
    # Force process events
    app.processEvents()
    
    # Check formats on "import os" (Block 1)
    doc = editor.document()
    block = doc.findBlockByNumber(1)
    text = block.text()
    
    print(f"Block 1: '{text}' State: {block.userState()}")
    
    formats = block.layout().formats()
    print(f"Format Ranges found: {len(formats)}")
    
    has_color = False
    for r in formats:
        color = r.format.foreground().color().name().upper()
        print(f"  Range {r.start}-{r.start+r.length}: {text[r.start:r.start+r.length]} -> {color}")
        if color == "#569CD6": # Python keyword blue
            has_color = True
            
    if not has_color:
        print("FAIL: No syntax coloring found.")
        return False
        
    print("SUCCESS: Syntax coloring intact.")
    return True

if __name__ == "__main__":
    if test_color_loss():
        sys.exit(0)
    else:
        sys.exit(1)
