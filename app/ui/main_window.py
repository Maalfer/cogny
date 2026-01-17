from PySide6.QtWidgets import QMainWindow, QToolBar
from PySide6.QtGui import QIcon
from PySide6.QtCore import QSettings
import os

from app.database.manager import DatabaseManager
from app.storage.file_manager import FileManager
from app.ui.ui_state import UiStateMixin
from app.ui.ui_theme import UiThemeMixin
from app.ui.ui_workers import UiWorkersMixin
from app.ui.ui_actions import UiActionsMixin
from app.ui.ui_setup import UiSetupMixin

class MainWindow(UiStateMixin, UiThemeMixin, UiWorkersMixin, UiActionsMixin, UiSetupMixin, QMainWindow):
    def __init__(self, db_path="notes.cdb", is_draft=False):
        super().__init__()
        self.is_draft = is_draft
        self.setWindowTitle(f"Cogny - {'Borrador (Sin Guardar)' if is_draft else os.path.basename(db_path)}")
        self.resize(1200, 800)
        

        # Resolve Assets Path
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        icon_path = os.path.join(base_dir, "assets", "logo.png")
        self.setWindowIcon(QIcon(icon_path))

        # Database Setup
        self.db = DatabaseManager(db_path)
        
        # File/Vault Setup
        # Use the vault path determined by the DatabaseManager
        if hasattr(self.db, 'vault_path') and self.db.vault_path:
            vault_path = self.db.vault_path
        else:
            # Fallback for legacy single-file DBs (treat parent dir as vault root?)
            # or just default to Documents
            vault_path = os.path.dirname(os.path.abspath(db_path))

        self.fm = FileManager(vault_path)
        
        self.setup_ui()
        
        # Apply Initial Theme (Stylesheets)
        # Palette is set in main.py, but stylesheets (sidebar) need to be applied to widgets.
        settings = QSettings()
        current_theme = settings.value("theme", "Dark")
        self.switch_theme(current_theme)

    def load_vault(self, vault_path):
        import os
        from app.storage.file_manager import FileManager
        
        # 1. Update Settings
        # settings = QSettings()
        # settings.setValue("last_vault_path", vault_path)
        
        # 2. Init new File Manager
        self.fm = FileManager(vault_path)
        
        # 3. Update Child Components
        self.sidebar.set_file_manager(self.fm)
        self.editor_area.set_file_manager(self.fm)
        
        # 4. Update Title
        self.setWindowTitle(f"Cogny - {os.path.basename(vault_path)}")
        
        # 5. Clear Image Cache? 
        # Images are loaded from FS now. 
        # But Editor has an LRU cache. It should be fine as keys are paths/IDs.
        # If IDs collide (unlikely with path), it might be an issue.
        # But we changed Editor to use Path as key mostly (or we should).
        # Actually NoteEditor._image_cache keys are... 
        # loadResource uses path string.
        # _cache_image uses image_id.
        # So we should clear it to be safe.
        from app.ui.editor import NoteEditor
        NoteEditor.clear_image_cache()

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

