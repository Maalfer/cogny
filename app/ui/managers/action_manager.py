from PySide6.QtGui import QAction, QKeySequence, QIcon
from PySide6.QtCore import QSettings, QThread, Signal, Qt
from PySide6.QtWidgets import QFileDialog, QToolBar, QProgressDialog
from app.ui.widgets import ModernInfo, ModernAlert
import os
from datetime import datetime

class PDFExportWorker(QThread):
    finished = Signal(bool, str)

    def __init__(self, title, content, path, theme_name, fm):
        super().__init__()
        self.title = title
        self.content = content
        self.path = path
        self.theme_name = theme_name
        self.fm = fm

    def run(self):
        try:
            from app.exporters.pdf_exporter import PDFExporter
            exporter = PDFExporter()
            
            # Using fm.resolve_file_path is safe here as it relies on OS I/O, not Qt GUI
            exporter.export_to_pdf(
                self.title, 
                self.content, 
                self.path, 
                theme_name=self.theme_name, 
                resolve_image_callback=lambda src: self.fm.resolve_file_path(src),
                base_url=self.fm.root_path
            )
            self.finished.emit(True, self.path)
        except Exception as e:
            self.finished.emit(False, str(e))

class ActionManager:
    def __init__(self, main_window):
        self.window = main_window
        # Aliases for convenience
        self.sidebar = main_window.sidebar
        self.tabbed_editor = main_window.tabbed_editor
        self.file_manager = main_window.fm
        self.create_actions()

    def create_actions(self):
        # File Actions
        self.act_new_vault = QAction("Nueva Bóveda...", self.window) 
        self.act_new_vault.triggered.connect(self.new_vault)
        
        self.act_open_vault = QAction("Abrir Bóveda...", self.window)
        self.act_open_vault.triggered.connect(self.open_vault)
        
        self.act_open_explorer = QAction("Abrir en Explorador de Archivos", self.window)
        self.act_open_explorer.triggered.connect(self.open_vault_in_explorer)
        
        self.act_new_root = QAction("Nueva Nota Raíz", self.window)
        self.act_new_root.triggered.connect(self.sidebar.add_root_note)

        self.act_new_folder_root = QAction("Nueva Carpeta Raíz", self.window)
        self.act_new_folder_root.triggered.connect(self.sidebar.add_root_folder)

        self.act_new_child = QAction("Nueva Nota Hija", self.window)
        self.act_new_child.triggered.connect(self.sidebar.add_child_note)
        
        self.act_new_folder_child = QAction("Nueva Carpeta Hija", self.window)
        self.act_new_folder_child.triggered.connect(self.sidebar.add_child_folder)

        self.act_mode_toggle = QAction(self.window)
        self.act_mode_toggle.triggered.connect(self.toggle_read_mode)
        self.update_mode_action_icon() # Set initial icon

        self.act_export_pdf = QAction("Exportar PDF", self.window)
        self.act_export_pdf.triggered.connect(lambda: self.export_note_pdf(self.tabbed_editor.current_note_id))

        self.act_export_doc = QAction("Exportar Documento...", self.window)
        self.act_export_doc.triggered.connect(lambda: self.export_note_doc(self.tabbed_editor.current_note_id))

        # Backup Action
        self.act_backup = QAction("Crear Respaldo...", self.window)
        self.act_backup.triggered.connect(self.show_backup_dialog)


        self.act_save = QAction("Guardar Nota", self.window)
        self.act_save.setShortcut(QKeySequence.Save)
        self.act_save.triggered.connect(self.window.on_save_triggered)

        self.act_exit = QAction("Salir", self.window)
        self.act_exit.setShortcut(QKeySequence.Quit)
        self.act_exit.triggered.connect(self.window.close)

        self.act_options = QAction("Opciones...", self.window)
        self.act_options.triggered.connect(self.show_options_dialog)

        # Edit Actions (Delegated to text_editor via window property or direct access?)
        # Ideally we access active editor dynamically
        self.act_undo = QAction("Deshacer", self.window)
        self.act_undo.setShortcut(QKeySequence.Undo)
        self.act_undo.triggered.connect(lambda: self.get_active_editor().undo() if self.get_active_editor() else None)

        self.act_redo = QAction("Rehacer", self.window)
        self.act_redo.setShortcut(QKeySequence.Redo)
        self.act_redo.triggered.connect(lambda: self.get_active_editor().redo() if self.get_active_editor() else None)

        self.act_cut = QAction("Cortar", self.window)
        self.act_cut.setShortcut(QKeySequence.Cut)
        self.act_cut.triggered.connect(lambda: self.get_active_editor().cut() if self.get_active_editor() else None)

        self.act_copy = QAction("Copiar", self.window)
        self.act_copy.setShortcut(QKeySequence.Copy)
        self.act_copy.triggered.connect(lambda: self.get_active_editor().copy() if self.get_active_editor() else None)

        self.act_paste = QAction("Pegar", self.window)
        self.act_paste.setShortcut(QKeySequence.Paste)
        self.act_paste.triggered.connect(lambda: self.get_active_editor().paste() if self.get_active_editor() else None)

        self.act_delete = QAction("Eliminar Nota", self.window)
        self.act_delete.setShortcut(QKeySequence.Delete)
        self.act_delete.triggered.connect(self.sidebar.delete_note)
        
        # View Actions
        self.act_zoom_in = QAction("Zoom Texto (+)", self.window)
        self.act_zoom_in.setShortcut(QKeySequence.ZoomIn)
        self.act_zoom_in.triggered.connect(lambda: self.get_active_editor().textZoomIn() if self.get_active_editor() else None)
        
        self.act_zoom_out = QAction("Zoom Texto (-)", self.window)
        self.act_zoom_out.setShortcut(QKeySequence.ZoomOut)
        self.act_zoom_out.triggered.connect(lambda: self.get_active_editor().textZoomOut() if self.get_active_editor() else None)
        
        self.act_page_zoom_in = QAction("Zoom Imagen (+)", self.window)
        self.act_page_zoom_in.setShortcut(QKeySequence("Ctrl+Shift++"))
        self.act_page_zoom_in.triggered.connect(lambda: self.get_active_editor().imageZoomIn() if self.get_active_editor() else None)
        
        self.act_page_zoom_out = QAction("Zoom Imagen (-)", self.window)
        self.act_page_zoom_out.setShortcut(QKeySequence("Ctrl+Shift+-"))
        self.act_page_zoom_out.triggered.connect(lambda: self.get_active_editor().imageZoomOut() if self.get_active_editor() else None)

        # Tools Actions
        self.act_theme = QAction("Tema", self.window)
        self.act_theme.triggered.connect(self.window.show_theme_dialog) # Assuming window implements it or we move it here?
        # Ideally ActionManager or Window handles dialog. Window has UiThemeMixin logic for now?
        # The mixin method show_theme_dialog in UiThemeMixin handles it.
        
        self.act_about = QAction("Acerca de", self.window)
        self.act_about.triggered.connect(self.show_about)

    def get_active_editor(self):
        """Helper to get the text editor widget from tab area."""
        # Using public property text_editor of TabbedEditorArea which returns active editor
        if hasattr(self.tabbed_editor, 'text_editor'):
            return self.tabbed_editor.text_editor
        return None

    def new_vault(self):
        # Use static method for better native portal integration on Linux
        path = QFileDialog.getExistingDirectory(self.window, "Seleccionar ubicación para la nueva bóveda", os.path.expanduser("~/Documentos"))
        
        if path:
            from app.ui.widgets import ModernInput
            name, ok = ModernInput.get_text(self.window, "Nueva Bóveda", "Nombre de la bóveda:")
            if ok and name.strip():
                    full_path = os.path.join(path, name.strip())
                    try:
                        os.makedirs(full_path, exist_ok=False)
                        os.makedirs(os.path.join(full_path, ".obsidian"), exist_ok=True)
                        os.makedirs(os.path.join(full_path, "images"), exist_ok=True)
                        
                        self.window.load_vault(full_path)
                        ModernInfo.show(self.window, "Éxito", f"Bóveda creada: {name}")
                    except FileExistsError:
                        ModernAlert.show(self.window, "Error", "Ya existe una carpeta con ese nombre.")
                    except Exception as e:
                        ModernAlert.show(self.window, "Error", f"No se pudo crear la bóveda: {e}")

    def open_vault(self):
        # Use static method
        path = QFileDialog.getExistingDirectory(self.window, "Abrir Bóveda (Seleccionar Carpeta)", os.path.expanduser("~/Documentos"))
        
        if path:
             self.window.load_vault(path)

    def open_vault_in_explorer(self):
        from app.utils.system_utils import show_in_explorer
        show_in_explorer(self.file_manager.root_path)

    def export_note_pdf(self, note_id):
        # 1. Check for Multi-Selection
        selection = self.sidebar.get_selected_notes()
        if len(selection) > 1:
            self.export_multiple_pdf(selection)
            return

        # 2. Single Note Export 
        try:
            content = self.file_manager.read_note(note_id)
            if content is None:
                ModernAlert.show(self.window, "Error", "No se pudo recuperar la nota.")
                return
            
            title = os.path.splitext(os.path.basename(note_id))[0]
            default_name = f"{title}.pdf"
            default_name = "".join([c for c in default_name if c.isalpha() or c.isdigit() or c in (' ', '.', '-', '_')]).strip()
            
            path, _ = QFileDialog.getSaveFileName(self.window, "Guardar PDF", 
                                                os.path.join(os.path.expanduser("~"), default_name), 
                                                "Archivos PDF (*.pdf)")
            
            if not path: return
            if not path.endswith('.pdf'): path += '.pdf'
                
            progress = QProgressDialog("Exportando a PDF...", "Cancelar", 0, 0, self.window)
            progress.setWindowModality(Qt.WindowModal)
            progress.setCancelButton(None) 
            progress.show()
            
            # Setup Worker
            self.pdf_worker = PDFExportWorker(title, content, path, "Light", self.file_manager)
            
            def on_finished(success, result):
                progress.close()
                if success:
                    ModernInfo.show(self.window, "Éxito", f"Nota exportada correctamente a:\\n{result}")
                else:
                    ModernAlert.show(self.window, "Error de Exportación", result)
                
                self.pdf_worker.deleteLater()
                self.pdf_worker = None
                
            self.pdf_worker.finished.connect(on_finished)
            self.pdf_worker.start()
            
        except Exception as e:
            ModernAlert.show(self.window, "Error de Exportación", str(e))

    def export_multiple_pdf(self, selection):
        try:
            default_name = f"Notas_Exportadas_{len(selection)}.zip"
            path, _ = QFileDialog.getSaveFileName(self.window, "Guardar Notas (ZIP)", 
                                                os.path.join(os.path.expanduser("~"), default_name), 
                                                "Archivos ZIP (*.zip)")
            
            if not path: return
            if not path.endswith('.zip'): path += '.zip'
            
            from app.exporters.export_varios_pdf import MultiPDFExporter
            exporter = MultiPDFExporter(self.file_manager)
            success = exporter.export_multiple(selection, path, theme_name="Light")
            
            if success:
                 ModernInfo.show(self.window, "Exportación Completada", f"Se exportaron {len(selection)} notas a:\\n{path}")
            else:
                 ModernAlert.show(self.window, "Error", "No se pudo generar el archivo ZIP.")
                 
        except Exception as e:
            ModernAlert.show(self.window, "Error de Exportación Múltiple", str(e))

    def export_note_doc(self, note_id):
        if not note_id: return

        from app.ui.widgets import ModernSelection
        format_choice, ok = ModernSelection.get_item(self.window, "Exportar Documento", "Selecciona el formato:", ["ODT (OpenDocument)", "DOCX (Word)"])
        
        if not ok or not format_choice:
            return
            
        is_docx = "DOCX" in format_choice
        ext = ".docx" if is_docx else ".odt"
        filter_str = "Microsoft Word (*.docx)" if is_docx else "OpenDocument Text (*.odt)"
        
        try:
            from app.ui.markdown_renderer import MarkdownRenderer
            raw_text = self.tabbed_editor.text_editor.toPlainText() 
            content = MarkdownRenderer.process_markdown_content(raw_text)
            
            title = os.path.splitext(os.path.basename(note_id))[0]
            default_name = f"{title}{ext}"
             
            path, _ = QFileDialog.getSaveFileName(self.window, f"Guardar {ext.upper()}", 
                                                os.path.join(os.path.expanduser("~"), default_name), 
                                                filter_str)
            
            if not path: return
            if not path.endswith(ext): path += ext
            
            from app.exporters.document_exporter import DocumentExporter
            exporter = DocumentExporter(self.file_manager)
            
            success = False
            if is_docx:
                success = exporter.export_docx(content, path)
            else:
                success = exporter.export_odt(content, path, base_url=self.file_manager.root_path)
                
            if success:
                ModernInfo.show(self.window, "Éxito", f"Documento exportado correctamente a:\\n{path}")
            else:
                ModernAlert.show(self.window, "Error", "Ocurrió un error al exportar el documento.")
                
        except Exception as e:
            ModernAlert.show(self.window, "Error", str(e))

    def show_backup_dialog(self):
        from app.ui.dialogs.dialogs_backup import BackupDialog
        from app.storage.backup_manager import BackupManager

        dlg = BackupDialog(self.window)
        if dlg.exec():
            fmt, password = dlg.get_data()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            ext = ".zip" if fmt == "zip" else ".tar.gz"
            default_name = f"Backup_Cogny_{timestamp}{ext}"
            
            path, _ = QFileDialog.getSaveFileName(self.window, "Guardar Respaldo", 
                                                os.path.join(os.path.expanduser("~"), default_name), 
                                                f"Archivo {fmt.upper()} (*{ext})")
            
            if path:
                if not path.endswith(ext): path += ext
                manager = BackupManager(self.file_manager.root_path)
                success, msg = manager.create_backup(path, fmt, password)
                if success:
                    ModernInfo.show(self.window, "Backup Completado", msg)
                else:
                    ModernAlert.show(self.window, "Error de Backup", msg)

    def show_about(self):
        ModernInfo.show(self.window, "Acerca de", "Cogny\\n\\nUna aplicación jerárquica para tomar notas.\\nConstruida con PySide6 y Archivos Markdown.")

    def toggle_read_mode(self):
        editor = self.get_active_editor()
        if not editor: return
        
        new_state = not editor.isReadOnly()
        editor.setReadOnly(new_state)
        
        self.update_mode_action_icon()
        
        mode = "Lectura" if new_state else "Edición"
        self.window.statusBar().showMessage(f"Modo cambiado a: {mode}", 2000)

    def update_mode_action_icon(self):
        editor = self.get_active_editor()
        is_readonly = False
        if editor:
            is_readonly = editor.isReadOnly()

        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")) # Adjust relative path
        # Actually better to rely on imported path or config if possible. 
        # But let's try to assume app/ui/managers logic
        # Current file: app/ui/managers/action_manager.py
        # Root is 3 levels up: app/ui/managers/../../../ -> app/
        # Assets are in root/assets
        
        if is_readonly:
            icon_path = os.path.join(base_dir, "assets", "icons", "read.svg")
            tooltip = "Modo Lectura (Clic para Editar)"
        else:
            icon_path = os.path.join(base_dir, "assets", "icons", "edit.svg")
            tooltip = "Modo Edición (Clic para Leer)"

        self.act_mode_toggle.setIcon(QIcon(icon_path))
        self.act_mode_toggle.setToolTip(tooltip)
        self.act_mode_toggle.setText("")

    def show_options_dialog(self):
        from app.ui.dialogs.dialogs_options import OptionsDialog
        dlg = OptionsDialog(self.window)
        dlg.exec()
