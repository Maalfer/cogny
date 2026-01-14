
import sys
import os
import tempfile
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSettings, QCoreApplication
from app.ui.main_window import MainWindow
from app.database.manager import DatabaseManager

def test_last_note_persistence():
    # Use unique org for testing to avoid conflicts
    QCoreApplication.setOrganizationName("CognyTestPersistence")
    QCoreApplication.setApplicationName("CognyTest")
    
    if not QApplication.instance():
        app = QApplication(sys.argv)
    else:
        app = QApplication.instance()
        
    # Temp DB
    fd, db_path = tempfile.mkstemp(suffix=".cdb")
    os.close(fd)
    
    try:
        # Phase 1: Setup and Save
        print("--- Phase 1: Open and Select ---")
        window1 = MainWindow(db_path)
        window1.show()
        
        # Add Note
        root_id = window1.sidebar.model.add_note("Persistent Note", None)
        window1.sidebar.tree_view.expandAll() # Ensure visible
        
        # Select it
        item = window1.sidebar.model.note_items[root_id]
        idx = item.index()
        proxy_idx = window1.sidebar.proxy_model.mapFromSource(idx)
        window1.sidebar.tree_view.setCurrentIndex(proxy_idx)
        app.processEvents()
        
        current_id = window1.editor_area.current_note_id
        print(f"Selected Note ID: {current_id}")
        
        if current_id != root_id:
            print(f"FAIL: Selection failed. got {current_id} expected {root_id}")
            return False
            
        # Simulate Close
        # We manually call closeEvent or just the logic?
        # Calling close() triggers closeEvent usually.
        window1.close()
        app.processEvents()
        
        # Phase 2: Restart and Restore
        print("--- Phase 2: Reopen ---")
        window2 = MainWindow(db_path)
        window2.show()
        app.processEvents()
        
        restored_id = window2.editor_area.current_note_id
        print(f"Restored Note ID: {restored_id}")
        
        if restored_id == root_id:
            print("SUCCESS: Last note restored.")
            return True
        else:
            print(f"FAIL: Expected {root_id}, got {restored_id}")
            return False
            
    finally:
        # Cleanup Settings
        settings = QSettings()
        settings.clear()
        
        if os.path.exists(db_path):
            os.remove(db_path)

if __name__ == "__main__":
    if test_last_note_persistence():
        sys.exit(0)
    else:
        sys.exit(1)
