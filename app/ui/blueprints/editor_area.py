from PySide6.QtWidgets import QWidget, QSplitter, QVBoxLayout, QApplication
from PySide6.QtCore import Qt, QSettings, Signal
from PySide6.QtGui import QFont, QTextCursor, QTextDocument

from app.ui.editor import NoteEditor
from app.ui.widgets import TitleEditor, ModernInfo, ModernAlert, ModernConfirm
from app.ui.highlighter import MarkdownHighlighter
from app.ui.themes import ThemeManager
from app.ui.blueprints.markdown import MarkdownRenderer

class EditorArea(QWidget):
    status_message = Signal(str, int) # message, timeout

    def __init__(self, file_manager, parent=None):
        super().__init__(parent)
        self.fm = file_manager
        self.current_note_id = None
        # self.note_loader = None removed
        self.setup_ui()

    def set_file_manager(self, file_manager):
        self.fm = file_manager
        self.text_editor.fm = file_manager
        # Reset editor
        self.clear()
        # Update Base URL for editor to new root temporarily until note loaded?
        from PySide6.QtCore import QUrl
        import os
        base_url = QUrl.fromLocalFile(self.fm.root_path + os.sep)
        self.text_editor.document().setBaseUrl(base_url)

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
        self.text_editor = NoteEditor(self.fm)
        
        # Highlighter
        self.highlighter = MarkdownHighlighter(self.text_editor.document())
        self.text_editor.highlighter = self.highlighter
        
        # Load Theme
        self.apply_current_theme()

        # Cleanup disabled to prevent data loss with loose loose coupling
        # self.db.cleanup_images(self.current_note_id, image_ids)
        # self.db.cleanup_attachments(self.current_note_id, att_ids)
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

    def load_note(self, note_id, is_folder=None, title=None):
        if is_folder:
             self.current_note_id = None
             self.show_folder_placeholder(title)
             return

        self.current_note_id = note_id
        self.title_edit.setReadOnly(False)
        self.text_editor.setReadOnly(False)
        
        # 1. Immediate UI Feedback
        self.status_message.emit(f"Cargando nota: {title}...", 0)
        self.title_edit.setPlainText(title)
        
        # Show specific loading state in editor
        # We use a simple HTML placeholder to indicate activity
        self.text_editor.setUpdatesEnabled(True) # Ensure repaint
        self.text_editor.setHtml("<div style='text-align: center; margin-top: 50px; color: #888;'><h2>Cargando...</h2></div>")
        self.text_editor.set_loading_state(True)
        
        # 2. Defer heavy loading to next event loop iteration
        # This allows the UI to repaint the "Loading..." message properly.
        from PySide6.QtCore import QTimer
        # 10ms is enough to let the event loop process the paint events
        QTimer.singleShot(10, lambda: self._perform_load_note(note_id, title))

    def _perform_load_note(self, note_id, title):
        if self.current_note_id != note_id:
            return

        # Pass current note path to editor for relative link calculation
        self.text_editor.current_note_path = note_id
        
        # Load Content from FS
        markdown_content = self.fm.read_note(note_id)
        if markdown_content is None:
            markdown_content = ""
            
        # Clean Content
        if markdown_content:
            markdown_content = markdown_content.replace('\ufffc', '')

        # Setup Base URL
        try:
            from PySide6.QtCore import QUrl
            import os
            full_path = os.path.join(self.fm.root_path, note_id)
            note_dir = os.path.dirname(full_path)
            base_url = QUrl.fromLocalFile(note_dir + os.sep)
            self.text_editor.document().setBaseUrl(base_url)
        except Exception as e:
            print(f"Error checking base url: {e}")

        # --- PROGRESSIVE LOADING STRATEGY ---
        CHUNK_SIZE = 10000 # Characters per frame (approx 2-3 pages)
        
        # 1. Initial Setup (Block heavy signals but allow updates?)
        self.text_editor.setUpdatesEnabled(False)
        self.text_editor.blockSignals(True)
        # We block document signals initially to load the first chunk fast
        self.text_editor.document().blockSignals(True)
        
        # Split content
        self._pending_chunks = [markdown_content[i:i+CHUNK_SIZE] for i in range(0, len(markdown_content), CHUNK_SIZE)]
        
        # 2. Load First Chunk Immediately (Synchronous)
        if self._pending_chunks:
            first_chunk = self._pending_chunks.pop(0)
            self.text_editor.setPlainText(first_chunk)
            # Render images for this chunk range
            self.text_editor.render_images(0, len(first_chunk))
            
            # Restore visuals for first chunk
            self.highlighter.setDocument(self.text_editor.document())
        else:
            self.text_editor.setPlainText("")
            
        # 3. Enable Updates so user sees first chunk
        self.text_editor.document().blockSignals(False)
        self.text_editor.blockSignals(False)
        self.text_editor.setUpdatesEnabled(True)
        
        # 4. Schedule rest of the content (if any)
        if self._pending_chunks:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, self._load_next_chunk)
        else:
            self._finish_loading()

    def _load_next_chunk(self):
        if not self._pending_chunks or self.current_note_id is None:
            self._finish_loading()
            return
            
        # Take next chunk
        chunk = self._pending_chunks.pop(0)
        
        # Append without blocking global signals (so UI paints?)
        # Actually, appending triggers layout. If we block signals, we might suppress painting?
        # QWidget UpdatesEnabled handles painting.
        # layout changes happen on document modification.
        # We want the user to see it growing.
        
        try:
            self.text_editor.append_chunk(chunk)
        except Exception as e:
            print(f"Error appending chunk: {e}")
            
        # Schedule next
        if self._pending_chunks:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, self._load_next_chunk)
        else:
            self._finish_loading()

    def _finish_loading(self):
        if getattr(self.text_editor, "is_loading", False):
             self.text_editor.set_loading_state(False)
             
        # Force one final update
        self.text_editor.update_extra_selections()
        self.status_message.emit("Nota cargada (completa).", 2000)

    def show_folder_placeholder(self, title):
        self.title_edit.setPlainText(title)
        self.title_edit.setReadOnly(True)
        self.text_editor.setHtml(f"<h1 style='color: gray; text-align: center; margin-top: 50px;'>Carpeta: {title}</h1><p style='color: gray; text-align: center;'>Esta es una carpeta.</p>")
        self.text_editor.setReadOnly(True)

    # Deprecated loading callbacks removed

    def save_current_note(self):
        if self.current_note_id is None:
            return

        title = self.title_edit.toPlainText()
        # Update filename if title changed? 
        # TitleEditor emits return_pressed, handled elsewhere?
        # Sidebar handles renaming (filename change).
        # Title in UI is just visual? Or does it write # Title?
        # Usually filename = title.
        # If user edits title here, we should probably rename file?
        # But that complicates things (saving triggers rename).
        # Let's assume Title Edit handles Rename elsewhere or we ignore title mismatch for now.
        # We just save content.
        
        # USE toPlainText() to preserve Markdown Source.
        # toMarkdown() was double-escaping characters (e.g. \` -> \\\`) because it thought they were literal text in a Rich Doc.
        content = self.text_editor.toPlainText()
        
        # Cleanup: Remove Object Replacement Characters (\ufffc) inserted by inserted images/attachments visuals.
        # These should not be saved to disk.
        content = content.replace('\ufffc', '')
        
        # We need to preserve `attachment://` links. 
        # `toPlainText` preserves them as text string `[filename](attachment://id)`.
        
        success = self.fm.save_note(self.current_note_id, content)
        if success:
             self.status_message.emit("Guardado.", 2000)
        else:
             self.status_message.emit("Error al guardar.", 2000)
        
        return title

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
            
            # Save using FileManager (reusing save_image logic which saves to 'images' folder)
            rel_path = self.fm.save_image(data, filename)
            
            # Insert Standard Markdown Link
            # [Filename](images/filename.ext)
            # Ensure path uses forward slashes
            url_path = rel_path.replace("\\", "/")
            self.text_editor.textCursor().insertText(f"[{filename}]({url_path})")
            
        except Exception as e:
            ModernAlert.show(self, "Error", f"No se pudo adjuntar el archivo: {e}")
