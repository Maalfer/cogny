
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QTextDocument, QTextBlockFormat

def test_user_state_persistence():
    app = QApplication(sys.argv)
    doc = QTextDocument()
    doc.setPlainText("Line 1\nLine 2")
    
    block = doc.findBlockByNumber(0)
    block.setUserState(123)
    
    print(f"Initial State: {block.userState()}")
    
    cursor = doc.findBlockByNumber(0).layout() # just to access
    
    # Modify Block Format
    import PySide6.QtGui
    cursor = PySide6.QtGui.QTextCursor(block)
    fmt = block.blockFormat()
    fmt.setBackground(PySide6.QtGui.QColor("red"))
    
    cursor.setBlockFormat(fmt)
    
    print(f"Post-Modification State: {block.userState()}")
    
    if block.userState() != 123:
        print("FAIL: State was reset!")
        return False
        
    print("SUCCESS: State persisted.")
    return True

if __name__ == "__main__":
    test_user_state_persistence()
