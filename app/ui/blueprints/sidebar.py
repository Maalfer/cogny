from PySide6.QtWidgets import QWidget, QVBoxLayout, QTreeView, QMenu, QSplitter
from PySide6.QtCore import Qt, Signal, QSortFilterProxyModel
from PySide6.QtGui import QAction, QIcon
from app.ui.widgets import ModernInput, ModernAlert, ModernConfirm
from app.models.note_model import NoteTreeModel

class Sidebar(QWidget):
    note_selected = Signal(int)
    action_requested = Signal(str, object) # action_name, args

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Tree View
        self.tree_view = QTreeView()
        self.model = NoteTreeModel(self.db)
        self.model.load_notes()

        # Proxy Model for Search/Filtering
        self.proxy_model = QSortFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.model)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.proxy_model.setRecursiveFilteringEnabled(True)

        self.tree_view.setModel(self.proxy_model)
        self.tree_view.setHeaderHidden(True)
        self.tree_view.setUniformRowHeights(True)
        
        # Signals
        self.tree_view.selectionModel().currentChanged.connect(self.on_selection_changed)
        self.tree_view.clicked.connect(self.on_tree_clicked)
        self.tree_view.expanded.connect(self.on_tree_expanded)

        # Drag and Drop
        self.tree_view.setDragEnabled(True)
        self.tree_view.setAcceptDrops(True)
        self.tree_view.setDragDropMode(QTreeView.InternalMove)
        self.tree_view.setDefaultDropAction(Qt.MoveAction)
        
        self.model.rowsMoved.connect(self.on_rows_moved)
        
        # Context Menu
        self.tree_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self.show_context_menu)
        
        layout.addWidget(self.tree_view)

    def on_selection_changed(self, current, previous):
        # Notify parent about selection change to trigger load/save
        index = self.tree_view.currentIndex()
        if not index.isValid():
            index = current
        
        if not index.isValid():
             return

        # Check if we are in Search Mode (different model)
        current_model = self.tree_view.model()
        if current_model != self.proxy_model:
            # Search Result Model (StandardItemModel)
            item = current_model.itemFromIndex(index)
            if item and hasattr(item, 'note_id'):
                self.note_selected.emit(item.note_id)
            return

        source_index = self.proxy_model.mapToSource(index)
        item = self.model.itemFromIndex(source_index)
        
        if not item:
            return

        self.note_selected.emit(item.note_id)

    def on_tree_clicked(self, index):
        if self.tree_view.isExpanded(index):
            self.tree_view.collapse(index)
        else:
            self.tree_view.expand(index)

    def on_tree_expanded(self, index):
        source_index = self.proxy_model.mapToSource(index)
        self.model.fetch_children(source_index)

    def on_rows_moved(self, parent, start, end, destination, row):
        if destination.isValid():
            proxy_dest = self.proxy_model.mapFromSource(destination)
            self.tree_view.expand(proxy_dest)

    def show_context_menu(self, position):
        index = self.tree_view.indexAt(position)
        menu = QMenu()

        if index.isValid():
            self.tree_view.setCurrentIndex(index)
            source_index = self.proxy_model.mapToSource(index)
            item = self.model.itemFromIndex(source_index)
            
            # 1. Rename Option
            action_rename = QAction("Cambiar nombre", self)
            action_rename.triggered.connect(self.rename_note_dialog)
            menu.addAction(action_rename)
            
            # 2. Creation Actions
            is_folder = getattr(item, 'is_folder', False) or item.rowCount() > 0
            
            if is_folder:
                action_create = QAction("Crear nota en esta carpeta", self)
                action_create.triggered.connect(self.add_child_note)
            else:
                action_create = QAction("Crear nota (mismo nivel)", self)
                action_create.triggered.connect(self.add_sibling_note)
            menu.addAction(action_create)

            if is_folder:
                 action_create_folder = QAction("Crear subcarpeta", self)
                 action_create_folder.triggered.connect(self.add_child_folder)
            else:
                 action_create_folder = QAction("Crear carpeta (mismo nivel)", self)
                 action_create_folder.triggered.connect(self.add_sibling_folder)
            menu.addAction(action_create_folder)

            menu.addSeparator()
            
            action_delete = QAction("Eliminar", self)
            action_delete.triggered.connect(self.delete_note)
            menu.addAction(action_delete)
            
            if not is_folder:
                menu.addSeparator()
                
                action_export = QAction("Exportar a PDF", self)
                action_export.triggered.connect(lambda: self.action_requested.emit("export_pdf", item.note_id))
                menu.addAction(action_export)
        else:
            action_new_root = QAction("Crear nota raíz", self)
            action_new_root.triggered.connect(self.add_root_note)
            menu.addAction(action_new_root)
            
            action_new_folder = QAction("Crear carpeta raíz", self)
            action_new_folder.triggered.connect(self.add_root_folder)
            menu.addAction(action_new_folder)
            
        menu.exec(self.tree_view.viewport().mapToGlobal(position))

    def rename_note_dialog(self):
        index = self.tree_view.currentIndex()
        if not index.isValid(): return
            
        source_index = self.proxy_model.mapToSource(index)
        item = self.model.itemFromIndex(source_index)
        if not item: return
            
        old_name = item.text()
        new_name, ok = ModernInput.get_text(self, "Cambiar nombre", "Nuevo nombre:", text=old_name)
        
        if ok and new_name.strip():
            item.setText(new_name.strip())
            self.db.update_note_title(item.note_id, new_name.strip())

    def add_sibling_note(self):
        index = self.tree_view.currentIndex()
        if not index.isValid():
            self.add_root_note()
            return

        source_index = self.proxy_model.mapToSource(index)
        item = self.model.itemFromIndex(source_index)
        
        parent = item.parent()
        parent_id = None
        if parent and hasattr(parent, "note_id"):
             parent_id = parent.note_id
        
        title, ok = ModernInput.get_text(self, "Nueva nota", "Título de la nota:")
        if ok and title.strip():
            self.model.add_note(title.strip(), parent_id)

    def add_child_note(self):
        index = self.tree_view.currentIndex()
        if not index.isValid():
            ModernAlert.show(self, "Sin Selección", "Por favor seleccione una nota padre primero.")
            return

        source_index = self.proxy_model.mapToSource(index)
        item = self.model.itemFromIndex(source_index)
        
        title, ok = ModernInput.get_text(self, "Nueva Nota", "Título de la Nota:")
        if ok and title:
            self.model.add_note(title, item.note_id)
            self.tree_view.expand(index)

    def add_child_folder(self):
        index = self.tree_view.currentIndex()
        if not index.isValid():
            ModernAlert.show(self, "Sin Selección", "Por favor seleccione un elemento padre primero.")
            return

        source_index = self.proxy_model.mapToSource(index)
        item = self.model.itemFromIndex(source_index)
        
        title, ok = ModernInput.get_text(self, "Nueva Subcarpeta", "Nombre de la Subcarpeta:")
        if ok and title:
            self.model.add_note(title, item.note_id, is_folder=True)
            self.tree_view.expand(index)

    def add_sibling_folder(self):
        index = self.tree_view.currentIndex()
        if not index.isValid():
            self.add_root_folder()
            return
            
        source_index = self.proxy_model.mapToSource(index)
        item = self.model.itemFromIndex(source_index)
        
        parent = item.parent()
        parent_id = None
        if parent and hasattr(parent, "note_id"):
             parent_id = parent.note_id
        
        title, ok = ModernInput.get_text(self, "Nueva Carpeta", "Nombre de la Carpeta:")
        if ok and title:
            self.model.add_note(title, parent_id, is_folder=True)

    def add_root_note(self):
        title, ok = ModernInput.get_text(self, "Nueva Nota", "Título de la Nota:")
        if ok and title:
            self.model.add_note(title, None)

    def add_root_folder(self):
        title, ok = ModernInput.get_text(self, "Nueva Carpeta", "Nombre de la Carpeta:")
        if ok and title:
            self.model.add_note(title, None, is_folder=True)

    def delete_note(self):
        index = self.tree_view.currentIndex()
        if not index.isValid(): return
            
        ret = ModernConfirm.show(self, "Confirmar Eliminación", "¿Eliminar esta nota y todos sus hijos?", "Sí", "Cancelar")
        
        if ret:
            source_index = self.proxy_model.mapToSource(index)
            item = self.model.itemFromIndex(source_index)
            
            # Signal before deletion to clear editor if needed
            self.action_requested.emit("note_deleted", item.note_id)

            self.db.delete_note(item.note_id)
            self.model.delete_note(item.note_id)

    def select_note(self, note_id):
        if not note_id: return
        
        if note_id in self.model.note_items:
            item = self.model.note_items[note_id]
            source_index = item.index()
            proxy_index = self.proxy_model.mapFromSource(source_index)
            
            if proxy_index.isValid():
                self.tree_view.setCurrentIndex(proxy_index)
                self.tree_view.scrollTo(proxy_index)

