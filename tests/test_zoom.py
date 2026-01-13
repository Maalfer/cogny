import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont

# Init App
if not QApplication.instance():
    app = QApplication(sys.argv)

from app.ui.editor import NoteEditor
from app.database.manager import DatabaseManager
from app.ui.themes import ThemeManager

class MockDB:
    pass

def test_text_zoom_changes_font_but_keeps_images():
    editor = NoteEditor(MockDB())
    
    # 1. Initial State
    initial_font_size = editor.current_font_size
    assert initial_font_size == 14, f"Initial font size should be 14, got {initial_font_size}"
    
    # Check Font Property
    assert editor.font().pointSize() == 14, f"Widget font size mismatch: {editor.font().pointSize()}"
    
    # 2. Zoom In
    editor.textZoomIn()
    new_size = editor.current_font_size
    assert new_size == 15, f"Font size should increase to 15, got {new_size}"
    
    assert editor.font().pointSize() == 15, f"Widget font size mismatch after zoom in: {editor.font().pointSize()}"
    
    # 3. Zoom Out
    editor.textZoomOut()
    editor.textZoomOut()
    new_size = editor.current_font_size
    assert new_size == 13, f"Font size should decrease to 13, got {new_size}"
    
    assert editor.font().pointSize() == 13, f"Widget font size mismatch after zoom out: {editor.font().pointSize()}"

    print("Text Zoom Test Passed")

def test_zoom_does_not_reset_custom_background():
    # Setup with custom background logic injection if needed
    # But currently `apply_theme` defaults to None.
    # We want to verified if we can preserve it.
    
    editor = NoteEditor(MockDB())
    
    # Simulate custom bg applied via MainWindow
    custom_bg = "#123456"
    editor.apply_theme("Dark", custom_bg)
    
    style = editor.styleSheet()
    assert f"background-color: {custom_bg}" in style, "Custom BG not applied initially"
    
    # Trigger Zoom
    editor.textZoomIn()
    
    # Check if BG is preserved (It FAILS currently because code passes None)
    style = editor.styleSheet()
    if f"background-color: {custom_bg}" not in style:
        print("FAIL: Custom background was reset during zoom!")
    else:
        print("PASS: Custom background preserved during zoom")

if __name__ == "__main__":
    try:
        test_text_zoom_changes_font_but_keeps_images()
        test_zoom_does_not_reset_custom_background()
    except AssertionError as e:
        print(f"Test Failed: {e}")
        sys.exit(1)
