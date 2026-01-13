
import sys
import os
import tempfile
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QModelIndex
from app.database.manager import DatabaseManager
from app.models.note_model import NoteTreeModel

def test_dnd_logic():
    if not QApplication.instance():
        app = QApplication(sys.argv)
    else:
        app = QApplication.instance()
        
    fd, db_path = tempfile.mkstemp(suffix=".cdb")
    os.close(fd)
    
    try:
        db = DatabaseManager(db_path)
        model = NoteTreeModel(db)
        
        # 1. Setup Data
        # Root Folder (1)
        root_id = model.add_note("Folder A", None)
        
        # Target Subfolder (2)
        sub_id = model.add_note("Subfolder B", root_id)
        
        # Note to Move (3) (Currently at Root)
        move_id = model.add_note("Note To Move", None)
        
        # Verify Initial State
        check = db.get_note(move_id)
        print(f"Initial Parent: {check[1]}") # Should be None
        if check[1] is not None:
            print("FAIL: Initial setup incorrect.")
            return False
            
        move_item = model.note_items[move_id]
        sub_item = model.note_items[sub_id]
        
        # 2. Simulate Drag (MimeData Creation)
        # We need the index of the item to move
        indexes = [move_item.index()]
        mime_data = model.mimeData(indexes)
        
        if not mime_data.hasFormat("application/x-cogny-note-id"):
            print("FAIL: MimeData format missing.")
            return False
            
        # 3. Simulate Drop (onto Subfolder)
        # parent index is the index of sub_item
        target_index = sub_item.index()
        
        # Action: Move
        # Row/Col: -1 (drop onto item, not between rows specificially, usually -1)
        result = model.dropMimeData(mime_data, Qt.MoveAction, -1, -1, target_index)
        
        if not result:
            print("FAIL: dropMimeData returned False.")
            return False
            
        # 4. Verify DB Update
        check_after = db.get_note(move_id)
        new_pid = check_after[1]
        print(f"New Parent ID: {new_pid} (Expected {sub_id})")
        
        if new_pid != sub_id:
            print(f"FAIL: Database parent_id mismatch.")
            return False
            
        # 5. Verify Model Structure
        # The move_item should now be a child of sub_item
        # Note: In StandardItemModel, if we move rows, the python object wrapper might be refreshed or same.
        # But 'move_item.parent()' should be sub_item.
        
        # Let's re-fetch item from map just in case implementation replaced it? 
        # (Our impl reuses item objects usually, but takeRow returns generic items)
        # Check current item parent
        current_parent = move_item.parent()
        if current_parent is not None:
             # StandardItemModel parent is a QStandardItem
             # sub_item is a NoteItem(QStandardItem)
             if current_parent.text() == "Subfolder B": # Simple check
                  print("SUCCESS: Model hierarchy updated.")
             else:
                  print(f"FAIL: Model parent is {current_parent.text()}")
                  return False
        else:
             print("FAIL: Model item has no parent.")
             return False
             
        return True
        
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)

if __name__ == "__main__":
    if test_dnd_logic():
        sys.exit(0)
    else:
        sys.exit(1)
