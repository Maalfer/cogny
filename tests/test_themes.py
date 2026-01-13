import unittest
import sys
from PySide6.QtWidgets import QApplication

# Initialize QApplication for QPalette usage if needed (ThemeManager.get_palette uses it)
if not QApplication.instance():
    app = QApplication(sys.argv)

from app.ui.themes import ThemeManager

class TestThemeManager(unittest.TestCase):
    def test_get_editor_style_no_crash(self):
        """Test that get_editor_style returns a string without crashing."""
        try:
            style_dark = ThemeManager.get_editor_style("Dark")
            self.assertIsInstance(style_dark, str)
            self.assertIn("background-color:", style_dark)
            
            style_light = ThemeManager.get_editor_style("Light")
            self.assertIsInstance(style_light, str)
            self.assertIn("background-color:", style_light)
            
             # With custom colors
            style_custom = ThemeManager.get_editor_style("Dark", "#123456")
            self.assertIn("#123456", style_custom)
            
        except NameError as e:
            self.fail(f"get_editor_style raised NameError: {e}")
        except ValueError as e:
             self.fail(f"get_editor_style raised ValueError (f-string): {e}")

if __name__ == '__main__':
    unittest.main()
