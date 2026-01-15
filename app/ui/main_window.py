from PySide6.QtWidgets import QMainWindow
from PySide6.QtGui import QIcon
import os

from app.database.manager import DatabaseManager
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
        
        # Initialize image cache with DB path for persistence
        from app.ui.image_cache import GlobalImageCache
        GlobalImageCache.set_db_path(db_path)
        
        self.setup_ui()
        
        # Start background image preloading after a short delay
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1000, lambda: self._start_image_preloader(db_path))
    
    def _start_image_preloader(self, db_path):
        """Start background worker to progressively preload images."""
        from app.ui.blueprints.workers import ImagePreloaderWorker
        self.image_preloader = ImagePreloaderWorker(db_path)
        self.image_preloader.progress.connect(self._on_preload_progress)
        self.image_preloader.start()
    
    def _on_preload_progress(self, current, total):
        """Show progress of image preloading in status bar."""
        # Update every 10 images to avoid spamming status bar
        if current % 10 == 0 or current == total:
            self.statusBar().showMessage(f"Indexando contenido: {current}/{total}", 2000)
