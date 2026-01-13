
import sys
from PySide6.QtWidgets import QApplication
from app.ui.editor import NoteEditor
from app.ui.highlighter import MarkdownHighlighter
from app.database.manager import DatabaseManager
from PySide6.QtCore import Qt

def test_html_color_loss():
    db = DatabaseManager(":memory:")
    
    if not QApplication.instance():
        app = QApplication(sys.argv)
    else:
        app = QApplication.instance()
        
    editor = NoteEditor(db)
    highlighter = MarkdownHighlighter(editor.document())
    highlighter.set_theme("Dark")
    editor.highlighter = highlighter
    editor.apply_theme("Dark")
    
    # Simulate loading a note
    # When loading, we use setHtml.
    # Note: setHtml might reset some things.
    html_content = """
    <p>Normal Text</p>
    <p>```python</p>
    <p>import os</p>
    <p>```</p>
    """
    # Or cleaner HTML that represents what comes from the DB or previous saves?
    # Usually `toHtml` wraps things in spans.
    # But let's try basic.
    
    print("--- Setting HTML ---")
    editor.setHtml(html_content)
    
    app.processEvents()
    
    # Force visual update (usually triggered by textChanged, which setHtml triggers)
    # editor.update_code_block_visuals() # Should have run automatically
    
    doc = editor.document()
    
    # Is the highlighter still active?
    print(f"Highlighter Document: {highlighter.document()}")
    print(f"Editor Document: {doc}")
    
    if highlighter.document() != doc:
        print("FAIL: Highlighter detached! setHtml changed the document instance?")
        return False
        
    # Check Code Block
    # We need to find where "import os" ended up.
    # setHtml parses paragraphs.
    
    # Find block with "import os"
    target_block = None
    for i in range(doc.blockCount()):
        b = doc.findBlockByNumber(i)
        if "import os" in b.text():
            target_block = b
            print(f"Found 'import os' at block {i}")
            break
            
    if not target_block:
        print("FAIL: Content not found.")
        return False
        
    # Check State
    print(f"Block State: {target_block.userState()}")
    
    # Check format (Color)
    formats = target_block.layout().formats()
    print(f"Formats found: {len(formats)}")
    
    has_color = False
    for r in formats:
        color = r.format.foreground().color().name().upper()
        text_segment = target_block.text()[r.start:r.start+r.length]
        print(f"  '{text_segment}' -> {color}")
        if color == "#569CD6":
             has_color = True
             
    if not has_color:
        print("FAIL: No syntax color found.")
        return False

    print("SUCCESS")
    return True

if __name__ == "__main__":
    if test_html_color_loss():
        sys.exit(0)
    else:
        sys.exit(1)
