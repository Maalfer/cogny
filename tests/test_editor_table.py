
import unittest
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QTextTable
from app.ui.editor import NoteEditor
from app.database.manager import DatabaseManager
from unittest.mock import MagicMock

# Ensure QApplication exists only once
app = QApplication.instance()
if not app:
    app = QApplication(sys.argv)

class TestNoteEditorTable(unittest.TestCase):
    def setUp(self):
        self.mock_db = MagicMock(spec=DatabaseManager)
        self.editor = NoteEditor(self.mock_db)

    def tearDown(self):
        self.editor.deleteLater()

    def test_insert_table(self):
        """Verify that insert_table inserts a table with correct dimensions."""
        # Initial State: No tables
        cursor = self.editor.textCursor()
        self.assertIsNone(cursor.currentTable())
        
        # Action: Insert 3x3 Table
        rows, cols = 3, 3
        self.editor.insert_table(rows, cols)
        
        # Verify
        cursor = self.editor.textCursor()
        table = cursor.currentTable()
        self.assertIsNotNone(table, "Table should exist at cursor position")
        self.IsInstance(table, QTextTable)
        
        self.assertEqual(table.rows(), rows)
        self.assertEqual(table.columns(), cols)
        
    def test_insert_table_default(self):
        """Verify default table insertion (2x2)."""
        self.editor.insert_table()
        
        cursor = self.editor.textCursor()
        table = cursor.currentTable()
        self.assertIsNotNone(table)
        self.assertEqual(table.rows(), 2)
        self.assertEqual(table.columns(), 2)
        
    def IsInstance(self, obj, cls):
        self.assertTrue(isinstance(obj, cls), f"{obj} is not instance of {cls}")

if __name__ == '__main__':
    unittest.main()
