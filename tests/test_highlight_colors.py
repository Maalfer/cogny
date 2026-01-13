
import sys
import time
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QTextDocument, QColor, QTextCursor, QSyntaxHighlighter
from app.ui.highlighter import MarkdownHighlighter
from app.ui.themes import ThemeManager

def test_highlighting():
    # Ensure App exists
    if not QApplication.instance():
        app = QApplication(sys.argv)
    else:
        app = QApplication.instance()
    
    doc = QTextDocument()
    highlighter = MarkdownHighlighter(doc)
    highlighter.set_theme("Dark") 
    
    text_content = "```python\nimport os\n```"
    doc.setPlainText(text_content)
    
    # Process events to ensure highlighting happens (sometimes async/queued)
    app.processEvents()
    
    print(f"Doc Line Count: {doc.blockCount()}")
    
    block0 = doc.findBlockByNumber(0)
    print(f"Block 0: '{block0.text()}' State: {block0.userState()}")
    
    # Check languages list
    print(f"Registered Languages: {highlighter.languages}")
    
    if "python" not in highlighter.languages:
        # Force rehighlight manually?
        highlighter.rehighlight()
        app.processEvents()
        print(f"Registered Languages after rehighlight: {highlighter.languages}")
    
    if "python" not in highlighter.languages:
        print("FAIL: 'python' not registered in highlighter.")
        return False
        
    block1 = doc.findBlockByNumber(1)
    text1 = block1.text()
    print(f"Block 1: '{text1}'")
    
    formats = block1.layout().formats()
    print(f"Found {len(formats)} format ranges in Block 1.")
    
    found_keyword = False
    for r in formats:
        fmt = r.format
        color = fmt.foreground().color().name().upper()
        start = r.start
        length = r.length
        sub = text1[start:start+length]
        print(f"  '{sub}' ({color})")
        if sub == "import" and color == "#569CD6":
             found_keyword = True
             
    if not found_keyword:
        print("FAIL: Check colors.")
        return False

    return True

if __name__ == "__main__":
    if test_highlighting():
        print("SUCCESS")
        sys.exit(0)
    else:
        sys.exit(1)
