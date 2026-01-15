import unittest
import os
from PySide6.QtWidgets import QApplication
from app.database.manager import DatabaseManager
from unittest.mock import MagicMock, patch

# Ensure app instance
app = QApplication.instance() or QApplication([])

class TestReadLater(unittest.TestCase):
    def setUp(self):
        self.db_path = "test_read_later.cdb"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        self.db = DatabaseManager(self.db_path)

    def tearDown(self):
        # self.db.close_connection() # ensure connection closed (Handled by context managers/GC)
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_migration_and_defaults(self):
        # 1. Check if column exists (SetupMixin should have added it)
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(notes)")
        columns = [info[1] for info in cursor.fetchall()]
        self.assertIn("is_read_later", columns)
        
        # 2. Add Note and check default
        note_id = self.db.add_note("Default Check")
        cursor.execute("SELECT is_read_later FROM notes WHERE id=?", (note_id,))
        val = cursor.fetchone()[0]
        self.assertEqual(val, 0) # SQLite default 0 for False

    def test_toggle_logic(self):
        note_id = self.db.add_note("Toggle Test")
        
        # Toggle ON
        state = self.db.toggle_read_later(note_id)
        self.assertTrue(state)
        
        # Verify DB
        rows = self.db.get_read_later_notes()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], note_id)
        
        # Toggle OFF
        state = self.db.toggle_read_later(note_id)
        self.assertFalse(state)
        
        # Verify DB
        rows = self.db.get_read_later_notes()
        self.assertEqual(len(rows), 0)

    def test_dialog_logic(self):
        # Setup Data
        n1 = self.db.add_note("Note 1")
        n2 = self.db.add_note("Note 2") 
        self.db.toggle_read_later(n1)
        
        # Init Dialog
        from app.ui.dialogs.read_later_dialog import ReadLaterDialog
        dlg = ReadLaterDialog(self.db)
        
        # Check List
        self.assertEqual(dlg.list_widget.count(), 1)
        item = dlg.list_widget.item(0)
        self.assertIn("Note 1", item.text())
        
        # Mock Signal
        mock_signal = MagicMock()
        dlg.note_selected.connect(mock_signal)
        
        # Select and Click Open
        item.setSelected(True)
        dlg.on_open_clicked()
        
        # Verify Signal
        mock_signal.assert_called_with(n1)
        
        # Verify Remove Logic
        # Re-init or just reset list
        self.db.toggle_read_later(n1) # Off
        dlg.load_notes()
        self.assertEqual(dlg.list_widget.count(), 1) # Should show "No notes" placeholder
        self.assertNotIn("Note 1", dlg.list_widget.item(0).text())

if __name__ == '__main__':
    unittest.main()
