from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QFileDialog
from app.ui.widgets import ModernInfo, ModernAlert
from app.ui.blueprints.markdown import MarkdownRenderer
import os

class UiActionsMixin:
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

    def toggle_editor_toolbar(self, checked):
        self.editor_toolbar.setVisible(checked)

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
            
            ModernInfo.show(self, "Éxito", f"Nota exportada correctamente a:\\n{path}")
            
        except Exception as e:
            ModernAlert.show(self, "Error de Exportación", str(e))

    def show_about(self):
        ModernInfo.show(self, "Acerca de", "Cogny\\n\\nUna aplicación jerárquica para tomar notas.\\nConstruida con PySide6 y SQLite.")
