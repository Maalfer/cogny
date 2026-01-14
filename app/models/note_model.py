from PySide6.QtGui import QStandardItemModel, QIcon, QStandardItem
from PySide6.QtCore import Qt, QMimeData, QByteArray, QDataStream, QIODevice
from typing import Optional, Dict
from app.models.note_item import NoteItem

class NoteTreeModel(QStandardItemModel):
    def __init__(self, db_manager):
        super().__init__()
        self.db = db_manager
        self.setHorizontalHeaderLabels(["Notes"])
        self.note_items: Dict[int, NoteItem] = {}

    def load_notes(self):
        """Reloads the roots from the database (Lazy Loading)."""
        self.clear()
        self.setHorizontalHeaderLabels(["Notes"])
        self.note_items = {}
        
        conn = self.db._get_connection()
        cursor = conn.cursor()
        
        # 1. Get Roots (Now including is_folder)
        cursor.execute("SELECT id, title, is_folder FROM notes WHERE parent_id IS NULL ORDER BY title")
        roots = cursor.fetchall()
        
        # 2. Get Set of Parent IDs (to know which roots have children)
        # Faster than counting for each.
        cursor.execute("SELECT DISTINCT parent_id FROM notes WHERE parent_id IS NOT NULL")
        parents_with_children = {row[0] for row in cursor.fetchall()}
        
        conn.close()

        # 3. Create Root Items
        for r in roots:
            nid = r['id']
            title = r['title']
            is_folder = bool(r['is_folder'])
            
            # Pass is_folder to NoteItem
            item = NoteItem(nid, title, is_folder)
            self.note_items[nid] = item
            
            # Check if it has children -> Add Dummy
            # OR if it is explicitly a folder -> Add Dummy (to allow expansion even if empty? 
            # Well, if explicit folder is empty, we still want it to be expandable? 
            # Actually, standard behavior is folders are always expandable or show empty inside. 
            # If we don't add dummy, it won't have expand arrow.
            # So if is_folder is True, we add dummy if rowCount is 0?
            # Let's add dummy if (has_children OR is_folder) to allow attempting expansion.
            # But if fetch_children finds nothing for an explicit folder, we remove dummy and it shows empty.
            if nid in parents_with_children or is_folder:
                item.appendRow(QStandardItem("Loading..."))
                item.setData(True, Qt.UserRole + 1) # Custom Role: HasUnfetchedChildren
            
            self.invisibleRootItem().appendRow(item)
            
        # Update Icons
        self.refresh_icons()

    def fetch_children(self, parent_index):
        """Fetches children for a node if they haven't been loaded yet."""
        item = self.itemFromIndex(parent_index)
        if not item:
            return
            
        # Check flag
        if not item.data(Qt.UserRole + 1):
             return # Already loaded or no children
             
        # Clear Dummy "Loading..."
        if item.rowCount() > 0:
             item.removeRow(0)
        
        # Fetch Children
        conn = self.db._get_connection()
        cursor = conn.cursor()
        
        # Determine children
        pid = item.note_id
        cursor.execute("SELECT id, title, is_folder FROM notes WHERE parent_id = ? ORDER BY title", (pid,))
        children = cursor.fetchall()
        
        # Determine which children are also parents
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
            
        # Mark as fetched
        item.setData(False, Qt.UserRole + 1)
        self.refresh_icons()

    def refresh_icons(self):
        """Updates icons: Explicit Folders or Roots/Parents get Folder Icon."""
        folder_icon = QIcon.fromTheme("folder")
        subfolder_icon = QIcon.fromTheme("folder-documents", QIcon.fromTheme("folder")) 
        note_icon = QIcon.fromTheme("text-x-generic") 
        
        for item in list(self.note_items.values()):
            try:
                # helper to check if C++ object exists
                if not item.index().isValid() and item != self.invisibleRootItem():
                     pass

                # If explicit folder -> Folder Icon
                # If implicit folder (has children) -> Folder Icon (Backward compat/User preference)
                # If root -> Folder Icon (if desired, or just Note icon if it's a root note?)
                # User requested explicit folders.
                # Let's say: Is Folder -> Folder Icon.
                # Has Children -> Folder Icon (Implicit).
                # Else -> Note Icon.
                
                is_explicit_folder = getattr(item, 'is_folder', False)
                has_children = item.rowCount() > 0
                
                if is_explicit_folder or has_children:
                    item.setIcon(folder_icon)
                else:
                    item.setIcon(note_icon)
            except RuntimeError:
                # NoteItem already deleted
                continue

    def add_note(self, title: str, parent_id: Optional[int], is_folder: bool = False) -> int:
        new_id = self.db.add_note(title, parent_id, is_folder=is_folder)
        new_item = NoteItem(new_id, title, is_folder)
        self.note_items[new_id] = new_item
        
        # If it's a folder, give it a dummy item so it looks expandable?
        if is_folder:
             # We mark it as "loaded" initially but empty? 
             # Or "unfetched"?
             # Since we just added it, we know it's empty.
             # But to show arrow, we might need a dummy? 
             # No, empty folders don't have arrows usually.
             pass
        
        if parent_id is None:
            self.invisibleRootItem().appendRow(new_item)
        elif parent_id in self.note_items:
            parent = self.note_items[parent_id]
            parent.appendRow(new_item)
            # Ensure parent icon updates if it was a note
            self.refresh_icons()
            
        self.refresh_icons()
        return new_id
        
    def delete_note(self, note_id: int):
        if note_id in self.note_items:
            item = self.note_items[note_id]
            # Safety check
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
        # Check Explicit Folder OR Implicit Folder (Children)
        is_folder = getattr(item, 'is_folder', False) or self.rowCount(index) > 0
        
        if is_folder:
            return default_flags | Qt.ItemIsDropEnabled
            
        # Leaf nodes get standard flags (No DropEnabled -> Forces Insert/Reorder)
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
        destination_parent = target_item # Default: drop INTO target
        
        if target_item:
            # If dropping ONTO a note (parent is the note), check if it's a folder.
            is_folder = getattr(target_item, 'is_folder', False) or target_item.rowCount() > 0
            
            # If dropping ON leaf (not folder) and row is -1 (directly on item)
            # OR if it IS a folder but maybe user meant "insert between"?
            # Qt logic: dropping ON item means inside. Dropping BETWEEN items gives row != -1.
            
            if not is_folder and insert_row == -1:
                # User dropped ONTO a leaf node.
                # Instead of nesting (creating folder) or rejecting, 
                # we interpret this as "Put it BEFORE this note at the same level".
                
                # Redirect operation:
                destination_parent = target_item.parent() 
                if destination_parent is None:
                    # Parent is Root
                    destination_parent = self.invisibleRootItem()
                    new_parent_id = None
                else:
                    new_parent_id = destination_parent.note_id
                    
                # We want to insert at the position of the target_item
                # But wait, QAbstractItemModel.dropMimeData signature has 'row'.
                # If row is -1, it means "on the item".
                # We are converting "on item" to "insert at item's row".
                # Note: target_item is the item we dropped ON.
                insert_row = target_item.row()
                
                # Check circular (if we are moving a parent of target_item to here) happens later
            else:
                # Dropping into a Folder (or index invalid -> root)
                new_parent_id = target_item.note_id
        else:
            # Dropping on Root (empty area) calls dropMimeData with invalid parent
             destination_parent = self.invisibleRootItem()
             
        # Emit layout change to enforce view update and prevent visual glitches (disappearing items)
        self.layoutAboutToBeChanged.emit()
        
        try:
            while not stream.atEnd():
                note_id = stream.readInt32()
                
                # Avoid self-parenting or circular (simple check: can't move to self)
                if note_id == new_parent_id:
                    continue
    
                if note_id in self.note_items:
                    item = self.note_items[note_id]
                    
                    # Check for circular dependency (moving parent into child)
                    # We can traver up from new_parent to see if we hit note_id
                    check_item = target_item
                    is_circular = False
                    while check_item:
                        if check_item.note_id == note_id:
                            is_circular = True
                            break
                        check_item = check_item.parent()
                    
                    if is_circular:
                        continue
    
                    # 1. Update Database
                    self.db.move_note_to_parent(note_id, new_parent_id)
    
                    # 2. Update Model (Move Row)
                    source_parent = item.parent() or self.invisibleRootItem()
                    
                    # Need to verify destination_parent is not None (it shouldn't be with logic above)
                    if destination_parent is None:
                         destination_parent = self.invisibleRootItem()
    
                    # Only move if parent actually changed OR we are reordering in same parent?
                    # User wants "put on top", so reordering is key.
                    # Even if parent is same, we might need to move row.
                    
                    current_parent_id = None
                    p = item.parent()
                    if p:
                        current_parent_id = p.note_id
                    
                    # Check for same parent move
                    same_parent = (current_parent_id == new_parent_id)
                    
                    # Move Row
                    row_idx = item.row()
                    taken_row = source_parent.takeRow(row_idx)
                    
                    # If inserting at specific row
                    # Note: insert_row might need adjustment if we removed a row from same parent *before* the insertion point?
                    # Yes, if same parent and row_idx < insert_row, insert_row decreases by 1.
                    final_insert_row = insert_row
                    if same_parent and row_idx < insert_row and insert_row != -1:
                         final_insert_row -= 1
                    
                    if final_insert_row != -1:
                         destination_parent.insertRow(final_insert_row, taken_row)
                         # For next item in loop, increment insert_row if we want them sequential?
                         # Yes, otherwise they reverse order if inserting at fixed index.
                         insert_row += 1 
                    else:
                         destination_parent.appendRow(taken_row)
        finally:
             self.layoutChanged.emit()
             self.refresh_icons()
             
        return True
                     
        self.refresh_icons()

        return True

