from PySide6.QtWidgets import QMainWindow, QToolBar
from PySide6.QtGui import QIcon
from PySide6.QtCore import QSettings, Signal
import os

from app.storage.file_manager import FileManager
from app.ui.ui_state import UiStateMixin
from app.ui.ui_theme import UiThemeMixin
from app.ui.ui_actions import UiActionsMixin
from app.ui.ui_setup import UiSetupMixin

class MainWindow(UiStateMixin, UiThemeMixin, UiActionsMixin, UiSetupMixin, QMainWindow):
    ready = Signal()
    def __init__(self, vault_path=None, is_draft=False):
        super().__init__()
        self.is_draft = is_draft
        self.vault_path = vault_path
        
        display_name = 'Borrador' if is_draft else (os.path.basename(vault_path) if vault_path else 'Sin Bóveda')
        self.setWindowTitle(f"Cogny - {display_name}")
        self.resize(1200, 800)
        
        # Resolve Assets Path
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        icon_path = os.path.join(base_dir, "assets", "logo.png")
        self.setWindowIcon(QIcon(icon_path))

        # File/Vault Setup
        if not vault_path:
             # Fallback or empty state
             vault_path = os.path.expanduser("~/Documentos")
             
        self.fm = FileManager(vault_path)
        
        self.setup_ui()
        
        # Apply Initial Theme (Stylesheets)
        settings = QSettings()
        current_theme = settings.value("theme", "Dark")
        self.switch_theme(current_theme)

    def preload_initial_state(self):
        """Called by splash to pre-load content before showing window."""
        # 1. Check for last opened note
        settings = QSettings()
        # We need to implement last_note saving/loading if not present.
        # Assuming we can get it from UiStateMixin or just store it.
        # Let's check if Sidebar stores current selection.
        # Ideally, we should add 'last_opened_note' to settings when saving/opening.
        
        last_note = settings.value(f"last_note_{self.vault_path}", "")
        
        if last_note and self.fm.file_exists(last_note): # Check existence
             # Connect to editor area loaded signal
             self.editor_area.note_loaded.connect(self._on_preload_finished)
             
             # Determine title (basename)
             title = os.path.basename(last_note)
             
             # Trigger Load
             self.editor_area.load_note(last_note, is_folder=False, title=title, preload_images=True)
        else:
             # Nothing to load, ready immediately
             self.ready.emit()
             
    def _on_preload_finished(self, success):
        self.editor_area.note_loaded.disconnect(self._on_preload_finished)
        self.ready.emit()

    def load_vault(self, vault_path):
        import os
        from app.storage.file_manager import FileManager
        
        # 1. Update Settings
        settings = QSettings()
        settings.setValue("last_vault_path", vault_path)
        
        # 2. Init new File Manager
        self.fm = FileManager(vault_path)
        self.vault_path = vault_path
        
        # 3. Update Child Components
        self.sidebar.set_file_manager(self.fm)
        self.editor_area.set_file_manager(self.fm)
        
        # 4. Update Title
        self.setWindowTitle(f"Cogny - {os.path.basename(vault_path)}")
        
        # 5. Clear Image Cache
        from app.ui.editor import NoteEditor
        NoteEditor.clear_image_cache()

    def switch_vault(self, new_path):
        # 1. Update Settings
        settings = QSettings()
        settings.setValue("last_vault_path", new_path)
        
        # Clear Draft Flag
        self.is_draft = False
        self.vault_path = new_path
        
        # 2. Re-initialize File Manager
        self.fm = FileManager(new_path)
        
        # 3. Clear image cache
        from app.ui.editor import NoteEditor
        NoteEditor.clear_image_cache()
        
        # 4. Restart UI
        # We can either full restart or just reload components.
        # Clearing splitter allows recreating Sidebar and EditorArea with new fm
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

