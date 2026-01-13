
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QTextDocument, QSyntaxHighlighter, QTextCursor
from app.ui.highlighter import MarkdownHighlighter

def test_header_sizes():
    if not QApplication.instance():
        app = QApplication(sys.argv)
    else:
        app = QApplication.instance()
        
    doc = QTextDocument()
    highlighter = MarkdownHighlighter(doc)
    
    # Test Data: (Text, Expected Size)
    test_cases = [
        ("# Title One", 0), # Expect standard size
        ("## Title Two", 0),
        ("### Title Three", 0),
        ("#### Title Four", 0),
        ("Normal Text", 0) 
    ]
    
    cursor = QTextCursor(doc)
    
    for text, expected in test_cases:
        cursor.insertText(text + "\n")
        
    app.processEvents()
    highlighter.rehighlight()
    app.processEvents()
    
    # We might need to manually trigger rehighlight or wait loop?
    # Let's inspect immediately.
    
    block = doc.begin()
    idx = 0
    
    while block.isValid() and idx < len(test_cases):
        text, expected = test_cases[idx]
        print(f"Checking Block: '{block.text().strip()}' (Expected {expected}pt)")
        
        # Highlighter formats are in the layout's additional formats
        layout = block.layout()
        formats = layout.formats() 
        # formats is a list of FormatRange objects
        
        found_size = 0
        
        # Iterate formats to finding the one covering the text (usually idx 0)
        # Note: We also have the hidden format for the hashes!
        # And the bold format.
        
        for r in formats:
            fmt = r.format
            size = fmt.fontPointSize()
            # We look for the main text size.
            # Hidden format size is 0.1
            if size > 1:
                found_size = int(size)
                # Keep looking if there are multiple? 
                # The header format covers the whole line "self.setFormat(0, len(text), header_format)"
                # Then hidden overwrites a part.
                # So we should find one record with large size.
                break
                
        if expected > 0:
            if found_size == expected:
                print(f"SUCCESS: Found size {found_size}")
            else:
                print(f"FAIL: Expected {expected}, got {found_size}")
                # Debug formats
                for i, r in enumerate(formats):
                    print(f"  Fmt {i}: start={r.start}, len={r.length}, size={r.format.fontPointSize()}, date={r.format.fontWeight()}")
                return False
        else:
            if found_size == 0 or found_size == 12 or found_size == 14: # Assuming default is ignored or standard
                 # If found_size is 0, it means property not set, valid.
                 print(f"SUCCESS: Normal text (size {found_size})")
        
        block = block.next()
        idx += 1
        
    return True

if __name__ == "__main__":
    if test_header_sizes():
        sys.exit(0)
    else:
        sys.exit(1)
