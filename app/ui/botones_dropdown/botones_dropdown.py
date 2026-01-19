from PySide6.QtWidgets import QSplitter, QToolBar, QFileDialog
from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QAction, QKeySequence
import os

from app.ui.buscador import SearchManager
from app.ui.barra_herramientas import FormatToolbar
from app.ui.sidebar import Sidebar
from app.ui.editor_area import EditorArea
from app.ui.widgets import ModernInfo, ModernAlert

class UiActionsMixin:
    def create_actions(self):
        # File Actions
        self.act_new_vault = QAction("Nueva Bóveda...", self) 
        self.act_new_vault.triggered.connect(self.new_vault)
        
        self.act_open_vault = QAction("Abrir Bóveda...", self)
        self.act_open_vault.triggered.connect(self.open_vault)

        self.act_new_root = QAction("Nueva Nota Raíz", self)
        self.act_new_root.triggered.connect(self.sidebar.add_root_note)

        self.act_new_folder_root = QAction("Nueva Carpeta Raíz", self)
        self.act_new_folder_root.triggered.connect(self.sidebar.add_root_folder)

        self.act_new_child = QAction("Nueva Nota Hija", self)
        self.act_new_child.triggered.connect(self.sidebar.add_child_note)
        
        self.act_new_folder_child = QAction("Nueva Carpeta Hija", self)
        self.act_new_folder_child.triggered.connect(self.sidebar.add_child_folder)

        self.act_export_pdf = QAction("Exportar PDF", self)
        self.act_export_pdf.triggered.connect(lambda: self.export_note_pdf(self.editor_area.current_note_id))

        self.act_export_doc = QAction("Exportar Documento...", self)
        self.act_export_doc.triggered.connect(lambda: self.export_note_doc(self.editor_area.current_note_id))

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

    def new_vault(self):
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
                        # Create 'images' folder (updated from Adjuntos)
                        os.makedirs(os.path.join(full_path, "images"), exist_ok=True)
                        
                        self.load_vault(full_path)
                        ModernInfo.show(self, "Éxito", f"Bóveda creada: {name}")
                    except FileExistsError:
                        ModernAlert.show(self, "Error", "Ya existe una carpeta con ese nombre.")
                    except Exception as e:
                        ModernAlert.show(self, "Error", f"No se pudo crear la bóveda: {e}")

    def open_vault(self):
        # OPEN VAULT (FOLDER)
        dialog = QFileDialog(self, "Abrir Bóveda (Seleccionar Carpeta)", os.path.expanduser("~/Documentos"))
        dialog.setFileMode(QFileDialog.Directory)
        dialog.setOption(QFileDialog.ShowDirsOnly, True)
        
        if dialog.exec():
             selected_files = dialog.selectedFiles()
             if selected_files:
                 self.load_vault(selected_files[0])



    def switch_vault(self, new_path):
        # 1. Update Settings
        settings = QSettings()
        settings.setValue("last_vault_path", new_path)
        
        # Clear Draft Flag
        self.is_draft = False
        
        # 2. Re-initialize FM
        from app.storage.file_manager import FileManager
        self.fm = FileManager(new_path)
        self.vault_path = new_path
        
        # 3. Clear image cache
        from app.ui.editor import NoteEditor
        NoteEditor.clear_image_cache()
        
        # 4. Restart UI
        self.menuBar().clear()
        for toolbar in self.findChildren(QToolBar):
            self.removeToolBar(toolbar)
            
        if self.centralWidget():
            self.centralWidget().deleteLater()
            
        self.setup_ui()
        self.setWindowTitle(f"Cogny - {os.path.basename(new_path)}")

    def on_sidebar_note_selected(self, note_id, is_folder):
        # Auto-save previous note
        self.editor_area.save_current_note()

        name = os.path.basename(note_id)
        self.editor_area.load_note(note_id, is_folder, title=name)
        
        # Save State
        if not is_folder:
            settings = QSettings()
            settings.setValue(f"last_note_{self.vault_path}", note_id)
        # Load new note with metadata from sidebar (avoids DB query)
        self.editor_area.load_note(note_id, is_folder=is_folder, title=name)

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
            self.save_as_vault()
            return

        title = self.editor_area.save_current_note()
        if title and self.editor_area.current_note_id:
             pass

    def save_as_vault(self):
        # Prompt user to select destination PARENT folder
        dialog = QFileDialog(self, "Guardar Bóveda en...", os.path.expanduser("~/Documentos"))
        dialog.setFileMode(QFileDialog.Directory)
        dialog.setOption(QFileDialog.ShowDirsOnly, True)
        
        if dialog.exec():
            selected_files = dialog.selectedFiles()
            if selected_files:
                parent_path = selected_files[0]
                from app.ui.widgets import ModernInput
                name, ok = ModernInput.get_text(self, "Guardar Bóveda", "Nombre de la carpeta:")
                
                if ok and name.strip():
                    dest_path = os.path.join(parent_path, name.strip())
                    
                    if os.path.exists(dest_path):
                        ModernAlert.show(self, "Error", "La carpeta de destino ya existe.")
                        return

                    try:
                        import shutil
                        shutil.copytree(self.fm.root_path, dest_path)
                        
                        # Switch to new vault
                        self.switch_vault(dest_path)
                        ModernInfo.show(self, "Éxito", f"Bóveda guardada en: {dest_path}")
                        
                    except Exception as e:
                        ModernAlert.show(self, "Error", f"No se pudo guardar la bóveda: {e}")

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
            content = self.fm.read_note(note_id)
            if content is None:
                ModernAlert.show(self, "Error", "No se pudo recuperar la nota.")
                return
            
            title = os.path.splitext(os.path.basename(note_id))[0]
            
            default_name = f"{title}.pdf"
            default_name = "".join([c for c in default_name if c.isalpha() or c.isdigit() or c in (' ', '.', '-', '_')]).strip()
            
            path, _ = QFileDialog.getSaveFileName(self, "Guardar PDF", 
                                                os.path.join(os.path.expanduser("~"), default_name), 
                                                "Archivos PDF (*.pdf)")
            
            if not path: return
            if not path.endswith('.pdf'): path += '.pdf'
                
            from app.exporters.pdf_exporter import PDFExporter
            
            # Ensure PDFExporter works without DB
            exporter = PDFExporter() 
            exporter.export_to_pdf(
                title, 
                content, 
                path, 
                theme_name="Light", 
                resolve_image_callback=lambda src: self.fm.resolve_file_path(src),
                base_url=self.fm.root_path
            )
            
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
            
            exporter = MultiPDFExporter(self.fm)
            # We force Light theme for printing
            success = exporter.export_multiple(selection, path, theme_name="Light")
            
            if success:
                 ModernInfo.show(self, "Exportación Completada", f"Se exportaron {len(selection)} notas a:\\n{path}")
            else:
                 ModernAlert.show(self, "Error", "No se pudo generar el archivo ZIP.")
                 
        except Exception as e:
            ModernAlert.show(self, "Error de Exportación Múltiple", str(e))

    def export_note_doc(self, note_id):
        if not note_id:
            return

        # 1. Ask for Format
        from app.ui.widgets import ModernSelection, ModernInfo, ModernAlert
        format_choice, ok = ModernSelection.get_item(self, "Exportar Documento", "Selecciona el formato:", ["ODT (OpenDocument)", "DOCX (Word)"])
        
        if not ok or not format_choice:
            return
            
        is_docx = "DOCX" in format_choice
        ext = ".docx" if is_docx else ".odt"
        filter_str = "Microsoft Word (*.docx)" if is_docx else "OpenDocument Text (*.odt)"
        
        # 2. Get Content & Path
        try:
            content = self.editor_area.text_editor.toHtml() # We use HTML for ODT
            raw_text = self.editor_area.text_editor.toPlainText() # We use Text for DOCX (simple version)
            
            title = os.path.splitext(os.path.basename(note_id))[0]
            default_name = f"{title}{ext}"
             
            path, _ = QFileDialog.getSaveFileName(self, f"Guardar {ext.upper()}", 
                                                os.path.join(os.path.expanduser("~"), default_name), 
                                                filter_str)
            
            if not path: return
            if not path.endswith(ext): path += ext
            
            # 3. Export
            from app.exporters.document_exporter import DocumentExporter
            exporter = DocumentExporter(self.fm)
            
            success = False
            if is_docx:
                success = exporter.export_docx(raw_text, path)
            else:
                success = exporter.export_odt(content, path, base_url=self.fm.root_path)
                
            if success:
                ModernInfo.show(self, "Éxito", f"Documento exportado correctamente a:\\n{path}")
            else:
                ModernAlert.show(self, "Error", "Ocurrió un error al exportar el documento.")
                
        except Exception as e:
            ModernAlert.show(self, "Error", str(e))

    def show_about(self):
        ModernInfo.show(self, "Acerca de", "Cogny\n\nUna aplicación jerárquica para tomar notas.\nConstruida con PySide6 y Archivos Markdown.")

