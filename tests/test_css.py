
import sys
from PySide6.QtWidgets import QApplication, QTextEdit
from app.ui.themes import ThemeManager

def test_css_parsing():
    if not QApplication.instance():
        app = QApplication(sys.argv)
    
    # Get current style
    style_dark = ThemeManager.get_editor_style("Dark")
    
    # Apply to dummy widget
    widget = QTextEdit()
    widget.setObjectName("NoteEditor")
    
    print("Applying Dark Style...")
    # This usually prints warnings to stderr if invalid
    widget.setStyleSheet(style_dark)
    
    style_light = ThemeManager.get_editor_style("Light")
    print("Applying Light Style...")
    widget.setStyleSheet(style_light)
    
    print("If you see 'Could not parse stylesheet', the test reproduced the issue.")

if __name__ == "__main__":
    test_css_parsing()
