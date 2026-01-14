from PySide6.QtWidgets import QWidget, QSplitter, QVBoxLayout, QApplication
from PySide6.QtCore import Qt, QSettings, Signal
from PySide6.QtGui import QFont

from app.ui.editor import NoteEditor
from app.ui.widgets import TitleEditor, ModernInfo, ModernAlert, ModernConfirm
from app.ui.highlighter import MarkdownHighlighter
from app.ui.themes import ThemeManager
from app.ui.blueprints.workers import NoteLoaderWorker
from app.ui.blueprints.markdown import MarkdownRenderer

class EditorArea(QWidget):
    status_message = Signal(str, int) # message, timeout

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.current_note_id = None
        self.note_loader = None
        self.setup_ui()

    def setup_ui(self):
        # Vertical Splitter (Title / Content)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.splitter = QSplitter(Qt.Vertical)
        
        # Title
        self.title_edit = TitleEditor()
        self.title_edit.setObjectName("TitleEdit")
        self.title_edit.setPlaceholderText("Título")
        
        title_font = QFont()
        title_font.setPointSize(24)
        title_font.setBold(True)
        self.title_edit.setFont(title_font)
        
        self.title_edit.return_pressed.connect(lambda: self.text_editor.setFocus())
        
        # Content
        self.text_editor = NoteEditor(self.db)
        
        # Highlighter
        self.highlighter = MarkdownHighlighter(self.text_editor.document())
        self.text_editor.highlighter = self.highlighter
        
        # Load Theme
        self.apply_current_theme()

        self.splitter.addWidget(self.title_edit)
        self.splitter.addWidget(self.text_editor)
        self.splitter.setSizes([80, 700])
        
        layout.addWidget(self.splitter)

    def apply_current_theme(self):
        settings = QSettings()
        current_theme = settings.value("theme", "Dark")
        self.switch_theme(current_theme)

    def switch_theme(self, theme_name):
        settings = QSettings()
        editor_bg = settings.value("theme_custom_editor_bg", "")
        self.text_editor.apply_theme(theme_name, editor_bg)
        if hasattr(self, "highlighter"):
             self.highlighter.set_theme(theme_name)

    def load_note(self, note_id):
        # Cancel previous loader
        if self.note_loader and self.note_loader.isRunning():
            self.note_loader.cancel()
            self.note_loader.wait() # Wait for thread to finish to prevent crash
            self.note_loader.deleteLater()
            self.note_loader = None
            
        # Get basic info to check if folder
        note_data = self.db.get_note(note_id)
        if not note_data: return # Or handle error
        
        # Check folder manually since we don't have the item object here easily, 
        # or we accept that callers might pass us a "folder" note ID.
        # Ideally, we should check is_folder from DB.
        # Use named access since Row factory is enabled
        is_folder = bool(note_data['is_folder'])
        # Actually let's trust the logic from main_window that checked item.is_folder or rowCount.
        # But wait, we don't have the tree item here. 
        # We can Query DB.
        
        # Re-implementing the logic cleanly:
        self.current_note_id = note_id
        
        # Note: DB schema might vary, let's look at get_note return.
        # main_window used note[2] for title, note[3] for content.
        # We'll use the worker completely for loading content.
        
        if is_folder:
             self.show_folder_placeholder(note_data[2])
             return

        self.title_edit.setReadOnly(False)
        self.text_editor.setReadOnly(False)
        self.text_editor.clear_image_cache()
        
        self.status_message.emit(f"Cargando nota: {note_data[2]}...", 0)
        self.title_edit.setPlainText("Cargando...")
        self.text_editor.setHtml("<h2 style='color: gray; text-align: center;'>Cargando contenido...</h2>")
        
        self.note_loader = NoteLoaderWorker(self.db.db_path, note_id)
        self.note_loader.finished.connect(self.on_note_loaded)
        self.note_loader.start()

    def show_folder_placeholder(self, title):
        self.title_edit.setPlainText(title)
        self.title_edit.setReadOnly(True)
        self.text_editor.setHtml(f"<h1 style='color: gray; text-align: center; margin-top: 50px;'>Carpeta: {title}</h1><p style='color: gray; text-align: center;'>Esta es una carpeta. Crea o selecciona una nota dentro de ella.</p>")
        self.text_editor.setReadOnly(True)

    def on_note_loaded(self, result):
        self.status_message.emit("", 0) # Clear
        
        if not result or result["note_id"] != self.current_note_id:
            return
            
        self.title_edit.setPlainText(result["title"])
        self.text_editor.current_note_id = result["note_id"]
        
        content = result["content"]
        
        if result["is_markdown"]:
             content = MarkdownRenderer.process_markdown_content(content)
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
        att_matches = re.findall(r'href="attachment://(\d+)"', content)
        for m in att_matches:
             try:
                 att_ids.append(int(m))
             except ValueError:
                 pass

        self.db.update_note(self.current_note_id, title, content)
        
        self.db.cleanup_images(self.current_note_id, image_ids)
        self.db.cleanup_attachments(self.current_note_id, att_ids)
        
        self.status_message.emit("Guardado.", 2000)
        
        return title # Return title to update tree if needed

    def clear(self):
        self.current_note_id = None
        self.title_edit.clear()
        self.text_editor.clear()

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