class UiSetupMixin:
    def setup_ui(self):
        # Central Widget
        self.splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(self.splitter)

        # 1. Sidebar Blueprint
        # print(f"DEBUG: Initializing Sidebar. self.fm type: {type(self.fm)}, self type: {type(self)}")
        self.sidebar = Sidebar(file_manager=self.fm, parent=self)
        self.sidebar.note_selected.connect(self.on_sidebar_note_selected)
        self.sidebar.action_requested.connect(self.on_sidebar_action)
        self.splitter.addWidget(self.sidebar)

        # 2. Editor Blueprint
        self.editor_area = EditorArea(file_manager=self.fm, parent=self)
        self.editor_area.status_message.connect(self.on_editor_status)
        self.splitter.addWidget(self.editor_area)
        
        self.splitter.setSizes([300, 700])

        # Create Actions and Menus
        self.create_actions()
        self.create_menus()
        self.create_toolbar()
        
        # Restore State
        self.restore_state()

    def create_toolbar(self):
        toolbar = QToolBar("Barra Principal")
        self.addToolBar(toolbar)
        
        # Search Bar
        # We need to link SearchManager to Sidebar's tree and model
        # SearchManager logic will need update to use FM or removed if it relied purely on DB FTS
        self.search_manager = SearchManager(self.fm, self.sidebar.tree_view, self.sidebar.proxy_model, self.sidebar.on_selection_changed)
        toolbar.addWidget(self.search_manager.get_widget())
        
        toolbar.addSeparator()
        toolbar.addAction(self.act_export_pdf)
        
        self.addToolBarBreak() 
        
        self.editor_toolbar = FormatToolbar(self, self.editor_area.text_editor)
        self.addToolBar(self.editor_toolbar)

    def create_menus(self):
        menubar = self.menuBar()

        # File Menu
        file_menu = menubar.addMenu("&Archivo")
        file_menu.addAction(self.act_new_vault) 
        file_menu.addAction(self.act_open_vault)
        
        

        
        file_menu.addAction(self.act_new_root)
        file_menu.addAction(self.act_new_folder_root)
        file_menu.addSeparator()
        file_menu.addAction(self.act_new_child)
        file_menu.addAction(self.act_new_folder_child)
        file_menu.addSeparator()
        file_menu.addAction(self.act_export_pdf)
        file_menu.addAction(self.act_export_doc)
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
        
        
        # Help Menu
        help_menu = menubar.addMenu("&Ayuda")
        help_menu.addAction(self.act_about)
