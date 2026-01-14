from PySide6.QtWidgets import (QMainWindow, QTreeView, QTextEdit, QPlainTextEdit,
                               QSplitter, QWidget, QVBoxLayout, QToolBar, 
                               QMessageBox, QInputDialog, QLineEdit, QStyle, QMenu, QSizePolicy)
from PySide6.QtGui import QAction, QKeySequence, QPalette, QColor, QIcon, QStandardItemModel, QStandardItem
from PySide6.QtWidgets import QApplication, QProgressDialog
from PySide6.QtCore import Qt, QSettings, QSortFilterProxyModel, QThread, Signal, QObject

from app.database.manager import DatabaseManager
from app.models.note_model import NoteTreeModel
from app.ui.highlighter import MarkdownHighlighter
from app.ui.editor import NoteEditor
from app.ui.themes import ThemeManager
from app.ui.widgets import TitleEditor, ModernInfo, ModernAlert, ModernConfirm, ModernInput
from app.ui.buscador import SearchManager

class MainWindow(QMainWindow):
    def __init__(self, db_path="notes.cdb"):
        super().__init__()
        self.setWindowTitle("Cogny") # Rebrand
        self.resize(1200, 800)
        
        # Resolve Assets Path
        import os
        # Assuming structure:
        #  - Source: root/app/ui/main_window.py
        #  - Install: site-packages/app/ui/main_window.py
        #  - Assets: site-packages/assets
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        # If running from source (root/app/ui/...), base_dir is root/app/.., i.e. root/app? No.
        # root/app/ui/../.. = root. OK.
        # If running from site-packages/app/ui/../.. = site-packages. OK.
        
        icon_path = os.path.join(base_dir, "assets", "logo.png")
        self.setWindowIcon(QIcon(icon_path))

        # Database Setup
        self.db = DatabaseManager(db_path)
        self.model = NoteTreeModel(self.db)
        self.model.load_notes()

        self.current_note_id = None
        self.setup_ui()

    def setup_ui(self):
        # Central Widget
        self.splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(self.splitter)

        # Left: Tree View
        self.tree_view = QTreeView()
        
        # Proxy Model for Search/Filtering
        self.proxy_model = QSortFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.model)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.proxy_model.setRecursiveFilteringEnabled(True)
        
        self.tree_view.setModel(self.proxy_model)
        self.tree_view.setHeaderHidden(True)
        self.tree_view.setUniformRowHeights(True) # Performance Optimization
        self.tree_view.selectionModel().currentChanged.connect(self.on_selection_changed)
        # Expand/Collapse on single click as requested
        self.tree_view.clicked.connect(self.on_tree_clicked)
        
        # Enable Drag and Drop
        self.tree_view.setDragEnabled(True)
        self.tree_view.setAcceptDrops(True)
        self.tree_view.setDragDropMode(QTreeView.InternalMove)
        self.tree_view.setDefaultDropAction(Qt.MoveAction)
        
        # Connect to Model's rowsMoved signal for auto-expansion
        self.model.rowsMoved.connect(self.on_rows_moved)
        
        # Lazy Loading Connection
        self.tree_view.expanded.connect(self.on_tree_expanded)
        
        # Context Menu
        self.tree_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self.show_context_menu)
        
        self.splitter.addWidget(self.tree_view)

        # Custom Title Edit to handle Enter key
        # TitleEditor is imported globally
        self.title_edit = TitleEditor()
        self.title_edit.setObjectName("TitleEdit")
        self.title_edit.setPlaceholderText("Título")
        
        # Style Title: Big & Bold
        from PySide6.QtGui import QFont
        title_font = QFont()
        title_font.setPointSize(24)
        title_font.setBold(True)
        self.title_edit.setFont(title_font)
        # self.title_edit.setStyleSheet("...") # Moved to themes.py for consistency
        
        # Event filter to jump to body on Enter is built-in to TitleEditor class I'll create
        self.title_edit.return_pressed.connect(lambda: self.text_editor.setFocus())
        
        self.text_editor = NoteEditor(self.db)
        
        # Load theme setting for editor
        settings = QSettings()
        current_theme = settings.value("theme", "Dark")
        self.text_editor.apply_theme(current_theme)

        self.highlighter = MarkdownHighlighter(self.text_editor.document())
        self.highlighter.set_theme(current_theme) # Initialize with correct theme colors
        self.text_editor.highlighter = self.highlighter  # Link for Live Preview logic
        
        # Right Side is now a Vertical Splitter to allow resizing Title vs Content
        self.right_splitter = QSplitter(Qt.Vertical)
        self.right_splitter.addWidget(self.title_edit)
        self.right_splitter.addWidget(self.text_editor)
        
        # Set initial sizes (Title small, Content huge)
        self.right_splitter.setSizes([80, 700])
        # self.right_splitter.setCollapsible(0, False) # Can we collapse title? Maybe user wants to hide it.
        
        # Add Right Splitter to Main Splitter
        self.splitter.addWidget(self.right_splitter)
        self.splitter.setSizes([300, 700])

        # Create Actions and Menus
        # Create Actions and Menus
        self.create_actions()
        self.create_menus()
        self.create_toolbar()
        
        # Restore State
        self.restore_state()

    def closeEvent(self, event):
        # Save current note ID
        settings = QSettings()
        if self.current_note_id is not None:
             settings.setValue("last_note_id", self.current_note_id)
        else:
             settings.remove("last_note_id")
             
        super().closeEvent(event)

    def restore_state(self):
        settings = QSettings()
        last_id = settings.value("last_note_id", type=int)
        
        if last_id and last_id in self.model.note_items:
            item = self.model.note_items[last_id]
            source_index = item.index()
            # Map Source Index to Proxy Index
            proxy_index = self.proxy_model.mapFromSource(source_index)
            
            if proxy_index.isValid():
                self.tree_view.setCurrentIndex(proxy_index)
                self.tree_view.scrollTo(proxy_index)

    def show_context_menu(self, position):
        index = self.tree_view.indexAt(position)
        menu = QMenu()

        if index.isValid():
            # Select the item implicitly for better UX
            self.tree_view.setCurrentIndex(index)
            
            # Use Source Index for logic
            source_index = self.proxy_model.mapToSource(index)
            item = self.model.itemFromIndex(source_index)
            
            # 1. Rename Option
            action_rename = QAction("Cambiar nombre", self)
            action_rename.triggered.connect(self.rename_note_dialog)
            menu.addAction(action_rename)
            
            # 2. Creation Actions
            is_folder = getattr(item, 'is_folder', False) or item.rowCount() > 0
            
            # Create Note (Child if folder, Sibling if note)
            if is_folder:
                action_create = QAction("Crear nota en esta carpeta", self)
                action_create.triggered.connect(self.add_child_note)
            else:
                action_create = QAction("Crear nota (mismo nivel)", self)
                action_create.triggered.connect(self.add_sibling_note)
            menu.addAction(action_create)

            # Create Folder (Child if folder, Sibling if note)
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
            
            menu.addSeparator()
            
            # Export Action
            action_export = QAction("Exportar a PDF", self)
            action_export.triggered.connect(lambda: self.export_note_pdf(item.note_id))
            menu.addAction(action_export)
        else:
            # Clicked on empty space
            action_new_root = QAction("Crear nota raíz", self)
            action_new_root.triggered.connect(self.add_root_note)
            menu.addAction(action_new_root)
            
            action_new_folder = QAction("Crear carpeta raíz", self)
            action_new_folder.triggered.connect(self.add_root_folder)
            menu.addAction(action_new_folder)
            
        menu.exec(self.tree_view.viewport().mapToGlobal(position))

    def rename_note_dialog(self):
        index = self.tree_view.currentIndex()
        if not index.isValid():
            return
            
        # Map to source
        source_index = self.proxy_model.mapToSource(index)
        item = self.model.itemFromIndex(source_index)
        if not item: 
            return
            
        old_name = item.text()
        new_name, ok = ModernInput.get_text(self, "Cambiar nombre", "Nuevo nombre:", text=old_name)
        
        if ok and new_name.strip():
            # Update Model (and DB via save logic if needed, but model update usually enough in-memory?)
            # Wait, item.setText updates the view, but we need to update DB.
            # Does item.setData update DB? No, manually unless we hook itemChanged.
            item.setText(new_name.strip())
            
            # Update DB immediately
            self.db.update_note_title(item.note_id, new_name.strip())
            
            # Note: Content isn't changed, but updated_at should update?
            # update_note_title method needed in DB manager or just use update_note.
            # Let's use update_note but we need content.
            # Fetch content first? Or add specialized method.
            # Optimization: update_note_title.

    def add_sibling_note(self):
        index = self.tree_view.currentIndex()
        if not index.isValid():
            self.add_root_note()
            return

        source_index = self.proxy_model.mapToSource(index)
        item = self.model.itemFromIndex(source_index)
        
        parent = item.parent()
        parent_id = None
        if parent:
             # It's a child of someone
             if hasattr(parent, "note_id"):
                 parent_id = parent.note_id
             # Else it's root item (None id)
        
        title, ok = ModernInput.get_text(self, "Nueva nota", "Título de la nota:")
        if ok and title.strip():
            self.model.add_note(title.strip(), parent_id)

    def add_child_note_context(self):
        # Deprecated by direct connection to add_child_note after setting selection
        pass

    def create_actions(self):
        # File Actions
        self.act_new_root = QAction("Nueva Nota Raíz", self)
        self.act_new_root.setStatusTip("Crear una nueva nota de nivel raíz")
        self.act_new_root.triggered.connect(self.add_root_note)

        self.act_new_folder_root = QAction("Nueva Carpeta Raíz", self)
        self.act_new_folder_root.setStatusTip("Crear una nueva carpeta de nivel raíz")
        self.act_new_folder_root.triggered.connect(self.add_root_folder)

        self.act_new_child = QAction("Nueva Nota Hija", self)
        self.act_new_child.setStatusTip("Crear una nota hija para la nota seleccionada")
        self.act_new_child.triggered.connect(self.add_child_note)
        
        self.act_new_folder_child = QAction("Nueva Carpeta Hija", self)
        self.act_new_folder_child.setStatusTip("Crear una carpeta hija")
        self.act_new_folder_child.triggered.connect(self.add_child_folder)
        
        self.act_import_obsidian = QAction("Importar Bóveda Obsidian...", self)
        self.act_import_obsidian.setStatusTip("Importar una bóveda completa de Obsidian (Borra los datos actuales)")
        self.act_import_obsidian.triggered.connect(self.import_obsidian_vault)

        self.act_export_obsidian = QAction("Exportar a Obsidian...", self)
        self.act_export_obsidian.setStatusTip("Exportar la bóveda actual a formato Obsidian")
        self.act_export_obsidian.triggered.connect(self.export_obsidian_vault)

        self.act_attach = QAction("Adjuntar Archivo...", self)
        self.act_attach.setStatusTip("Adjuntar un archivo a la nota actual")
        self.act_attach.triggered.connect(self.attach_file)

        self.act_save = QAction("Guardar Nota", self)
        self.act_save.setShortcut(QKeySequence.Save)
        self.act_save.setStatusTip("Guardar la nota actual")
        self.act_save.triggered.connect(self.save_current_note)

        self.act_exit = QAction("Salir", self)
        self.act_exit.setShortcut(QKeySequence.Quit)
        self.act_exit.setStatusTip("Salir de la aplicación")
        self.act_exit.triggered.connect(self.close)

        # Edit Actions
        self.act_undo = QAction("Deshacer", self)
        self.act_undo.setShortcut(QKeySequence.Undo)
        self.act_undo.triggered.connect(self.text_editor.undo)

        self.act_redo = QAction("Rehacer", self)
        self.act_redo.setShortcut(QKeySequence.Redo)
        self.act_redo.triggered.connect(self.text_editor.redo)

        self.act_cut = QAction("Cortar", self)
        self.act_cut.setShortcut(QKeySequence.Cut)
        self.act_cut.triggered.connect(self.text_editor.cut)

        self.act_copy = QAction("Copiar", self)
        self.act_copy.setShortcut(QKeySequence.Copy)
        self.act_copy.triggered.connect(self.text_editor.copy)

        self.act_paste = QAction("Pegar", self)
        self.act_paste.setShortcut(QKeySequence.Paste)
        self.act_paste.triggered.connect(self.text_editor.paste)

        self.act_delete = QAction("Eliminar Nota", self)
        self.act_delete.setShortcut(QKeySequence.Delete)
        self.act_delete.setStatusTip("Eliminar la nota seleccionada")
        self.act_delete.triggered.connect(self.delete_note)
        
        # View Actions
        self.act_zoom_in = QAction("Zoom Texto (+)", self)
        self.act_zoom_in.setShortcut(QKeySequence.ZoomIn)
        self.act_zoom_in.setStatusTip("Aumentar solo el tamaño del texto")
        self.act_zoom_in.triggered.connect(lambda _: self.text_editor.textZoomIn())
        
        self.act_zoom_out = QAction("Zoom Texto (-)", self)
        self.act_zoom_out.setShortcut(QKeySequence.ZoomOut)
        self.act_zoom_out.setStatusTip("Disminuir solo el tamaño del texto")
        self.act_zoom_out.triggered.connect(lambda _: self.text_editor.textZoomOut())
        
        # Page Zoom Actions (Text + Images) - Renaming to "Image Zoom"
        self.act_page_zoom_in = QAction("Zoom Imagen (+)", self)
        self.act_page_zoom_in.setShortcut(QKeySequence("Ctrl+Shift++"))
        self.act_page_zoom_in.setStatusTip("Aumentar solo el tamaño de las imágenes")
        self.act_page_zoom_in.triggered.connect(lambda _: self.text_editor.imageZoomIn())
        
        self.act_page_zoom_out = QAction("Zoom Imagen (-)", self)
        self.act_page_zoom_out.setShortcut(QKeySequence("Ctrl+Shift+-"))
        self.act_page_zoom_out.setStatusTip("Disminuir solo el tamaño de las imágenes")
        self.act_page_zoom_out.triggered.connect(lambda _: self.text_editor.imageZoomOut())

        # Tools Actions
        self.act_stats = QAction("Estadísticas", self)
        self.act_stats.triggered.connect(self.show_statistics)

        self.act_theme = QAction("Tema", self)
        self.act_theme.setStatusTip("Cambiar entre tema Claro y Oscuro")
        self.act_theme.triggered.connect(self.show_theme_dialog)


        # Help Actions
        self.act_about = QAction("Acerca de", self)
        self.act_about.triggered.connect(self.show_about)



    def create_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)
        
        style = self.style()
        
        # Spacer
        empty = QWidget()
        empty.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        
        # Search Bar
        from app.ui.buscador import SearchManager 
        from app.ui.barra_herramientas import FormatToolbar
        self.search_manager = SearchManager(self.db, self.tree_view, self.proxy_model, self.on_selection_changed)
        toolbar.addWidget(self.search_manager.get_widget())
        
        # --- Editor Toolbar (Secondary) ---
        self.addToolBarBreak() # Force next toolbar to next line
        

        self.editor_toolbar = FormatToolbar(self, self.text_editor)
        self.addToolBar(self.editor_toolbar)

    def create_menus(self):
        menubar = self.menuBar()

        # File Menu
        file_menu = menubar.addMenu("&Archivo")
        file_menu.addAction(self.act_new_root)
        file_menu.addAction(self.act_new_folder_root)
        file_menu.addSeparator()
        file_menu.addAction(self.act_new_child)
        file_menu.addAction(self.act_new_folder_child)
        file_menu.addSeparator()
        file_menu.addAction(self.act_import_obsidian)
        file_menu.addSeparator()
        file_menu.addAction(self.act_attach)
        file_menu.addSeparator()
        file_menu.addAction(self.act_save)
        file_menu.addSeparator()
        file_menu.addAction(self.act_exit)

        # Edit Menu
        edit_menu = menubar.addMenu("&Editar")
        edit_menu.addAction(self.act_undo)
        edit_menu.addAction(self.act_redo)
        edit_menu.addSeparator()
        edit_menu.addAction(self.act_cut)
        edit_menu.addAction(self.act_copy)
        edit_menu.addAction(self.act_paste)
        edit_menu.addSeparator()
        edit_menu.addAction(self.act_delete)
        
        # View Menu
        view_menu = menubar.addMenu("&Ver")
        
        # Toolbar Toggle
        self.act_toggle_toolbar = QAction("Barra de Formato", self, checkable=True)
        self.act_toggle_toolbar.setStatusTip("Mostrar/Ocultar barra de herramientas de formato")
        self.act_toggle_toolbar.setChecked(True)
        self.act_toggle_toolbar.triggered.connect(self.toggle_editor_toolbar)
        view_menu.addAction(self.act_toggle_toolbar)
        view_menu.addSeparator()
        
        view_menu.addAction(self.act_zoom_in)
        view_menu.addAction(self.act_zoom_out)
        view_menu.addSeparator()
        view_menu.addAction(self.act_page_zoom_in)
        view_menu.addAction(self.act_page_zoom_out)
        
        # Tools Menu
        tools_menu = menubar.addMenu("&Herramientas")
        tools_menu.addAction(self.act_theme)
        
        # Importar...
        action_import_obsidian = QAction("Importar Obsidian...", self)
        action_import_obsidian.triggered.connect(self.import_obsidian_vault)
        tools_menu.addAction(action_import_obsidian)

        action_export_obsidian = QAction("Exportar a Obsidian...", self)
        action_export_obsidian.triggered.connect(self.export_obsidian_vault)
        tools_menu.addAction(action_export_obsidian)
        
        action_optimize = QAction("Optimizar Base de Datos", self)
        action_optimize.setStatusTip("Compactar y optimizar la base de datos (Reducir tamaño)")
        action_optimize.triggered.connect(self.optimize_database_action)
        tools_menu.addAction(action_optimize)
        
        # Help Menu
        help_menu = menubar.addMenu("&Ayuda")
        help_menu.addAction(self.act_about)
        
        # Statistics (Moved to Help)
        action_stats = QAction("Estadísticas", self)
        action_stats.triggered.connect(self.show_statistics)
        help_menu.addAction(action_stats)

    def toggle_editor_toolbar(self, checked):
        self.editor_toolbar.setVisible(checked)

    def show_theme_dialog(self):
        from app.ui.widgets import ThemeSettingsDialog
        if ThemeSettingsDialog.show_dialog(self):
            # Dialog handles saving to QSettings. We just need to apply.
            # We can get the new theme name from settings.
            settings = QSettings()
            new_theme = settings.value("theme", "Dark")
            self.switch_theme(new_theme)

    def switch_theme(self, theme_name):
        settings = QSettings()
        # Retrieve custom colors
        sidebar_bg = settings.value("theme_custom_sidebar_bg", "")
        editor_bg = settings.value("theme_custom_editor_bg", "")
        
        # Update App Palette
        QApplication.instance().setPalette(ThemeManager.get_palette(theme_name, sidebar_bg))
        # Update Editor
        self.text_editor.apply_theme(theme_name, editor_bg)
             
        # Update Highlighter
        if hasattr(self, "highlighter"):
             self.highlighter.set_theme(theme_name)
        
        # Save Preference
        # Already saved by Dialog, but good for direct calls
        settings.setValue("theme", theme_name)
        
        # Update Status
        self.statusBar().showMessage(f"Tema cambiado a {theme_name}", 2000)


    def add_root_note(self):
        title, ok = ModernInput.get_text(self, "Nueva Nota", "Título de la Nota:")
        if ok and title:
            self.model.add_note(title, None)

    def add_root_folder(self):
        title, ok = ModernInput.get_text(self, "Nueva Carpeta", "Nombre de la Carpeta:")
        if ok and title:
            self.model.add_note(title, None, is_folder=True)

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
        if parent:
             if hasattr(parent, "note_id"):
                 parent_id = parent.note_id
        
        title, ok = ModernInput.get_text(self, "Nueva Carpeta", "Nombre de la Carpeta:")
        if ok and title:
            self.model.add_note(title, parent_id, is_folder=True)

    def add_child_note(self):
        index = self.tree_view.currentIndex()
        if not index.isValid():
            ModernAlert.show(self, "Sin Selección", "Por favor seleccione una nota padre primero.")
            return

        # Map Proxy Index to Source Index
        source_index = self.proxy_model.mapToSource(index)
        item = self.model.itemFromIndex(source_index)
        
        title, ok = ModernInput.get_text(self, "Nueva Nota", "Título de la Nota:")
        if ok and title:
            self.model.add_note(title, item.note_id)
            self.tree_view.expand(index)

            self.tree_view.expand(index)

    def attach_file(self):
        if self.current_note_id is None:
            ModernAlert.show(self, "Sin Selección", "Por favor seleccione una nota para adjuntar el archivo.")
            return

        from PySide6.QtWidgets import QFileDialog
        import os
        
        path, _ = QFileDialog.getOpenFileName(self, "Adjuntar Archivo")
        if not path:
            return
            
        filename = os.path.basename(path)
        try:
            with open(path, 'rb') as f:
                data = f.read()
            
            att_id = self.db.add_attachment(self.current_note_id, filename, data)
            self.text_editor.insert_attachment(att_id, filename)
            
            
        except Exception as e:
            ModernAlert.show(self, "Error", f"No se pudo adjuntar el archivo: {e}")

            self.text_editor.insert_attachment(att_id, filename)
            
            
        except Exception as e:
            ModernAlert.show(self, "Error", f"No se pudo adjuntar el archivo: {e}")



    def delete_note(self):
        index = self.tree_view.currentIndex()
        self.delete_note_at_index(index)

    def delete_note_at_index(self, index):
        if not index.isValid():
            return
            
        ret = ModernConfirm.show(self, "Confirmar Eliminación", "¿Eliminar esta nota y todos sus hijos?", 
                                   "Sí", "Cancelar")
        
        if ret:
            # Map Proxy Index to Source Index for Deletion
            source_index = self.proxy_model.mapToSource(index)
            item = self.model.itemFromIndex(source_index)
            
            self.db.delete_note(item.note_id)
            self.model.delete_note(item.note_id)
            
            if self.current_note_id == item.note_id:
                self.title_edit.clear()
                self.text_editor.clear()
                self.current_note_id = None

    def save_current_note(self):
        if self.current_note_id is None:
            return

        title = self.title_edit.toPlainText()
        content = self.text_editor.toHtml()
        
        import re
        
        # Cleanup Images
        image_ids = []
        matches = re.findall(r'src="image://db/(\d+)"', content)
        for m in matches:
             try:
                 image_ids.append(int(m))
             except ValueError:
                 pass
        
        # Cleanup Attachments
        att_ids = []
        # Matches href="attachment://123"
        att_matches = re.findall(r'href="attachment://(\d+)"', content)
        for m in att_matches:
             try:
                 att_ids.append(int(m))
             except ValueError:
                 pass

        self.db.update_note(self.current_note_id, title, content)
        
        self.db.cleanup_images(self.current_note_id, image_ids)
        self.db.cleanup_attachments(self.current_note_id, att_ids)
        
        if self.current_note_id in self.model.note_items:
             self.model.note_items[self.current_note_id].setText(title)
             
        self.statusBar().showMessage("Guardado.", 2000)

    class ImportWorker(QThread):
        progress = Signal(str)
        finished = Signal()
        error = Signal(str)

        def __init__(self, db_manager, vault_path):
            super().__init__()
            self.db = db_manager
            self.vault_path = vault_path

        def run(self):
            try:
                from app.importers.obsidian import ObsidianImporter
                importer = ObsidianImporter(self.db)
                importer.import_vault(self.vault_path, progress_callback=self.progress.emit)
                self.finished.emit()
            except Exception as e:
                self.error.emit(str(e))

    class ExportWorker(QThread):
        progress = Signal(str)
        finished = Signal()
        error = Signal(str)

        def __init__(self, db_manager, output_path):
            super().__init__()
            self.db = db_manager
            self.output_path = output_path

        def run(self):
            try:
                from app.exporters.obsidian_exporter import ObsidianExporter
                exporter = ObsidianExporter(self.db)
                exporter.export_vault(self.output_path, progress_callback=self.progress.emit)
                self.finished.emit()
            except Exception as e:
                self.error.emit(str(e))

    class OptimizeWorker(QThread):
        finished = Signal()
        error = Signal(str)

        def __init__(self, db_manager):
            super().__init__()
            self.db = db_manager

        def run(self):
            try:
                self.db.optimize_database()
                self.finished.emit()
            except Exception as e:
                self.error.emit(str(e))

    def import_obsidian_vault(self):
        from PySide6.QtWidgets import QFileDialog
        
        # Confirmation
        ret = ModernConfirm.show(self, "Confirmar Importación", 
                                  "Importar una Bóveda de Obsidian BORRARÁ todas las notas actuales.\n\n¿Estás seguro de que quieres continuar?",
                                  "Sí", "Cancelar")
        if not ret:
            return

        vault_path = QFileDialog.getExistingDirectory(self, "Seleccionar Bóveda de Obsidian")
        if not vault_path:
            return

        # Setup Progress Dialog
        self.progress_dialog = QProgressDialog("Importando Bóveda...", "Cancelar", 0, 0, self)
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setCancelButton(None) # Disable cancel for now as it's unsafe to stop mid-transaction easily
        self.progress_dialog.show()

        # Setup Worker
        self.worker = self.ImportWorker(self.db, vault_path)
        self.worker.progress.connect(self.update_import_progress)
        self.worker.finished.connect(self.on_import_finished)
        self.worker.error.connect(self.on_import_error)
        
        self.worker.start()

    def update_import_progress(self, message):
        self.progress_dialog.setLabelText(message)

    def on_import_finished(self):
        if hasattr(self, "progress_dialog") and self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog.deleteLater()
            self.progress_dialog = None
            
        if hasattr(self, "worker") and self.worker:
            self.worker.quit()
            self.worker.wait()
            self.worker.deleteLater()
            self.worker = None
            
        self.model.load_notes()
        self.current_note_id = None
        self.title_edit.clear()
        self.text_editor.clear()
        
        # Show success message slightly delayed to ensure UI refresh
        from PySide6.QtCore import QTimer
        QTimer.singleShot(100, lambda: ModernInfo.show(self, "Éxito", "¡Bóveda importada correctamente!"))

    def on_import_error(self, error_msg):
        if hasattr(self, "progress_dialog") and self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog.deleteLater()
            self.progress_dialog = None
            
        if hasattr(self, "worker") and self.worker:
            self.worker.quit()
            self.worker.wait()
            self.worker.deleteLater()
            self.worker = None
            
        ModernAlert.show(self, "Error de Importación", f"Ocurrió un error: {error_msg}")

    def export_obsidian_vault(self):
        from PySide6.QtWidgets import QFileDialog
        
        output_path = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta de Destino para Exportar")
        if not output_path:
            return

        # Setup Progress Dialog
        self.progress_dialog = QProgressDialog("Exportando Bóveda...", "Cancelar", 0, 0, self)
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setCancelButton(None) 
        self.progress_dialog.show()

        # Setup Worker
        self.export_worker = self.ExportWorker(self.db, output_path)
        self.export_worker.progress.connect(self.update_export_progress)
        self.export_worker.finished.connect(self.on_export_finished)
        self.export_worker.error.connect(self.on_export_error)
        
        self.export_worker.start()

    def update_export_progress(self, message):
        if self.progress_dialog:
            self.progress_dialog.setLabelText(message)

    def on_export_finished(self):
        if hasattr(self, "progress_dialog") and self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog.deleteLater()
            self.progress_dialog = None
            
        if hasattr(self, "export_worker") and self.export_worker:
            self.export_worker.quit()
            self.export_worker.wait()
            self.export_worker.deleteLater()
            self.export_worker = None
            
        from PySide6.QtCore import QTimer
        QTimer.singleShot(100, lambda: ModernInfo.show(self, "Éxito", "¡Bóveda exportada correctamente!"))

    def on_export_error(self, error_msg):
        if hasattr(self, "progress_dialog") and self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog.deleteLater()
            self.progress_dialog = None
            
        if hasattr(self, "export_worker") and self.export_worker:
            self.export_worker.quit()
            self.export_worker.wait()
            self.export_worker.deleteLater()
            self.export_worker = None
            
        ModernAlert.show(self, "Error de Exportación", f"Ocurrió un error: {error_msg}")

    def optimize_database_action(self):
        # Setup Progress Dialog (Spinner)
        self.progress_dialog = QProgressDialog("Optimizando Base de Datos...", None, 0, 0, self)
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setCancelButton(None)
        self.progress_dialog.setRange(0, 0) # Infinite spinner
        self.progress_dialog.show()

        self.optimize_worker = self.OptimizeWorker(self.db)
        self.optimize_worker.finished.connect(self.on_optimize_finished)
        self.optimize_worker.error.connect(self.on_optimize_error)
        self.optimize_worker.start()

    def on_optimize_finished(self):
        if hasattr(self, "progress_dialog") and self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog.deleteLater()
            self.progress_dialog = None
            
        if hasattr(self, "optimize_worker") and self.optimize_worker:
            self.optimize_worker.quit()
            self.optimize_worker.wait()
            self.optimize_worker.deleteLater()
            self.optimize_worker = None
            
        from PySide6.QtCore import QTimer
        QTimer.singleShot(100, lambda: ModernInfo.show(self, "Éxito", "Optimización y reparación completada correctamente.\nEl tamaño del archivo se ha reducido y se han corregido posibles errores."))

    def on_optimize_error(self, error_msg):
        if hasattr(self, "progress_dialog") and self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog.deleteLater()
            self.progress_dialog = None
            
        if hasattr(self, "optimize_worker") and self.optimize_worker:
            self.optimize_worker.quit()
            self.optimize_worker.wait()
            self.optimize_worker.deleteLater()
            self.optimize_worker = None
            
        ModernAlert.show(self, "Error", f"Error al optimizar: {error_msg}")
            
        ModernAlert.show(self, "Error de Exportación", f"Ocurrió un error: {error_msg}")

    def show_statistics(self):
        stats = self.db.get_detailed_statistics()
        
        msg = (
            f"<b>Notas Totales:</b> {stats['total_notes']}<br>"
            f"<b>Sub-notas Totales:</b> {stats['total_subnotes']}<br>"
            f"<b>Imágenes Totales:</b> {stats['total_images']}<br>"
            f"<b>Fragmentos de Código Totales:</b> {stats['total_code_fragments']}<br>"
            f"<b>Palabras Totales:</b> {stats['total_words']}<br>"
            f"<b>Letras Totales:</b> {stats['total_letters']}"
        )
        ModernInfo.show(self, "Estadísticas", msg)

    def show_about(self):
        ModernInfo.show(self, "Acerca de", "Cogni\n\nUna aplicación jerárquica para tomar notas.\nConstruida con PySide6 y SQLite.")

    def on_rows_moved(self, parent, start, end, destination, row):
        """Auto-expand the destination folder when a note is dropped into it."""
        # destination is the QModelIndex of the NEW parent (SOURCE MODEL INDEX).
        if destination.isValid():
            # Map Source Index back to Proxy Index to expand in View
            proxy_dest = self.proxy_model.mapFromSource(destination)
            self.tree_view.expand(proxy_dest)


    class NoteLoaderWorker(QThread):
        finished = Signal(dict)
        error = Signal(str)

        def __init__(self, db_manager, note_id):
            super().__init__()
            self.db = db_manager
            self.note_id = note_id
            self.is_cancelled = False

        def run(self):
            if self.is_cancelled: return
            try:
                # 1. Fetch Note
                note = self.db.get_note(self.note_id)
                if not note: 
                    self.finished.emit(None)
                    return
                
                if self.is_cancelled: return

                # 2. Pre-process content (simulate or perform heavy regex)
                title = note[2]
                content = note[3] if note[3] else ""
                
                result = {
                    "note_id": self.note_id,
                    "title": title,
                    "content": content,
                    "is_markdown": False,
                    "processed_content": content
                }
                
                # Check format
                if content.strip() and not content.lstrip().startswith("<!DOCTYPE HTML"):
                    result["is_markdown"] = True
                    # We return raw content and let main thread process it or helper
                    pass 

                self.finished.emit(result)
            except Exception as e:
                self.error.emit(str(e))

        def cancel(self):
            self.is_cancelled = True

    def on_selection_changed(self, current, previous):
        # Auto-save previous note if active
        if self.current_note_id is not None:
             self.save_current_note()

        # Cancel previous loader if running
        if hasattr(self, "note_loader") and self.note_loader and self.note_loader.isRunning():
            self.note_loader.cancel()
            self.note_loader.wait(50) # Wait brief time, then ignore
            self.note_loader.deleteLater()
            self.note_loader = None
            
        index = self.tree_view.currentIndex()
        if not index.isValid():
            # Try to get from selection model directly if index is invalid
             index = current
             
        if not index.isValid():
             return

        # Map Proxy Index to Source Index
        source_index = self.proxy_model.mapToSource(index)
        item = self.model.itemFromIndex(source_index)
        
        # If using Search Model (no proxy mapping needed if it's not the main model)
        if not item:
            # Maybe search model?
            model = index.model()
            if isinstance(model, QSortFilterProxyModel):
                 source_index = model.mapToSource(index)
                 item = self.model.itemFromIndex(source_index)
            else:
                 # Standard Model (Search Results)
                 item = model.itemFromIndex(current) if current.isValid() else None
            
        if not item:
            return
            
        self.current_note_id = item.note_id
        
        # Check Explicit Folder OR Implicit Folder (Children)
        is_explicit_folder = getattr(item, 'is_folder', False)
        
        if is_explicit_folder or item.rowCount() > 0:
            # It is a folder (Explicit or Implicit)
            self.title_edit.setPlainText(item.text())
            self.title_edit.setReadOnly(True) 
            self.text_editor.setHtml(f"<h1 style='color: gray; text-align: center; margin-top: 50px;'>Carpeta: {item.text()}</h1><p style='color: gray; text-align: center;'>Esta es una carpeta. Crea o selecciona una nota dentro de ella.</p>")
            self.text_editor.setReadOnly(True)
            return

        # It is a Note (Leaf)
        self.title_edit.setReadOnly(False)
        self.text_editor.setReadOnly(False)
        self.text_editor.clear_image_cache() 
        
        # UI State: Loading
        self.statusBar().showMessage(f"Cargando nota: {item.text()}...", 0)
        self.title_edit.setPlainText("Cargando...")
        self.text_editor.setHtml("<h2 style='color: gray; text-align: center;'>Cargando contenido...</h2>")
        
        # Start Worker
        self.note_loader = self.NoteLoaderWorker(self.db, item.note_id)
        self.note_loader.finished.connect(self.on_note_loaded)
        self.note_loader.start()

    def on_note_loaded(self, result):
        self.statusBar().clearMessage()
        
        if not result or result["note_id"] != self.current_note_id:
            # Result stale or empty
            return
            
        self.title_edit.setPlainText(result["title"])
        self.text_editor.current_note_id = result["note_id"]
        
        content = result["content"]
        
        if result["is_markdown"]:
             content = self.process_markdown_content(content)
             if content != self.text_editor.toHtml():
                 formatted = f'<div style="white-space: pre-wrap;">{content}</div>'
                 self.text_editor.blockSignals(True)
                 try:
                     self.text_editor.setHtml(formatted)
                 finally:
                     self.text_editor.blockSignals(False)
                 self.text_editor.update_code_block_visuals()
        else:
             self.text_editor.setHtml(content)

    def on_tree_clicked(self, index):
        """Toggle expansion on single click."""
        if self.tree_view.isExpanded(index):
            self.tree_view.collapse(index)
        else:
            self.tree_view.expand(index)
            
    def on_tree_expanded(self, index):
        """Lazy Load children when expanded."""
        # Convert Proxy Index to Source Index
        source_index = self.proxy_model.mapToSource(index)
        self.model.fetch_children(source_index)

    def process_markdown_content(self, text):
        """
        Hybrid Rendering:
        - Code Blocks (```): Protected, escaped.
        - Tables: Rendered as HTML <table>.
        - Internal Images/Attachments: Preserved (Not escaped).
        - Text: Escaped (Raw Markdown view).
        """
        import html
        import re
        import uuid
        
        # 1. Protect Internal HTML (Images & Attachments)
        # We replace them with unique placeholders so they survive html.escape()
        # Pattern 1: Images <img src="image://db/123" />
        # Pattern 2: Attachments &nbsp;<span...>...</a>&nbsp; based on importer format
        
        # Dictionary to store placeholders
        placeholders = {}
        
        def preserve_match(match):
            token = f"__INTERNAL_HTML_PLACEHOLDER_{uuid.uuid4().hex}__"
            placeholders[token] = match.group(0)
            return token
            
        # Regex for Image
        text = re.sub(r'<img src="image://db/\d+"\s*/>', preserve_match, text)
        
        # Regex for Attachment (Approximate match for the specific format generated by obsidian.py)
        # &nbsp;<span style="font-size: 16px;">📎</span>&nbsp;<a href="attachment://...</a>&nbsp;
        # We can be a bit looser to match 'attachment://' hrefs if we trust the source.
        # But let's try to match the anchor tag at least.
        text = re.sub(r'<a href="attachment://\d+".*?>.*?</a>', preserve_match, text)
        # Also preserve the span icon if strict match needed?
        # Simpler: <span...📎</span> handles the icon.
        text = re.sub(r'&nbsp;<span.*?>📎</span>&nbsp;', preserve_match, text)
        text = re.sub(r'&nbsp;', preserve_match, text) # Warning: this might be too aggressive? 
        # Actually, the entire block is: &nbsp;<span...>📎</span>&nbsp;<a ...>...</a>&nbsp;
        # Let's match roughly known internal patterns.
        
        # Better approach for attachments: Just preserve <a href="attachment://...">...</a>
        # And <span...>📎</span>
        text = re.sub(r'<span[^>]*>📎</span>', preserve_match, text)

        # 2. Protect Code Blocks
        # ... (rest of logic) ...
        parts = re.split(r'(```[\s\S]*?```)', text)
        processed_parts = []
        
        for part in parts:
            if part.startswith("```") and part.endswith("```"):
                # Code Block: Escape everything (including placeholders? No, code should show raw placeholders? 
                # Ideally code block shouldn't contain internal HTML unless user typed it. 
                # If we escape code block, placeholders trigger later restoration? 
                # Restoration happens at END. So if code block has placeholder, it gets restored to HTML.
                # This means if I type <img..> in code block, it renders! 
                # FIX: Verify if match was inside code block before? 
                # Complexity: High.
                # Alternative: Do Code Block Splitting FIRST. Then Protect Internal HTML only in NON-CODE parts.
                processed_parts.append(html.escape(part))
            else:
                # Normal Text (or Internal HTML contexts)
                # PROTECT INTERNAL HTML HERE, NOT GLOBALLY
                
                # Apply placeholders to this part only
                def preserve_match_local(match):
                    token = f"__INTERNAL_HTML_PLACEHOLDER_{uuid.uuid4().hex}__"
                    placeholders[token] = match.group(0)
                    return token
                
                # Patterns
                part = re.sub(r'<img src="image://db/\d+"\s*/>', preserve_match_local, part)
                part = re.sub(r'<a href="attachment://\d+".*?>.*?</a>', preserve_match_local, part)
                part = re.sub(r'<span[^>]*>📎</span>', preserve_match_local, part)
                # We skip separate &nbsp; handling for simplicity, html.escape handles nbsp? No, keeps &nbsp? 
                # html.escape escapes &, so &nbsp; -> &amp;nbsp;.
                # Revert &amp;nbsp; later?
                part = re.sub(r'&nbsp;', preserve_match_local, part)
                
                # Scan for tables ...
                lines = part.split('\n')
                in_table = False
                table_lines = []
                final_lines = []
                
                for line in lines:
                    stripped = line.strip()
                    # Placeholder-safe check: placeholders shouldn't affect table detection if they don't contain pipes or newlines.
                    # UUIDs are safe.
                    
                    is_table_line = stripped.startswith('|') and (stripped.endswith('|') or len(stripped.split('|')) > 1)
                    
                    if is_table_line:
                        in_table = True
                        table_lines.append(line)
                    else:
                        if in_table:
                             final_lines.append(self.render_markdown_table(table_lines))
                             table_lines = []
                             in_table = False
                        
                        final_lines.append(html.escape(line))
                        
                if in_table:
                     final_lines.append(self.render_markdown_table(table_lines))
                     
                processed_parts.append('\n'.join(final_lines))
                
        content = "".join(processed_parts)
        content = re.sub(r'(?m)^[-*_]{3,}\s*$', '<hr>', content)
        
        # 3. Restore Placeholders
        for token, original in placeholders.items():
            content = content.replace(token, original)
            
        return content

    def render_markdown_table(self, lines):
        """Converts list of markdown table lines to HTML table."""
        if len(lines) < 2:
            import html
            return "\n".join([html.escape(l) for l in lines])
            
        import html
        
        html_out = ['<table border="1" cellspacing="0" cellpadding="5">']
        
        # 1. Header
        header_row = lines[0].strip().strip('|').split('|')
        html_out.append("<thead><tr>")
        for h in header_row:
             html_out.append(f"<th>{html.escape(h.strip())}</th>")
        html_out.append("</tr></thead>")
        
        # 2. Body
        html_out.append("<tbody>")
        
        # Skip separator line (line 1) usually "---|---|---"
        start_idx = 1
        if len(lines) > 1 and '---' in lines[1]:
            start_idx = 2
            
        for i in range(start_idx, len(lines)):
            row = lines[i].strip().strip('|').split('|')
            html_out.append("<tr>")
            for cell in row:
                html_out.append(f"<td>{html.escape(cell.strip())}</td>")
            html_out.append("</tr>")
            
        html_out.append("</tbody></table>")
        return "".join(html_out)

    def export_note_pdf(self, note_id):
        """Exports the selected note to PDF."""
        # 1. Fetch Note Data
        try:
            note_data = self.db.get_note(note_id)
            if not note_data:
                ModernAlert.show(self, "Error", "No se pudo recuperar la nota.")
                return
                
            title = note_data['title']
            content = note_data['content']
            
            # Process Content (Markdown -> HTML)
            # We reuse process_markdown_content to ensure consistent rendering (tables, etc.)
            processed_content = self.process_markdown_content(content)
            
            # 2. Ask User for Save Location
            from PySide6.QtWidgets import QFileDialog
            import os
            
            default_name = f"{title}.pdf"
            # Sanitize filename
            default_name = "".join([c for c in default_name if c.isalpha() or c.isdigit() or c in (' ', '.', '-', '_')]).strip()
            
            path, _ = QFileDialog.getSaveFileName(self, "Guardar PDF", 
                                                os.path.join(os.path.expanduser("~"), default_name), 
                                                "Archivos PDF (*.pdf)")
            
            if not path:
                return
                
            if not path.endswith('.pdf'):
                path += '.pdf'
                
            # 3. Export
            from app.exporters.pdf_exporter import PDFExporter
            
            # Get Current Theme
            settings = QSettings()
            current_theme = settings.value("theme", "Dark")
            
            exporter = PDFExporter(self.db)
            # Pass RAW content, let exporter handle rendering
            exporter.export_to_pdf(title, content, path, theme_name=current_theme)
            
            ModernInfo.show(self, "Éxito", f"Nota exportada correctamente a:\n{path}")
            
        except Exception as e:
            ModernAlert.show(self, "Error de Exportación", str(e))

    def export_database(self):
        ModernInfo.show(self, "Próximamente", "La exportación de la base de datos estará disponible en una futura actualización.")

    def show_statistics(self):
        ModernInfo.show(self, "Próximamente", "Las estadísticas estarán disponibles en una futura actualización.")

    def show_about(self):
        ModernInfo.show(self, "Acerca de Cogny", "Cogny - Tu Segundo Cerebro\nVersión 0.3-alpha\n\nDesarrollado con PySide6 y SQLite.")

