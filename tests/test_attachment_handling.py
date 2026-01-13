
import sys
import unittest
from unittest.mock import patch, MagicMock
from PySide6.QtWidgets import QApplication, QMessageBox, QMenu
from PySide6.QtGui import QKeyEvent, QTextCursor, QMouseEvent
from PySide6.QtCore import Qt, QPoint
from app.ui.editor import NoteEditor
from app.database.manager import DatabaseManager

class TestAttachmentHandling(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        self.db = MagicMock(spec=DatabaseManager)
        self.editor = NoteEditor(self.db)
        self.editor.show()
        
        # Determine a dummy filename that exists for icon generation
        # or mock the icon generation parts if needed.
        # But we can just use "test.txt" and let it use default icon without erroring?
        # insert_attachment uses QFileInfo("test.txt").exists() -> False but icon fails gracefully?
        # QIconProvider handles non-existent files safely usually (returns default icon).
        
        # But let's patch the db.add_attachment part if actual code called it.
        # insert_attachment takes ID and filename. It doesn't use DB in insert_attachment, only in open/delete.
        pass

    def test_insert_attachment_shows_icon(self):
        # Call insert_attachment
        self.editor.insert_attachment(123, "test_doc.pdf")
        
        html = self.editor.toHtml()
        
        # Verify img tag exists (Icon)
        self.assertIn('<img src="data:image/png;base64,', html)
        
        # Verify anchor
        self.assertIn('href="attachment://123"', html)
        self.assertIn('test_doc.pdf', html)
        
    def test_left_click_does_not_open(self):
        self.editor.insert_attachment(123, "test.pdf")
        
        # Mock open_attachment
        with patch.object(self.editor, 'open_attachment') as mock_open:
            # Simulate click on the link
            # We need to find the position.
            # insert logic places it at cursor.
            
            # Since click simulation on specific coordinates is hard without layout calculation,
            # we can call mouseReleaseEvent with a mocked event and verify no call IF anchorAt returns something.
            # Ideally we mock anchorAt.
            
            with patch.object(self.editor, 'anchorAt', return_value="attachment://123"):
                event = QMouseEvent(QMouseEvent.MouseButtonRelease, QPoint(10,10), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
                self.editor.mouseReleaseEvent(event)
                
                # Should NOT call open_attachment
                mock_open.assert_not_called()

    def test_double_click_does_not_open(self):
        self.editor.insert_attachment(123, "test.pdf")
        
        with patch.object(self.editor, 'open_attachment') as mock_open:
            with patch.object(self.editor, 'anchorAt', return_value="attachment://123"):
                event = QMouseEvent(QMouseEvent.MouseButtonDblClick, QPoint(10,10), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
                self.editor.mouseDoubleClickEvent(event)
                
                # Should NOT call open_attachment
                mock_open.assert_not_called()

    def test_right_click_context_menu(self):
        self.editor.insert_attachment(123, "test.pdf")
        
        with patch.object(self.editor, 'anchorAt', return_value="attachment://123"):
            with patch.object(self.editor, 'createStandardContextMenu') as mock_create_menu:
                # Mock Menu with standard actions
                mock_menu = MagicMock(spec=QMenu)
                
                # Create mock actions
                action_copy = MagicMock()
                action_copy.text.return_value = "Copy"
                action_delete_std = MagicMock()
                action_delete_std.text.return_value = "Delete"
                
                # Setup actions list
                mock_menu.actions.return_value = [action_copy, action_delete_std]
                
                mock_create_menu.return_value = mock_menu
                
                # Mock open_attachment and save_attachment_as
                with patch.object(self.editor, 'open_attachment'):
                    with patch.object(self.editor, 'save_attachment_as'):
                    
                        # Simulate Context Menu Event
                        event = MagicMock()
                        event.pos.return_value = QPoint(10,10)
                        event.globalPos.return_value = QPoint(100,100)
                        
                        self.editor.contextMenuEvent(event)
                        
                        # Verify Standard "Delete" was removed
                        mock_menu.removeAction.assert_called_with(action_delete_std)
                        
                        # Verify Actions added
                        # We expect 3 addAction calls (Open, Save As, Delete File)
                        # We can't strictly count >= 3 if removeAction happened, but addAction adds new ones.
                        mock_menu.addAction.assert_any_call("Open File")
                        mock_menu.addAction.assert_any_call("Save File As...")
                        mock_menu.addAction.assert_any_call("Delete File")
                        
                        mock_menu.exec.assert_called_once()
    
    def test_delete_via_context_menu(self):
        # Mock confirmation to return True (Yes)
        with patch('app.ui.widgets.ModernConfirm.show', return_value=True) as mock_msg:
             # Manually trigger the delete method since triggering via menu execution is hard in unit test without signals
             # But we can call the method directly to verify logic
             
             # Insert and define range (dummy)
             self.editor.insert_attachment(123, "test.pdf")
             
             # Call method
             self.editor.delete_attachment_interactive(123, None)
             
             # Verify DB call
             self.db.delete_attachment.assert_called_with(123)
             mock_msg.assert_called_once()

    def test_save_attachment_as(self):
        # Mock DB
        self.db.get_attachment.return_value = ("test.pdf", b"DATA")
        
        # Mock QFileDialog
        with patch('PySide6.QtWidgets.QFileDialog.getSaveFileName', return_value=("/tmp/saved_test.pdf", "PDF")):
            # Mock open builtin
            with patch('builtins.open', new_callable=MagicMock()) as mock_file:
                 mock_f = mock_file.return_value.__enter__.return_value
                 
                 self.editor.save_attachment_as(123)
                 
                 # Verify write
                 mock_file.assert_called_with("/tmp/saved_test.pdf", 'wb')
                 mock_f.write.assert_called_with(b"DATA")

    def test_delete_attachment_confirmation(self):
        # Insert
        self.editor.insert_attachment(123, "test.pdf")
        
        # Select it
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.Start)
        cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
        self.editor.setTextCursor(cursor)
        
        # Confirm Selection has attachment
        is_att, att_id, _ = self.editor.cursor_contains_attachment(cursor)
        self.assertTrue(is_att)
        self.assertEqual(att_id, 123)
        
        # 1. Cancel Delete
        with patch('app.ui.widgets.ModernConfirm.show', return_value=False) as mock_msg:
             event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Delete, Qt.NoModifier)
             self.editor.keyPressEvent(event)
             
             mock_msg.assert_called_once()
             # DB delete NOT called
             self.db.delete_attachment.assert_not_called()
             
        # 2. Confirm Delete
        with patch('app.ui.widgets.ModernConfirm.show', return_value=True) as mock_msg:
             event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Delete, Qt.NoModifier)
             self.editor.keyPressEvent(event)
             
             mock_msg.assert_called_once()
             self.db.delete_attachment.assert_called_once_with(123)

    def test_open_attachment_linux_subprocess(self):
        # Mock sys.platform to linux
        with patch('sys.platform', 'linux'):
            with patch('subprocess.Popen') as mock_popen:
                self.db.get_attachment.return_value = ("test.pdf", b"data")
                self.editor.open_attachment(123)
                
                # Check if xdg-open was called
                args, _ = mock_popen.call_args
                self.assertEqual(args[0][0], 'xdg-open')
                self.assertIn('cogni_test_', args[0][1])


    def test_context_menu_action_triggers_method(self):
        """Test that triggering the context menu action actually calls the method, 
           handling the signal argument issue."""
        self.editor.insert_attachment(123, "test.pdf")
        
        # We need to capture the created actions
        with patch.object(self.editor, 'anchorAt', return_value="attachment://123"):
            with patch.object(self.editor, 'createStandardContextMenu') as mock_create_menu:
                mock_menu = MagicMock(spec=QMenu)
                mock_create_menu.return_value = mock_menu
                
                # Mock methods to check if they are called
                with patch.object(self.editor, 'delete_attachment_interactive') as mock_delete:
                    with patch.object(self.editor, 'open_attachment') as mock_open:
                        with patch.object(self.editor, 'save_attachment_as') as mock_save:
                        
                            # We actually need to intercept addAction to get the QAction objects 
                            # or the connection objects.
                            # Since addAction returns a QAction (mocked), we can check what was done to it.
                            # But standard mock destroys the link. 
                            # We need the ACTUAL 'triggered.connect' to be called.
                            
                            # Let's use a real QMenu but mock the exec logic?
                            # Or just mock addAction to return a Mock that has triggered signal?
                            
                            # Signal mock helper
                            actions = {}
                            
                            def add_action_side_effect(text):
                                action_mock = MagicMock()
                                actions[text] = action_mock
                                return action_mock
                                
                            mock_menu.addAction.side_effect = add_action_side_effect
                            
                            # Trigger Event
                            event = MagicMock()
                            event.pos.return_value = QPoint(10,10)
                            event.globalPos.return_value = QPoint(100,100)
                            self.editor.contextMenuEvent(event)
                            
                            # Now we have the mock actions.
                            # Find 'Delete File' action
                            delete_action = actions.get("Delete File")
                            self.assertIsNotNone(delete_action)
                            
                            # Retrieve the connected slot
                            # connect is called with a callable.
                            # delete_action.triggered.connect.call_args[0][0] is the lambda.
                            connected_lambda = delete_action.triggered.connect.call_args[0][0]
                            
                            # CALL IT with a boolean argument (simulate triggered(False))
                            # This is the crux of the bug: if this raises TypeError, the fix is needed.
                            try:
                                connected_lambda(False)
                            except TypeError:
                                self.fail("Lambda raised TypeError when called with boolean arg (signal emission style)")
                                
                            # Verify target method called
                            mock_delete.assert_called()


if __name__ == "__main__":
    unittest.main()
