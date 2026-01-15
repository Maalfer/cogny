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
        
        self.setup_ui()

