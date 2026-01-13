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
        
        # Context Menu
        self.tree_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self.show_context_menu)
        
        self.splitter.addWidget(self.tree_view)

        # Right: Editor
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
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
        
        right_layout.addWidget(self.title_edit)
        right_layout.addWidget(self.text_editor)
        
        self.splitter.addWidget(right_widget)
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
            
            # 1. Rename Option (Always available)
            action_rename = QAction("Cambiar nombre", self)
            action_rename.triggered.connect(self.rename_note_dialog)
            menu.addAction(action_rename)
            
            # 2. Create New Note (Context Aware)
            # If Folder -> Create Child (Inside)
            # If Note -> Create Sibling (Next to it)
            
            is_folder = self.model.hasChildren(source_index)
            
            if is_folder:
                 action_new = QAction("Crear nueva nota", self)
                 action_new.setStatusTip("Crear una nota dentro de esta carpeta")
                 action_new.triggered.connect(self.add_child_note)
                 menu.addAction(action_new)
            else:
                 action_new = QAction("Crear nueva nota", self)
                 action_new.setStatusTip("Crear una nota al mismo nivel")
                 action_new.triggered.connect(self.add_sibling_note)
                 menu.addAction(action_new)

            # 3. Create Subnode (Explicit) - redundant if we have the above, but kept for clarity if needed
            # User request: "lo que quiero es que me cree una nota dentro de esa carpeta"
            # The above logic satisfies this.
            
            # We can keep "Crear carpeta" or "Create Subnode" if creating a specific folder type?
            # But notes are folders. So "Crear nueva nota" inside folder = New Child.
            
            # Let's remove the old explicit "Start subnode" if it's redundant, or rename it.
            # actually let's just use the logic above.
            
            menu.addSeparator()
            
            action_delete = QAction("Eliminar", self)
            action_delete.triggered.connect(self.delete_note)
            menu.addAction(action_delete)
        else:
            # Clicked on empty space -> New Root Note
            action_new_root = QAction("Crear nota raíz", self)
            action_new_root.triggered.connect(self.add_root_note)
            menu.addAction(action_new_root)
            
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

        self.act_new_child = QAction("Nueva Nota Hija", self)
        self.act_new_child.setStatusTip("Crear una nota hija para la nota seleccionada")
        self.act_new_child.triggered.connect(self.add_child_note)
        
        self.act_import_obsidian = QAction("Importar Bóveda Obsidian...", self)
        self.act_import_obsidian.setStatusTip("Importar una bóveda completa de Obsidian (Borra los datos actuales)")
        self.act_import_obsidian.triggered.connect(self.import_obsidian_vault)

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



    def create_menus(self):
        menubar = self.menuBar()

        # File Menu
        file_menu = menubar.addMenu("&Archivo")
        file_menu.addAction(self.act_new_root)
        file_menu.addAction(self.act_new_child)
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
        view_menu.addAction(self.act_zoom_in)
        view_menu.addAction(self.act_zoom_out)
        view_menu.addSeparator()
        view_menu.addAction(self.act_page_zoom_in)
        view_menu.addAction(self.act_page_zoom_out)
        
        # Tools Menu
        tools_menu = menubar.addMenu("&Herramientas")
        tools_menu.addAction(self.act_stats)
        tools_menu.addAction(self.act_theme)
        
        # Help Menu
        help_menu = menubar.addMenu("&Ayuda")
        help_menu.addAction(self.act_about)

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

    # ... (other methods) ...

    def create_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)
        
        style = self.style()
        
        # Spacer
        empty = QWidget()
        empty.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        # toolbar.addWidget(empty) # No spacer needed if it's the only thing? 
        # User said: "en esa fila quiero que solamente este el buscador de notas"
        # If I want it to take up the full width or just be there?
        # Usually search bars are on the right or take available space.
        # If it's the ONLY thing, maybe valid to just add it.
        # But `QToolBar` packs left.
        
        # Search Bar
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Buscar notas...")
        self.search_bar.textChanged.connect(self.on_search_text_changed)
        
        toolbar.addWidget(self.search_bar)
        
    def on_search_text_changed(self, text):
        if not text.strip():
            # Restore Tree View
            self.tree_view.setModel(self.proxy_model)
            self.tree_view.setRootIsDecorated(True)
            self.proxy_model.setFilterRegularExpression("") # Clear filter just in case
            # Reconnect Selection Model
            self.tree_view.selectionModel().currentChanged.connect(self.on_selection_changed)
        else:
            # Perform Ranked Search
            self.perform_search(text)

    def perform_search(self, text):
        search_model = QStandardItemModel()
        
        # Use FTS5 Search (Ranked by DB)
        results = self.db.search_notes_fts(text)
        
        # Result tuple from FTS: (rowid, title, rank)
        # Note: FTS rank is typically lower = better, but it depends on the function. 
        # Standard 'bm25' or default 'rank' function.
        # SQLite's default usually returns rank values where *smaller* is better relevance? 
        # Wait, the order is already ORDER BY rank.
        # Let's assume the DB returns them in correct order.
        
        # Icon for notes
        note_icon = QIcon.fromTheme("text-x-generic")
        
        for row in results:
            note_id = row[0]
            title = row[1]
            rank_score = row[2] # might be used for display?
            
            # Since title might be empty in FTS if not stored? 
            # We configured 'content=notes', so we retrieve from external table presumably?
            # actually we mapped: SELECT rowid, title... FROM notes_fts. 
            # If external content, it fetches from there correctly.
            
            item = QStandardItem(f"{title}")
            item.setEditable(False)
            item.note_id = note_id
            item.setIcon(note_icon)
            search_model.appendRow(item)
            
        self.tree_view.setModel(search_model)
        self.tree_view.setRootIsDecorated(False)
        # Reconnect Selection Model (New model = New Selection Model)
        self.tree_view.selectionModel().currentChanged.connect(self.on_selection_changed)

    def add_root_note(self):
        title, ok = ModernInput.get_text(self, "Nueva Nota", "Título de la Nota:")
        if ok and title:
            self.model.add_note(title, None)

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
        if hasattr(self, "progress_dialog"):
            self.progress_dialog.close()
            self.progress_dialog.deleteLater()
            self.progress_dialog = None
            
        if hasattr(self, "worker"):
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
        if hasattr(self, "progress_dialog"):
            self.progress_dialog.close()
            self.progress_dialog.deleteLater()
            self.progress_dialog = None
            
        if hasattr(self, "worker"):
            self.worker.quit()
            self.worker.wait()
            self.worker.deleteLater()
            self.worker = None
            
        ModernAlert.show(self, "Error de Importación", f"Ocurrió un error: {error_msg}")

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

    def on_selection_changed(self, current, previous):
        # Auto-save previous note if active
        if self.current_note_id is not None:
             self.save_current_note()
             
        if not current.isValid():
            self.current_note_id = None
            self.title_edit.clear()
            self.text_editor.clear()
            self.title_edit.setReadOnly(True)
            self.text_editor.setReadOnly(True)
            return

        # Determine if we are in Proxy Model (Tree) or Standard Model (Search)
        model = self.tree_view.model()
        
        if isinstance(model, QSortFilterProxyModel):
            # Map Proxy Index to Source Index
            source_index = self.proxy_model.mapToSource(current)
            if not source_index.isValid():
                return
            item = self.model.itemFromIndex(source_index)
        else:
            # Standard Model (Search Results)
            item = model.itemFromIndex(current)
            
        if not item:
            # Defensive check fixes AttributeError: 'NoneType' object has no attribute 'note_id'
            return
            
        self.current_note_id = item.note_id
        
        # Check if it has children (Folder Behavior)
        if item.rowCount() > 0:
            # It is a folder
            self.title_edit.setPlainText(item.text())
            self.title_edit.setReadOnly(True) # Cannot edit title of folder from here? User said "cannot write in them".
            
            # Show placeholder in editor
            self.text_editor.setHtml(f"<h1 style='color: gray; text-align: center; margin-top: 50px;'>Carpeta: {item.text()}</h1><p style='color: gray; text-align: center;'>Selecciona una sub-nota para editar.</p>")
            self.text_editor.setReadOnly(True)
            
            # Ensure it's expanded? User said "click displays notes inside".
            # on_tree_clicked handles toggle, but selection via arrow keys might not.
            # Let's enforce expansion on selection? Maybe annoying if navigating.
            # Stick to on_tree_clicked for expansion toggle.
            return

        # It is a Note (Leaf)
        self.title_edit.setReadOnly(False)
        self.text_editor.setReadOnly(False)
        
        note = self.db.get_note(item.note_id)
        if note:
             self.title_edit.setPlainText(note[2])
             # Update current_note_id in editor BEFORE setting text, so if they paste immediately it works
             self.text_editor.current_note_id = self.current_note_id
             
             content = note[3] if note[3] else ""
             
             # Check if content is likely Raw Markdown (imported) vs Rich Text HTML (saved by app)
             # "Rich Text" usually starts with <!DOCTYPE HTML> ...
             if content.strip() and not content.lstrip().startswith("<!DOCTYPE HTML"):
                 # It's likely raw markdown. 
                 
                 # 1. Convert Markdown Horizontal Rules (---, ***, ___) to HTML <hr>
                 import re
                 # Multiline mode to match start/end of lines
                 content = re.sub(r'(?m)^[-*_]{3,}\s*$', '<hr>', content)
                 
                 # 2. Wrap it to preserve newlines/indentation in setHtml
                 # We assume it might have <img> tags from the importer
                 formatted_content = f'<div style="white-space: pre-wrap;">{content}</div>'
                 self.text_editor.setHtml(formatted_content)
             else:
                 self.text_editor.setHtml(content)

    def on_tree_clicked(self, index):
        """Toggle expansion on single click."""
        if self.tree_view.isExpanded(index):
            self.tree_view.collapse(index)
        else:
            self.tree_view.expand(index)
