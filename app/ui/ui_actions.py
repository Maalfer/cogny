from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QFileDialog, QToolBar
from app.ui.widgets import ModernInfo, ModernAlert
from app.ui.blueprints.markdown import MarkdownRenderer
import os

class UiActionsMixin:
    def create_actions(self):
        # File Actions
        self.act_new_db = QAction("Nueva Bóveda...", self) # Concept shift?
        self.act_new_db.triggered.connect(self.new_database)
        
        self.act_open_db = QAction("Abrir Bóveda...", self)
        self.act_open_db.triggered.connect(self.open_database)
        
        self.act_save_as_db = QAction("Guardar Como...", self) # Copy current DB to new location and switch
        self.act_save_as_db.triggered.connect(self.save_as_database)
        
        self.act_read_later_list = QAction("Notas Guardadas...", self)
        self.act_read_later_list.triggered.connect(self.show_read_later_dialog)

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

        self.act_export_pdf = QAction("Exportar PDF", self)
        self.act_export_pdf.triggered.connect(lambda: self.export_note_pdf(self.editor_area.current_note_id))

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

    def new_database(self):
        # Create New Vault (Folder)
        # We need a parent directory to create the new vault INSIDE.
        dialog = QFileDialog(self, "Seleccionar ubicación para la nueva bóveda", os.path.expanduser("~/Documentos"))
        dialog.setFileMode(QFileDialog.Directory)
        dialog.setOption(QFileDialog.ShowDirsOnly, True)
        
        if dialog.exec():
            selected_files = dialog.selectedFiles()
            if selected_files:
                path = selected_files[0]
                from app.ui.widgets import ModernInput
                name, ok = ModernInput.get_text(self, "Nueva Bóveda", "Nombre de la bóveda:")
                if ok and name.strip():
                    full_path = os.path.join(path, name.strip())
                    try:
                        os.makedirs(full_path, exist_ok=False)
                        # Create .obsidian folder (optional but nice)
                        os.makedirs(os.path.join(full_path, ".obsidian"), exist_ok=True)
                        # Create 'Adjuntos' folder
                        os.makedirs(os.path.join(full_path, "Adjuntos"), exist_ok=True)
                        
                        self.load_vault(full_path)
                        ModernInfo.show(self, "Éxito", f"Bóveda creada: {name}")
                    except FileExistsError:
                        ModernAlert.show(self, "Error", "Ya existe una carpeta con ese nombre.")
                    except Exception as e:
                        ModernAlert.show(self, "Error", f"No se pudo crear la bóveda: {e}")

    def open_database(self):
        # OPEN VAULT (FOLDER)
        # Use explicit dialog instance for better control over directory selection behavior
        dialog = QFileDialog(self, "Abrir Bóveda (Seleccionar Carpeta)", os.path.expanduser("~/Documentos"))
        dialog.setFileMode(QFileDialog.Directory)
        dialog.setOption(QFileDialog.ShowDirsOnly, True)
        
        # Try to enforce native dialog if available, but ensure it respects directory selection
        # On some Linux DEs, native dialogs can be finicky about "Open" vs "Enter".
        # If issues persist, we might consider DontUseNativeDialog.
        # For now, let's stick to standard configuration which usually works if setFileMode is correct.
        
        if dialog.exec():
             selected_files = dialog.selectedFiles()
             if selected_files:
                 self.load_vault(selected_files[0])

    def save_as_database(self):
        # Save current DB content to a new file.
        # Since SQLite is a file, we can checkpoint/backup or just copy.
        # But simpler: switch to new path (created empty) and user copies content?
        # "Save As" usually means "Save current state to new file and switch".
        # SQLite `VACUUM INTO` or backup API is best. 
        # For simplicity in this iteration: We will just COPY the file.
        path, _ = QFileDialog.getSaveFileName(self, "Guardar Base de Datos Como...", 
                                            os.path.expanduser("~/Documentos"), 
                                            "Cogny Database (*.cdb)")
        if path:
            if not path.endswith(".cdb"): path += ".cdb"
            
            # Flush current changes
            self.editor_area.save_current_note()
            
            # Copy file
            import shutil
            try:
                shutil.copy2(self.db.db_path, path)
                self.switch_database(path)
                ModernInfo.show(self, "Éxito", f"Base de datos guardada en:\\n{path}")
            except Exception as e:
                ModernAlert.show(self, "Error", f"No se pudo guardar como:\\n{str(e)}")

    def switch_database(self, new_path):
        # 1. Update Settings
        settings = QSettings()
        settings.setValue("last_db_path", new_path)
        
        # Clear Draft Flag
        self.is_draft = False
        
        # 2. Re-initialize DB Manager
        from app.database.manager import DatabaseManager
        self.db = DatabaseManager(new_path)
        
        # 3. Clear image cache (different DB = different images)
        from app.ui.editor import NoteEditor
        NoteEditor.clear_image_cache()
        
        # 4. Restart UI
        self.menuBar().clear()
        for toolbar in self.findChildren(QToolBar):
            self.removeToolBar(toolbar)
            
        # Clear Central Widget (Splitter)
        if self.centralWidget():
            self.centralWidget().deleteLater()
            
        # Re-run setup
        self.setup_ui()
            
        # Update Title
        self.setWindowTitle(f"Cogny - {os.path.basename(new_path)}")

    def on_sidebar_note_selected(self, note_id, is_folder, title):
        # Auto-save previous note
        self.editor_area.save_current_note()
        # Load new note with metadata from sidebar (avoids DB query)
        self.editor_area.load_note(note_id, is_folder=is_folder, title=title)

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

    def on_save_triggered(self):
        # Intercept Save if we are in Draft Mode
        if getattr(self, "is_draft", False):
            # Prompt user to save the whole database
            self.save_as_database()
            return

        title = self.editor_area.save_current_note()
        if title and self.editor_area.current_note_id:
             # Need to update sidebar title in tree?
             # Sidebar model might need refresh or manual update.
             # Ideally sidebar listens to DB changes or we call a method.
             # We can't access model item easily here. 
             # Let's rely on Sidebar refreshing or simple "Reload" logic if needed.
             # Or we can notify sidebar.
             pass

    def toggle_editor_toolbar(self, checked):
        self.editor_toolbar.setVisible(checked)

    def export_note_pdf(self, note_id):
        # 1. Check for Multi-Selection in Sidebar
        # If user explicitly selected multiple notes in the sidebar tree, 
        # we prioritize exporting that batch as a ZIP.
        selection = self.sidebar.get_selected_notes()
        
        if len(selection) > 1:
            self.export_multiple_pdf(selection)
            return

        # 2. Single Note Export (Legacy Flow)
        try:
            note_data = self.db.get_note(note_id)
            if not note_data:
                ModernAlert.show(self, "Error", "No se pudo recuperar la nota.")
                return
            
            title = note_data['title']
            content = note_data['content']
            
            default_name = f"{title}.pdf"
            default_name = "".join([c for c in default_name if c.isalpha() or c.isdigit() or c in (' ', '.', '-', '_')]).strip()
            
            path, _ = QFileDialog.getSaveFileName(self, "Guardar PDF", 
                                                os.path.join(os.path.expanduser("~"), default_name), 
                                                "Archivos PDF (*.pdf)")
            
            if not path: return
            if not path.endswith('.pdf'): path += '.pdf'
                
            from app.exporters.pdf_exporter import PDFExporter
            
            # Force Light theme for PDF export (standard white paper look)
            exporter = PDFExporter(self.db)
            exporter.export_to_pdf(title, content, path, theme_name="Light")
            
            ModernInfo.show(self, "Éxito", f"Nota exportada correctamente a:\\n{path}")
            
        except Exception as e:
            ModernAlert.show(self, "Error de Exportación", str(e))

    def export_multiple_pdf(self, selection):
        """Bundles multiple notes into a single ZIP file."""
        try:
            # Suggest a ZIP filename
            default_name = f"Notas_Exportadas_{len(selection)}.zip"
            path, _ = QFileDialog.getSaveFileName(self, "Guardar Notas (ZIP)", 
                                                os.path.join(os.path.expanduser("~"), default_name), 
                                                "Archivos ZIP (*.zip)")
            
            if not path: return
            if not path.endswith('.zip'): path += '.zip'
            
            from app.exporters.export_varios_pdf import MultiPDFExporter
            
            exporter = MultiPDFExporter(self.db)
            # We force Light theme for printing
            success = exporter.export_multiple(selection, path, theme_name="Light")
            
            if success:
                 ModernInfo.show(self, "Exportación Completada", f"Se exportaron {len(selection)} notas a:\\n{path}")
            else:
                 ModernAlert.show(self, "Error", "No se pudo generar el archivo ZIP.")
                 
        except Exception as e:
            ModernAlert.show(self, "Error de Exportación Múltiple", str(e))

    def show_about(self):
        ModernInfo.show(self, "Acerca de", "Cogny\\n\\nUna aplicación jerárquica para tomar notas.\\nConstruida con PySide6 y SQLite.")

    def show_read_later_dialog(self):
        from app.ui.dialogs.read_later_dialog import ReadLaterDialog
        dlg = ReadLaterDialog(self.db, self)
        dlg.note_selected.connect(self.sidebar.select_note)
        dlg.exec()
