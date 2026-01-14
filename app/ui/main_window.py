from PySide6.QtWidgets import (QMainWindow, QSplitter, QVBoxLayout, QToolBar, 
                               QSizePolicy, QApplication, QProgressDialog, QStyle, QMenu)
from PySide6.QtGui import QAction, QKeySequence, QIcon, QFont, QPalette
from PySide6.QtCore import Qt, QSettings, QTimer

from app.database.manager import DatabaseManager
from app.ui.themes import ThemeManager
from app.ui.widgets import ModernInfo, ModernAlert, ModernConfirm, ThemeSettingsDialog
from app.ui.buscador import SearchManager
from app.ui.barra_herramientas import FormatToolbar

# Blueprints
from app.ui.blueprints.sidebar import Sidebar
from app.ui.blueprints.editor_area import EditorArea
from app.ui.blueprints.workers import ImportWorker, ExportWorker, OptimizeWorker
from app.ui.blueprints.markdown import MarkdownRenderer

class MainWindow(QMainWindow):
    def __init__(self, db_path="notes.cdb"):
        super().__init__()
        self.setWindowTitle("Cogny")
        self.resize(1200, 800)
        
        # Resolve Assets Path
        import os
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        icon_path = os.path.join(base_dir, "assets", "logo.png")
        self.setWindowIcon(QIcon(icon_path))

        # Database Setup
        self.db = DatabaseManager(db_path)
        # Note: Model is now inside Sidebar, but we might need access or not.
        
        self.setup_ui()

    def setup_ui(self):
        # Central Widget
        self.splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(self.splitter)

        # 1. Sidebar Blueprint
        self.sidebar = Sidebar(self.db, self)
        self.sidebar.note_selected.connect(self.on_sidebar_note_selected)
        self.sidebar.action_requested.connect(self.on_sidebar_action)
        self.splitter.addWidget(self.sidebar)

        # 2. Editor Blueprint
        self.editor_area = EditorArea(self.db, self)
        self.editor_area.status_message.connect(self.on_editor_status)
        self.splitter.addWidget(self.editor_area)
        
        self.splitter.setSizes([300, 700])

        # Create Actions and Menus
        self.create_actions()
        self.create_menus()
        self.create_toolbar()
        
        # Restore State
        self.restore_state()

    def closeEvent(self, event):
        settings = QSettings()
        if self.editor_area.current_note_id is not None:
             settings.setValue("last_note_id", self.editor_area.current_note_id)
        else:
             settings.remove("last_note_id")
             
        super().closeEvent(event)

    def restore_state(self):
        settings = QSettings()
        last_id = settings.value("last_note_id", type=int)
        
        # We need to tell Sidebar to select this note
        # But Sidebar's model load is async? No, it's inside init currently.
        if last_id:
             self.sidebar.select_note(last_id)


    def on_sidebar_note_selected(self, note_id):
        # Auto-save previous if needed (EditorArea handles save logic call, but we might want to trigger it before switch?)
        # EditorArea.load_note calls save? No. Sidebar emits selection changed.
        # Logic: 
        # 1. Save current note in EditorArea
        self.editor_area.save_current_note()
        # 2. Load new note
        self.editor_area.load_note(note_id)
        
        # Check if it was a folder logic: Sidebar might have checked it? 
        # EditorArea handles checking is_folder inside load_note (we implemented that).

    def on_sidebar_action(self, action, arg):
        if action == "export_pdf":
            self.export_note_pdf(arg)
        elif action == "note_deleted":
            # Check if current note was deleted
            if self.editor_area.current_note_id == arg:
                self.editor_area.clear()

    def on_editor_status(self, msg, timeout):
        if timeout > 0:
            self.statusBar().showMessage(msg, timeout)
        else:
            self.statusBar().showMessage(msg)
            if not msg: self.statusBar().clearMessage()

    def create_actions(self):
        # File Actions
        self.act_new_root = QAction("Nueva Nota Raíz", self)
        self.act_new_root.triggered.connect(self.sidebar.add_root_note)

        self.act_new_folder_root = QAction("Nueva Carpeta Raíz", self)
        self.act_new_folder_root.triggered.connect(self.sidebar.add_root_folder)

        self.act_new_child = QAction("Nueva Nota Hija", self)
        self.act_new_child.triggered.connect(self.sidebar.add_child_note)
        
        self.act_new_folder_child = QAction("Nueva Carpeta Hija", self)
        self.act_new_folder_child.triggered.connect(self.sidebar.add_child_folder)
        
        self.act_import_obsidian = QAction("Importar Bóveda Obsidian...", self)
        self.act_import_obsidian.triggered.connect(self.import_obsidian_vault)

        self.act_export_obsidian = QAction("Exportar a Obsidian...", self)
        self.act_export_obsidian.triggered.connect(self.export_obsidian_vault)

        self.act_attach = QAction("Adjuntar Archivo...", self)
        self.act_attach.triggered.connect(self.editor_area.attach_file)

        self.act_save = QAction("Guardar Nota", self)
        self.act_save.setShortcut(QKeySequence.Save)
        self.act_save.triggered.connect(self.on_save_triggered)

        self.act_exit = QAction("Salir", self)
        self.act_exit.setShortcut(QKeySequence.Quit)
        self.act_exit.triggered.connect(self.close)

        # Edit Actions (Delegated to text_editor)
        self.act_undo = QAction("Deshacer", self)
        self.act_undo.setShortcut(QKeySequence.Undo)
        self.act_undo.triggered.connect(self.editor_area.text_editor.undo)

        self.act_redo = QAction("Rehacer", self)
        self.act_redo.setShortcut(QKeySequence.Redo)
        self.act_redo.triggered.connect(self.editor_area.text_editor.redo)

        self.act_cut = QAction("Cortar", self)
        self.act_cut.setShortcut(QKeySequence.Cut)
        self.act_cut.triggered.connect(self.editor_area.text_editor.cut)

        self.act_copy = QAction("Copiar", self)
        self.act_copy.setShortcut(QKeySequence.Copy)
        self.act_copy.triggered.connect(self.editor_area.text_editor.copy)

        self.act_paste = QAction("Pegar", self)
        self.act_paste.setShortcut(QKeySequence.Paste)
        self.act_paste.triggered.connect(self.editor_area.text_editor.paste)

        self.act_delete = QAction("Eliminar Nota", self)
        self.act_delete.setShortcut(QKeySequence.Delete)
        self.act_delete.triggered.connect(self.sidebar.delete_note)
        
        # View Actions
        self.act_zoom_in = QAction("Zoom Texto (+)", self)
        self.act_zoom_in.setShortcut(QKeySequence.ZoomIn)
        self.act_zoom_in.triggered.connect(lambda _: self.editor_area.text_editor.textZoomIn())
        
        self.act_zoom_out = QAction("Zoom Texto (-)", self)
        self.act_zoom_out.setShortcut(QKeySequence.ZoomOut)
        self.act_zoom_out.triggered.connect(lambda _: self.editor_area.text_editor.textZoomOut())
        
        self.act_page_zoom_in = QAction("Zoom Imagen (+)", self)
        self.act_page_zoom_in.setShortcut(QKeySequence("Ctrl+Shift++"))
        self.act_page_zoom_in.triggered.connect(lambda _: self.editor_area.text_editor.imageZoomIn())
        
        self.act_page_zoom_out = QAction("Zoom Imagen (-)", self)
        self.act_page_zoom_out.setShortcut(QKeySequence("Ctrl+Shift+-"))
        self.act_page_zoom_out.triggered.connect(lambda _: self.editor_area.text_editor.imageZoomOut())

        # Tools Actions
        self.act_theme = QAction("Tema", self)
        self.act_theme.triggered.connect(self.show_theme_dialog)
        
        self.act_about = QAction("Acerca de", self)
        self.act_about.triggered.connect(self.show_about)

    def on_save_triggered(self):
        title = self.editor_area.save_current_note()
        if title and self.editor_area.current_note_id:
             # Need to update sidebar title in tree?
             # Sidebar model might need refresh or manual update.
             # Ideally sidebar listens to DB changes or we call a method.
             # We can't access model item easily here. 
             # Let's rely on Sidebar refreshing or simple "Reload" logic if needed.
             # Or we can notify sidebar.
             pass

    def create_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)
        
        # Search Bar
        # We need to link SearchManager to Sidebar's tree and model
        self.search_manager = SearchManager(self.db, self.sidebar.tree_view, self.sidebar.proxy_model, self.sidebar.on_selection_changed)
        toolbar.addWidget(self.search_manager.get_widget())
        
        self.addToolBarBreak() 
        
        self.editor_toolbar = FormatToolbar(self, self.editor_area.text_editor)
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
        
        self.act_toggle_toolbar = QAction("Barra de Formato", self, checkable=True)
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
        
        action_import_obsidian = QAction("Importar Obsidian...", self)
        action_import_obsidian.triggered.connect(self.import_obsidian_vault)
        tools_menu.addAction(action_import_obsidian)

        action_export_obsidian = QAction("Exportar a Obsidian...", self)
        action_export_obsidian.triggered.connect(self.export_obsidian_vault)
        tools_menu.addAction(action_export_obsidian)
        
        action_optimize = QAction("Optimizar Base de Datos", self)
        action_optimize.triggered.connect(self.optimize_database_action)
        tools_menu.addAction(action_optimize)
        
        # Help Menu
        help_menu = menubar.addMenu("&Ayuda")
        help_menu.addAction(self.act_about)

    def toggle_editor_toolbar(self, checked):
        self.editor_toolbar.setVisible(checked)

    def show_theme_dialog(self):
        if ThemeSettingsDialog.show_dialog(self):
            settings = QSettings()
            new_theme = settings.value("theme", "Dark")
            self.switch_theme(new_theme)

    def switch_theme(self, theme_name):
        settings = QSettings()
        sidebar_bg = settings.value("theme_custom_sidebar_bg", "")
        
        # App Palette
        QApplication.instance().setPalette(ThemeManager.get_palette(theme_name, sidebar_bg))
        
        # Update components
        self.editor_area.switch_theme(theme_name)
        
        self.statusBar().showMessage(f"Tema cambiado a {theme_name}", 2000)

    # --- Workers delegation ---

    def import_obsidian_vault(self):
        from PySide6.QtWidgets import QFileDialog
        
        ret = ModernConfirm.show(self, "Confirmar Importación", 
                                  "Importar una Bóveda de Obsidian BORRARÁ todas las notas actuales.\n\n¿Estás seguro de que quieres continuar?",
                                  "Sí", "Cancelar")
        if not ret: return

        vault_path = QFileDialog.getExistingDirectory(self, "Seleccionar Bóveda de Obsidian")
        if not vault_path: return

        self.progress_dialog = QProgressDialog("Importando Bóveda...", "Cancelar", 0, 0, self)
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setCancelButton(None)
        self.progress_dialog.show()

        self.worker = ImportWorker(self.db, vault_path)
        self.worker.progress.connect(self.progress_dialog.setLabelText)
        self.worker.finished.connect(self.on_import_finished)
        self.worker.error.connect(self.on_worker_error)
        self.worker.start()

    def on_import_finished(self):
        if self.progress_dialog: self.progress_dialog.close()
        self.clean_worker()
        self.sidebar.model.load_notes()
        self.editor_area.clear()
        QTimer.singleShot(100, lambda: ModernInfo.show(self, "Éxito", "¡Bóveda importada correctamente!"))

    def export_obsidian_vault(self):
        from PySide6.QtWidgets import QFileDialog
        
        output_path = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta de Destino para Exportar")
        if not output_path: return

        self.progress_dialog = QProgressDialog("Exportando Bóveda...", "Cancelar", 0, 0, self)
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setCancelButton(None)
        self.progress_dialog.show()

        self.worker = ExportWorker(self.db, output_path)
        self.worker.progress.connect(self.progress_dialog.setLabelText)
        self.worker.finished.connect(self.on_export_finished)
        self.worker.error.connect(self.on_worker_error)
        self.worker.start()

    def on_export_finished(self):
        if self.progress_dialog: self.progress_dialog.close()
        self.clean_worker()
        QTimer.singleShot(100, lambda: ModernInfo.show(self, "Éxito", "¡Bóveda exportada correctamente!"))

    def optimize_database_action(self):
        self.progress_dialog = QProgressDialog("Optimizando Base de Datos...", None, 0, 0, self)
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setCancelButton(None)
        self.progress_dialog.setRange(0, 0)
        self.progress_dialog.show()

        self.worker = OptimizeWorker(self.db)
        self.worker.finished.connect(self.on_optimize_finished)
        self.worker.error.connect(self.on_worker_error)
        self.worker.start()

    def on_optimize_finished(self):
        if self.progress_dialog: self.progress_dialog.close()
        self.clean_worker()
        QTimer.singleShot(100, lambda: ModernInfo.show(self, "Éxito", "Optimización completada."))

    def on_worker_error(self, error_msg):
        if self.progress_dialog: self.progress_dialog.close()
        self.clean_worker()
        ModernAlert.show(self, "Error", f"Ocurrió un error: {error_msg}")

    def clean_worker(self):
        if hasattr(self, "worker") and self.worker:
            self.worker.quit()
            self.worker.wait()
            self.worker.deleteLater()
            self.worker = None
        self.progress_dialog = None

    def export_note_pdf(self, note_id):
        # ... Reuse PDF export logic calling PDFExporter ...
        # Since it was inline, we can move it here or to a helper.
        # It needs UI (FileDialog) so MainWindow or EditorArea?
        # Let's keep it here but use MarkdownRenderer.
        try:
            note_data = self.db.get_note(note_id)
            if not note_data:
                ModernAlert.show(self, "Error", "No se pudo recuperar la nota.")
                return
            
            title = note_data['title']
            content = note_data['content']
            
            processed_content = MarkdownRenderer.process_markdown_content(content)
            
            from PySide6.QtWidgets import QFileDialog
            import os
            
            default_name = f"{title}.pdf"
            default_name = "".join([c for c in default_name if c.isalpha() or c.isdigit() or c in (' ', '.', '-', '_')]).strip()
            
            path, _ = QFileDialog.getSaveFileName(self, "Guardar PDF", 
                                                os.path.join(os.path.expanduser("~"), default_name), 
                                                "Archivos PDF (*.pdf)")
            
            if not path: return
            if not path.endswith('.pdf'): path += '.pdf'
                
            from app.exporters.pdf_exporter import PDFExporter
            
            settings = QSettings()
            current_theme = settings.value("theme", "Dark")
            
            exporter = PDFExporter(self.db)
            exporter.export_to_pdf(title, content, path, theme_name=current_theme)
            
            ModernInfo.show(self, "Éxito", f"Nota exportada correctamente a:\n{path}")
            
        except Exception as e:
            ModernAlert.show(self, "Error de Exportación", str(e))

    def show_about(self):
        ModernInfo.show(self, "Acerca de", "Cogny\n\nUna aplicación jerárquica para tomar notas.\nConstruida con PySide6 y SQLite.")
