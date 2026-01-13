
import sys
from PySide6.QtWidgets import QApplication
from app.ui.editor import NoteEditor
from app.ui.highlighter import MarkdownHighlighter
from app.database.manager import DatabaseManager
from PySide6.QtCore import Qt

def test_bash_highlight():
    if not QApplication.instance():
        app = QApplication(sys.argv)
    else:
        app = QApplication.instance()
        
    db = DatabaseManager(":memory:")
    editor = NoteEditor(db)
    
    # Init Highlighter
    highlighter = MarkdownHighlighter(editor.document())
    highlighter.set_theme("Dark")
    editor.highlighter = highlighter # Inject for completeness, though visual updater uses state
    editor.apply_theme("Dark")
    
    # Bash Content
    text = "```bash\necho \"hello\"\n```"
    editor.setPlainText(text)
    
    app.processEvents()
    
    doc = editor.document()
    b1 = doc.findBlockByNumber(1)
    
    print(f"Block 1: '{b1.text()}' userState: {b1.userState()}")
    
    # Check Colors on "echo"
    formats = b1.layout().formats()
    print(f"Formats found: {len(formats)}")
    
    found_echo_color = False
    
    for r in formats:
        sub = b1.text()[r.start:r.start+r.length]
        color = r.format.foreground().color().name().upper()
        print(f"  '{sub}' -> {color}")
        
        # In Dark Theme:
        # echo maps to 'function' -> #DCDCAA (Yellow)
        if sub == "echo" and color == "#DCDCAA": 
             found_echo_color = True
        elif sub == "echo" and color == "#D4D4D4":
             print("FAIL: echo is still Gray")
             return False

    if not found_echo_color:
        print("FAIL: echo color incorrect or not found.")
        return False

    print("SUCCESS")
    return True

if __name__ == "__main__":
    if test_bash_highlight():
        sys.exit(0)
    else:
        sys.exit(1)
