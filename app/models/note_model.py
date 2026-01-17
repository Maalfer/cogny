from PySide6.QtGui import QStandardItemModel, QIcon, QStandardItem
from PySide6.QtCore import Qt, QMimeData, QByteArray, QDataStream, QIODevice
from typing import Optional, Dict
from app.models.note_item import NoteItem

class NoteTreeModel(QStandardItemModel):
    def __init__(self, file_manager):
        super().__init__()
        self.fm = file_manager
        self.setHorizontalHeaderLabels(["Notas"])
        self.note_items: Dict[str, NoteItem] = {} # Key is now path (str)

    def load_notes(self):
        self.clear()
        self.setHorizontalHeaderLabels(["Notas"])
        self.note_items = {}
        
        # Load Root
        children = self.fm.get_children(None)
        
        for r in children:
            nid = r['id']
            title = r['title']
            is_folder = r['is_folder']
            
            item = NoteItem(nid, title, is_folder)
            self.note_items[nid] = item
            
            if is_folder:
                item.appendRow(QStandardItem("Loading..."))
                item.setData(True, Qt.UserRole + 1)
            
            self.invisibleRootItem().appendRow(item)
            
        self.refresh_icons()

    def fetch_children(self, parent_index):
        item = self.itemFromIndex(parent_index)
        if not item: return
        if not item.data(Qt.UserRole + 1): return # Already loaded
             
        if item.rowCount() > 0:
             item.removeRow(0) # Remove "Loading..."
        
        children = self.fm.get_children(item.note_id)
        
        for r in children:
            nid = r['id']
            title = r['title']
            is_folder = r['is_folder']
            
            child_item = NoteItem(nid, title, is_folder)
            self.note_items[nid] = child_item
            
            if is_folder:
                child_item.appendRow(QStandardItem("Loading..."))
                child_item.setData(True, Qt.UserRole + 1)
                
            item.appendRow(child_item)
            
        item.setData(False, Qt.UserRole + 1)
        self.refresh_icons()

    def refresh_icons(self):
        from PySide6.QtWidgets import QApplication, QStyle
        style = QApplication.style()
        folder_icon = style.standardIcon(QStyle.SP_DirIcon)
        note_icon = style.standardIcon(QStyle.SP_FileIcon) 
        
        for item in list(self.note_items.values()):
            try:
                if getattr(item, 'is_folder', False):
                    item.setIcon(folder_icon)
                else:
                    item.setIcon(note_icon)
            except RuntimeError:
                continue

    def add_note(self, title: str, parent_id: Optional[str], is_folder: bool = False) -> Optional[str]:
        # Determine Path
        import os
        if parent_id:
             new_id = os.path.join(parent_id, title)
        else:
             new_id = title
             
        success = self.fm.create_note(new_id, is_folder)
        if not success: return None
        
        new_item = NoteItem(new_id, title, is_folder)
        self.note_items[new_id] = new_item
        
        if parent_id is None:
            self.invisibleRootItem().appendRow(new_item)
        elif parent_id in self.note_items:
            parent = self.note_items[parent_id]
            # Ensure parent is expanded/loaded? 
            # If parent wasn't loaded, we might duplicate? 
            # Ideally we force fetch children if not loaded.
            if parent.data(Qt.UserRole + 1): # Not loaded yet
                self.fetch_children(parent.index())
            else:
                parent.appendRow(new_item)
                
        self.refresh_icons()
        return new_id
        
    def delete_note(self, note_id: str):
        self.fm.delete_item(note_id)
        
        if note_id in self.note_items:
            item = self.note_items[note_id]
            try:
                parent = item.parent() or self.invisibleRootItem()
                parent.removeRow(item.row())
            except RuntimeError:
                pass
            del self.note_items[note_id]

    # Drag and Drop Implementation
    def flags(self, index):
        default_flags = Qt.ItemIsDragEnabled | Qt.ItemIsSelectable | Qt.ItemIsEnabled
        
        if not index.isValid():
            return default_flags | Qt.ItemIsDropEnabled
            
        item = self.itemFromIndex(index)
        is_folder = getattr(item, 'is_folder', False) or self.rowCount(index) > 0
        
        if is_folder:
            return default_flags | Qt.ItemIsDropEnabled
            
        return default_flags

    def supportedDropActions(self):
        return Qt.MoveAction

    def mimeTypes(self):
        return ["application/x-cogny-note-id"]

    def mimeData(self, indexes):
        mime = QMimeData()
        encoded_data = QByteArray()
        stream = QDataStream(encoded_data, QIODevice.WriteOnly)

        for index in indexes:
            if index.isValid():
                item = self.itemFromIndex(index)
                stream.writeQString(item.note_id) # Was writeInt32
        
        mime.setData("application/x-cogny-note-id", encoded_data)
        return mime

    def dropMimeData(self, data, action, row, column, parent):
        if action == Qt.IgnoreAction:
            return True

        if not data.hasFormat("application/x-cogny-note-id"):
            return False

        encoded_data = data.data("application/x-cogny-note-id")
        stream = QDataStream(encoded_data, QIODevice.ReadOnly)
        
        target_item = self.itemFromIndex(parent)
        destination_parent = target_item
        
        new_parent_id = None
        if target_item:
             new_parent_id = target_item.note_id
        
        # If dropping on root (invalid parent), new_parent_id remains None
        
        # If dropping on root (invalid parent), new_parent_id remains None
        
        # Remove manual layout signals as load_notes() handles model reset
        try:
            while not stream.atEnd():
                note_id = stream.readQString()
                
                if note_id == new_parent_id:
                    continue
    
                if note_id in self.note_items:
                    item = self.note_items[note_id]
                    
                    # Circular check
                    check_item = target_item
                    is_circular = False
                    while check_item:
                        if check_item.note_id == note_id:
                            is_circular = True
                            break
                        check_item = check_item.parent()
                    
                    if is_circular:
                         continue
                    
                    # Move in File System
                    new_id = self.fm.move_item(note_id, new_parent_id)
                    
                    if not new_id: continue
                    
                    # Since IDs are paths, moving invalidates all IDs in the subtree.
                    # We must reload the model to ensure consistency.
                    self.load_notes() 
                    
                    # Return True to signal success. 
                    # Note: Since we reset the model, the View's attempt to removeRows (if any)
                    # should be harmless or fail silently against the new model state.
                    return True

        except Exception as e:
            print(f"Error in dropMimeData: {e}")
             
        return False

