
import sys
import unittest
from unittest.mock import patch, MagicMock
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QKeyEvent, QTextCursor
from PySide6.QtCore import Qt, QByteArray, QBuffer, QIODevice
from app.ui.editor import NoteEditor
from app.database.manager import DatabaseManager

class TestImageDeletion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        self.db = DatabaseManager(":memory:")
        self.editor = NoteEditor(self.db)
        self.editor.show()
        
        # Insert Dummy Image
        self.editor.textCursor().insertHtml('<img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUAAAAFCAYAAACNbyblAAAAHElEQVQI12P4//8/w38GIAXDIBKE0DHxgljNBAAO9TXL0Y4OHwAAAABJRU5ErkJggg==" />')
        QApplication.processEvents()

    def test_cancel_deletion(self):
        # 1. Position cursor after image
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.editor.setTextCursor(cursor)
        
        # 2. Mock QMessageBox to return No
        with patch('PySide6.QtWidgets.QMessageBox.question', return_value=QMessageBox.No) as mock_msg:
            # 3. Simulate Backspace
            event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Backspace, Qt.NoModifier)
            self.editor.keyPressEvent(event)
            
            # Check interaction
            mock_msg.assert_called_once()
            
            # 4. Verify Image Still Exists (doc length > 0 or has image)
            # An empty doc has 1 block, empty text.
            # Convert to HTML to check img tag
            html = self.editor.toHtml()
            self.assertIn("<img", html)
            print("SUCCESS: Deletion Cancelled. Image preserved.")

    def test_confirm_deletion(self):
        # 1. Position cursor after image
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.editor.setTextCursor(cursor)
        
        # 2. Mock QMessageBox to return Yes
        with patch('PySide6.QtWidgets.QMessageBox.question', return_value=QMessageBox.Yes) as mock_msg:
            # 3. Simulate Backspace
            event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Backspace, Qt.NoModifier)
            self.editor.keyPressEvent(event)
             
            # Check interaction
            mock_msg.assert_called_once()
            
            # 4. Verify Image Gone
            # Text should be empty or just block chars
            doc_text = self.editor.toPlainText().strip()
            # toHtml usually wraps in empty structure. 
            # Check for img tag.
            html = self.editor.toHtml()
            # Note: Depending on Qt version, toHtml might still keep minimal markup.
            # But the specific img tag from data src should be gone or changed.
            
            # If deleted, the fragment is gone.
            # Let's check block count or content.
            # Actually, insertHtml creates a fragment.
            
            # We can check specific img detection logic
            found = False
            block = self.editor.document().begin()
            while block.isValid():
                it = block.begin()
                while not it.atEnd():
                    if it.fragment().charFormat().isImageFormat():
                        found = True
                    it += 1
                block = block.next()
                
            self.assertFalse(found, "Image should be deleted")
            print("SUCCESS: Deletion Confirmed. Image removed.")

if __name__ == "__main__":
    unittest.main()
