from PySide6.QtGui import QStandardItemModel, QIcon, QStandardItem
from PySide6.QtCore import Qt, QMimeData, QByteArray, QDataStream, QIODevice
from typing import Optional, Dict
from app.models.note_item import NoteItem

class NoteTreeModel(QStandardItemModel):
    def __init__(self, db_manager):
        super().__init__()
        self.db = db_manager
        self.setHorizontalHeaderLabels(["Notas"])
        self.note_items: Dict[int, NoteItem] = {}

    def load_notes(self):
        self.clear()
        self.setHorizontalHeaderLabels(["Notas"])
        self.note_items = {}
        
        conn = self.db._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, title, is_folder FROM notes WHERE parent_id IS NULL ORDER BY title")
        roots = cursor.fetchall()
        
        cursor.execute("SELECT DISTINCT parent_id FROM notes WHERE parent_id IS NOT NULL")
        parents_with_children = {row[0] for row in cursor.fetchall()}
        
        conn.close()

        for r in roots:
            nid = r['id']
            title = r['title']
            is_folder = bool(r['is_folder'])
            
            item = NoteItem(nid, title, is_folder)
            self.note_items[nid] = item
            
            if nid in parents_with_children or is_folder:
                item.appendRow(QStandardItem("Loading..."))
                item.setData(True, Qt.UserRole + 1)
            
            self.invisibleRootItem().appendRow(item)
            
        self.refresh_icons()

    def fetch_children(self, parent_index):
        item = self.itemFromIndex(parent_index)
        if not item:
            return
            
        if not item.data(Qt.UserRole + 1):
             return
             
        if item.rowCount() > 0:
             item.removeRow(0)
        
        conn = self.db._get_connection()
        cursor = conn.cursor()
        
        pid = item.note_id
        cursor.execute("SELECT id, title, is_folder FROM notes WHERE parent_id = ? ORDER BY title", (pid,))
        children = cursor.fetchall()
        
        cursor.execute("SELECT DISTINCT parent_id FROM notes WHERE parent_id IN (SELECT id FROM notes WHERE parent_id = ?)", (pid,))
        grandparents = {row[0] for row in cursor.fetchall()}
        
        conn.close()
        
        for r in children:
            nid = r['id']
            title = r['title']
            is_folder = bool(r['is_folder'])
            
            child_item = NoteItem(nid, title, is_folder)
            self.note_items[nid] = child_item
            
            if nid in grandparents or is_folder:
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
                if not item.index().isValid() and item != self.invisibleRootItem():
                     pass

                is_explicit_folder = getattr(item, 'is_folder', False)
                
                if is_explicit_folder:
                    item.setIcon(folder_icon)
                else:
                    item.setIcon(note_icon)
            except RuntimeError:
                continue

    def add_note(self, title: str, parent_id: Optional[int], is_folder: bool = False) -> int:
        new_id = self.db.add_note(title, parent_id, is_folder=is_folder)
        new_item = NoteItem(new_id, title, is_folder)
        self.note_items[new_id] = new_item
        
        if parent_id is None:
            self.invisibleRootItem().appendRow(new_item)
        elif parent_id in self.note_items:
            parent = self.note_items[parent_id]
            parent.appendRow(new_item)
            self.refresh_icons()
            
        self.refresh_icons()
        return new_id
        
    def delete_note(self, note_id: int):
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
                stream.writeInt32(item.note_id)
        
        mime.setData("application/x-cogny-note-id", encoded_data)
        return mime

    def dropMimeData(self, data, action, row, column, parent):
        if action == Qt.IgnoreAction:
            return True

        if not data.hasFormat("application/x-cogny-note-id"):
            return False

        encoded_data = data.data("application/x-cogny-note-id")
        stream = QDataStream(encoded_data, QIODevice.ReadOnly)
        
        new_parent_id = None
        target_item = self.itemFromIndex(parent)
        
        insert_row = row 
        destination_parent = target_item
        
        if target_item:
            is_folder = getattr(target_item, 'is_folder', False) or target_item.rowCount() > 0
            
            if not is_folder and insert_row == -1:
                destination_parent = target_item.parent() 
                if destination_parent is None:
                    destination_parent = self.invisibleRootItem()
                    new_parent_id = None
                else:
                    new_parent_id = destination_parent.note_id
                    
                insert_row = target_item.row()
            else:
                new_parent_id = target_item.note_id
        else:
             destination_parent = self.invisibleRootItem()
             
        self.layoutAboutToBeChanged.emit()
        
        try:
            while not stream.atEnd():
                note_id = stream.readInt32()
                
                if note_id == new_parent_id:
                    continue
    
                if note_id in self.note_items:
                    item = self.note_items[note_id]
                    
                    check_item = target_item
                    is_circular = False
                    while check_item:
                        if check_item.note_id == note_id:
                            is_circular = True
                            break
                        check_item = check_item.parent()
                    
                    if is_circular:
                        continue
    
                    self.db.move_note_to_parent(note_id, new_parent_id)
    
                    source_parent = item.parent() or self.invisibleRootItem()
                    
                    if destination_parent is None:
                         destination_parent = self.invisibleRootItem()
    
                    current_parent_id = None
                    p = item.parent()
                    if p:
                        current_parent_id = p.note_id
                    
                    same_parent = (current_parent_id == new_parent_id)
                    
                    row_idx = item.row()
                    taken_row = source_parent.takeRow(row_idx)
                    
                    final_insert_row = insert_row
                    if same_parent and row_idx < insert_row and insert_row != -1:
                         final_insert_row -= 1
                    
                    if final_insert_row != -1:
                         destination_parent.insertRow(final_insert_row, taken_row)
                         insert_row += 1 
                    else:
                         destination_parent.appendRow(taken_row)
        finally:
             self.layoutChanged.emit()
             self.refresh_icons()
             
        return True

