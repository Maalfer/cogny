
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QTextDocument, QTextCharFormat, QFont, QFontMetrics, QColor
from PySide6.QtCore import Qt

def test_hidden_width():
    if not QApplication.instance():
        app = QApplication(sys.argv)
    else:
        app = QApplication.instance()
        
    # 1. Standard Font
    fmt = QTextCharFormat()
    fmt.setFontFamilies(["Arial"])
    fmt.setFontPointSize(12)
    
    font = fmt.font()
    fm = QFontMetrics(font)
    width_normal = fm.horizontalAdvance("# ")
    print(f"Normal Width '# ': {width_normal}")
    
    # 2. Transparent Format (Current Implementation)
    fmt_transparent = QTextCharFormat(fmt)
    fmt_transparent.setForeground(QColor("transparent"))
    
    font_trans = fmt_transparent.font()
    fm_trans = QFontMetrics(font_trans)
    width_trans = fm_trans.horizontalAdvance("# ")
    print(f"Transparent Width '# ': {width_trans}")
    
    if width_trans == width_normal:
        print("CONFIRMED: Transparent text takes up full space.")
    else:
        print(f"Unexpected: Transparent width {width_trans} != {width_normal}")
        
    # 3. Proposed Fix: Font Size 0 or 1
    fmt_fix = QTextCharFormat(fmt_transparent)
    fmt_fix.setFontPointSize(1) # Try 1pt
    
    font_fix = fmt_fix.font()
    fm_fix = QFontMetrics(font_fix)
    width_fix = fm_fix.horizontalAdvance("# ")
    print(f"Fix (1pt) Width '# ': {width_fix}")
    
    fmt_fix_0 = QTextCharFormat(fmt_transparent)
    fmt_fix_0.setFontPointSize(0.1) # Try decimals? Qt usually clamps.
    font_fix_0 = fmt_fix_0.font()
    fm_fix_0 = QFontMetrics(font_fix_0)
    width_fix_0 = fm_fix_0.horizontalAdvance("# ")
    print(f"Fix (0.1pt) Width '# ': {width_fix_0}")
    
    return True

if __name__ == "__main__":
    test_hidden_width()
