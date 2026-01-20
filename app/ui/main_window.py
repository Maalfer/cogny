from PySide6.QtWidgets import QMainWindow, QToolBar
from PySide6.QtGui import QIcon
from PySide6.QtCore import QSettings, Signal
import os

from app.storage.file_manager import FileManager
from app.ui.ui_state import UiStateMixin
from app.ui.ui_theme import UiThemeMixin
from app.ui.botones_dropdown.botones_dropdown import UiActionsMixin, UiSetupMixin

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
        
        # Initialize Config Manager
        from app.storage.config_manager import ConfigManager
        self.config_manager = ConfigManager(self.fm.root_path)
        
        self.setup_ui()
        
        # Apply Initial Theme (Stylesheets)
        # settings = QSettings() -> Removed global settings for theme
        current_theme = self.config_manager.get("theme", "Dark")
        self.switch_theme(current_theme)

    def preload_initial_state(self):
        """Called by splash to pre-load content before showing window."""
        # [CRITICAL] PRELOAD LOGIC - DO NOT MODIFY
        # This function is the ONLY place where the initial note should be loaded.
        # It MUST use async_load=True to keep the Splash Screen animations running.
        # It MUST handle the Fallback scenario (finding any note) if the last note is missing.
        # 1. Check for last opened note in Vault Config
        last_note = self.config_manager.get("last_opened_note", "")
        
        if last_note and self.fm.file_exists(last_note): # Check existence
             print(f"DEBUG: Found last note: {last_note}. Starting preload...")
             # Connect to editor area loaded signal
             self.editor_area.note_loaded.connect(self._on_preload_finished)
             
             # Determine title (basename)
             # Determine title (basename)
             title = os.path.basename(last_note)
             
             # Trigger Load Synchronously
             # We use async_load=True to allow the Event Loop to run (animations, splash screen updates)
             # while the note loads in the background. The 'ready' signal will still only be emitted when done.
             self.editor_area.load_note(last_note, is_folder=False, title=title, preload_images=True, async_load=True)
             return

        # Fallback: If no last note, try to find ANY note to warm up the editor
        # This prevents the "First Note Slow" issue by ensuring the engine is initialized.
        print(f"DEBUG: Last note '{last_note}' not found. Searching for fallback...")
        
        fallback_note = None
        # Use FileManager to list files or search
        # Simple walk to find first .md
        for root, dirs, files in os.walk(self.fm.root_path):
             # Skip hidden
             dirs[:] = [d for d in dirs if not d.startswith('.')]
             for f in files:
                  if f.endswith('.md'):
                       fallback_note = self.fm._get_rel_path(os.path.join(root, f))
                       break
             if fallback_note:
                  break
                  
        if fallback_note:
             print(f"DEBUG: Found fallback note: {fallback_note}. Preloading...")
             self.editor_area.note_loaded.connect(self._on_preload_finished)
             title = os.path.basename(fallback_note)
             self.editor_area.load_note(fallback_note, is_folder=False, title=title, preload_images=True, async_load=True)
        else:
             print("DEBUG: No notes found in vault. Ready immediately.")
             # Nothing to load, ready immediately
             self.ready.emit()
             
    def _on_preload_finished(self, success):
        self.editor_area.note_loaded.disconnect(self._on_preload_finished)
        
        # [CRITICAL] SIDEBAR SYNC
        # We MUST block signals to prevent the Sidebar from triggering a "selection changed" event,
        # which would cause a circular note reload and double-loading.
        if self.editor_area.current_note_id:
            try:
                self.sidebar.blockSignals(True)
                self.sidebar.select_note(self.editor_area.current_note_id)
            finally:
                self.sidebar.blockSignals(False)
        
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
        
        # Re-init Config Manager
        from app.storage.config_manager import ConfigManager
        self.config_manager = ConfigManager(self.fm.root_path)
        
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

