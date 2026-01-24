from PySide6.QtWidgets import QWidget, QSplitter, QVBoxLayout, QApplication
from PySide6.QtCore import Qt, QSettings, Signal, QEvent
from PySide6.QtGui import QFont, QTextCursor, QTextDocument

from app.ui.editors.note_editor import NoteEditor
from app.ui.components.inputs import TitleEditor
from app.ui.components.dialogs import ModernInfo, ModernAlert, ModernConfirm
from app.ui.editors.highlighter import MarkdownHighlighter
from app.ui.themes import ThemeManager
from app.ui.markdown_renderer import MarkdownRenderer

class EditorArea(QWidget):
    status_message = Signal(str, int) # message, timeout
    note_loaded = Signal(bool) # success
    note_renamed = Signal(str, str) # old_id, new_id

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
        # Vertical Layout (Title / Content)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Title
        self.title_edit = TitleEditor()
        self.title_edit.setObjectName("TitleEdit")
        self.title_edit.setPlaceholderText("Título")
        
        title_font = QFont()
        title_font.setPointSize(24)
        title_font.setBold(True)
        self.title_edit.setFont(title_font)
        
        self.title_edit.return_pressed.connect(lambda: self.text_editor.setFocus())
        self.title_edit.setReadOnly(True)
        self.title_edit.installEventFilter(self)
        
        # Content
        self.text_editor = NoteEditor(self.fm)
        
        # Highlighter
        self.highlighter = MarkdownHighlighter(self.text_editor.document(), self.text_editor)
        self.text_editor.highlighter = self.highlighter
        
        # Load Theme
        self.apply_current_theme()

        # Add widgets directly to layout
        layout.addWidget(self.title_edit)
        layout.addWidget(self.text_editor)

    def apply_current_theme(self):
        settings = QSettings()
        current_theme = settings.value("theme", "Dark")
        self.switch_theme(current_theme)

    def switch_theme(self, theme_name, text_color=None, global_bg=None):
        settings = QSettings()
        editor_bg = settings.value("theme_custom_editor_bg", "")
        self.text_editor.apply_theme(theme_name, editor_bg, text_color, global_bg)
        
        # Apply Title Style
        title_style = ThemeManager.get_title_style(theme_name, global_bg, text_color)
        self.title_edit.setStyleSheet(title_style)
        
        if hasattr(self, "highlighter"):
             self.highlighter.set_theme(theme_name)

    def load_note(self, note_id, is_folder=None, title=None, preload_images=False, async_load=True):
        if is_folder:
             self.current_note_id = None
             self.show_folder_placeholder(title)
             return

        self.current_note_id = note_id
        
        
        # Save Last Opened Note for Splash Screen logic
        try:
             # We assume ConfigManager is available or can be instantiated (since it is lightweight)
             from app.storage.config_manager import ConfigManager
             config = ConfigManager(self.fm.root_path)
             config.save_config("last_opened_note", note_id)
        except Exception as e:
             print(f"Error saving last opened note: {e}")
        
        
        # Display Title (Strip .md extension)
        display_title = title
        if display_title and display_title.endswith('.md'):
             display_title = display_title[:-3]
             
        self.title_edit.setPlainText(display_title)
        self.title_edit.setReadOnly(True) # Ensure Read-Only
        self.text_editor.setReadOnly(False)
        
        # Show specific loading state in editor
        # We use a simple HTML placeholder to indicate activity
        self.text_editor.setUpdatesEnabled(True) # Ensure repaint
        self.text_editor.setHtml("<div style='text-align: center; margin-top: 50px; color: #888;'><h2>Cargando...</h2></div>")
        self.text_editor.set_loading_state(True)
        
        # 2. Perform Load
        print(f"DEBUG: load_note called for {note_id}. Async={async_load}")
        if async_load:
            # Defer heavy loading to next event loop iteration
            from PySide6.QtCore import QTimer
            QTimer.singleShot(10, lambda: self._perform_load_note(note_id, title, preload_images, async_load=True))
        else:
            # Synchronous load (blocks UI until done)
            # Necessary for Splash Screen "preload" to be true preload
            self._perform_load_note(note_id, title, preload_images, async_load=False)

    def _perform_load_note(self, note_id, title, preload_images=False, async_load=True):
        if self.current_note_id != note_id:
            return

        # Pass current note path to editor for relative link calculation
        self.text_editor.current_note_path = note_id
        
        def on_loaded(markdown_content):
            print(f"DEBUG EditorArea: Async read finished for {note_id}. Content len: {len(markdown_content) if markdown_content else 0}")
            # Verify we are still looking at the same note (user didn't switch fast)
            if self.current_note_id != note_id: 
                print(f"DEBUG EditorArea: Note ID changed (Current: {self.current_note_id} vs {note_id}), aborting render.")
                return
            self._on_content_ready(markdown_content, note_id, preload_images, async_load)

        if async_load:
            self.fm.read_note_async(note_id, on_loaded)
        else:
            markdown_content = self.fm.read_note(note_id)
            on_loaded(markdown_content)

    def _on_content_ready(self, markdown_content, note_id, preload_images, async_load):
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

        # Trigger Preload if requested
        if preload_images and markdown_content:
            # Simple Regex Extraction to find image paths
            import re
            # Match standard and wikilink images
            # Scan entire content to ensure we catch all images for the splash screen
            scan_text = markdown_content 
            
            # Standard: ![...](path)
            std_matches = re.findall(r"!\[.*?\]\((.*?)\)", scan_text)
            
            # Wiki: ![[path|...]] or ![[path]]
            wiki_matches = []
            for m in re.findall(r"!\[\[(.*?)\]\]", scan_text):
                if "|" in m:
                    wiki_matches.append(m.split("|")[0])
                else:
                    wiki_matches.append(m)
            
            all_paths = std_matches + wiki_matches
            
            if all_paths:
                # We block the flow here until images are loaded
                # Define callback to resume
                def resume_loading():
                    print("DEBUG: Images preloaded. Resuming rendering...")
                    from PySide6.QtCore import QThread
                    self._start_rendering(markdown_content, async_load=async_load)
                
                print(f"DEBUG: Preloading images: {len(all_paths)}")
                self.text_editor.preload_images(all_paths, resume_loading)
                return

        # If no preload needed or no images, proceed directly
        print("DEBUG: No images to preload or list empty. Starting rendering directly.")
        self._start_rendering(markdown_content, async_load=async_load)

    def _start_rendering(self, markdown_content, async_load=True):
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
            # Render images and tables for this chunk range
            self.text_editor.render_images(0, len(first_chunk))
            self.text_editor.render_tables(0, len(first_chunk))
            
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
            if async_load:
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, self._load_next_chunk)
            else:
                 # Flush synchronously
                 from PySide6.QtWidgets import QApplication
                 while self._pending_chunks:
                     chunk = self._pending_chunks.pop(0)
                     try:
                         self.text_editor.append_chunk(chunk)
                         # Process events to allow layout updates and splash animations
                         QApplication.processEvents()
                     except Exception:
                         pass
                 self._finish_loading()
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
             
        # Force one final update with DELAY
        # This 100ms delay ensures that the MarkdownHighlighter has finished 
        # assigning block states (e.g. STATE_CODE_BLOCK) before we try to paint the backgrounds.
        from PySide6.QtCore import QTimer
        QTimer.singleShot(100, self.text_editor.update_extra_selections)
        
        self.status_message.emit("Nota cargada (completa).", 2000)
        print("DEBUG: Loading finished. Emitting note_loaded(True)")
        self.note_loaded.emit(True)

    def show_folder_placeholder(self, title):
        self.title_edit.setPlainText(title)
        self.title_edit.setReadOnly(True)
        self.text_editor.setHtml(f"<h1 style='color: gray; text-align: center; margin-top: 50px;'>Carpeta: {title}</h1><p style='color: gray; text-align: center;'>Esta es una carpeta.</p>")
        self.text_editor.setReadOnly(True)

    # Deprecated loading callbacks removed

    def save_current_note(self, silent=False):
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
        
        if not silent:
            if success:
                 self.status_message.emit("Guardado.", 2000)
            else:
                 self.status_message.emit("Error al guardar.", 2000)
        
        return title

    def rename_current_note(self, new_title):
        if not self.current_note_id or not new_title.strip():
            return
            
        import os
        # Get current title from ID (filename)
        # Note: self.current_note_id is relative path e.g. "folder/note.md"
        old_basename = os.path.basename(self.current_note_id)
        old_title = os.path.splitext(old_basename)[0]
        
        if new_title.strip() == old_title:
            return
            
        print(f"DEBUG: Renaming '{self.current_note_id}' ({old_title}) to '{new_title.strip()}'")
        
        # Verify source file exists
        if not self.fm.file_exists(self.current_note_id):
            print(f"ERROR: Source file not found: {self.current_note_id}")
            self.status_message.emit("Error: Archivo no encontrado. ¿Se ha movido?", 3000)
            return

        try:
            new_rel_path = self.fm.rename_item(self.current_note_id, new_title.strip())
            
            if new_rel_path:
                print(f"DEBUG: Rename successful. New ID: {new_rel_path}")
                old_id = self.current_note_id
                self.current_note_id = new_rel_path
                self.note_renamed.emit(old_id, new_rel_path)
                self.status_message.emit(f"Renombrado a {new_title}", 2000)
            else:
                 print("DEBUG: Rename returned None?")
        except Exception as e:
            print(f"ERROR doing rename: {e}")
            self.status_message.emit(f"Error al renombrar: {e}", 3000)
            # Revert title edit if failed?
            # self.title_edit.setPlainText(old_title)

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

    def eventFilter(self, obj, event):
        if obj == self.title_edit and event.type() == QEvent.Wheel:
            # Forward wheel event to text_editor custom logic
            if self.text_editor:
                self.text_editor.manual_scroll(event)
            return True
        return super().eventFilter(obj, event)

    def wheelEvent(self, event):
        # Forward any bubble-up scroll events (e.g. from margins) to the editor
        if self.text_editor:
            self.text_editor.manual_scroll(event)
            event.accept()
