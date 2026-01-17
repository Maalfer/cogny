import os
from .connection import ConnectionMixin
from .setup import SetupMixin
from .notes import NotesMixin
from .media import MediaMixin
from .search import SearchMixin

class DatabaseManager(ConnectionMixin, SetupMixin, NotesMixin, MediaMixin, SearchMixin):
    def __init__(self, db_path: str = "notes.cdb", initialize: bool = True):
        # Determine if we are in "Vault Mode" (Folder) or "Legacy Mode" (Single File)
        if os.path.isdir(db_path):
            self.vault_path = db_path
            self.db_path = os.path.join(db_path, ".cogny.cdb")
            self.is_vault = True
        else:
            # Legacy or Draft mode (potentially just a file path)
            self.db_path = db_path
            self.vault_path = os.path.dirname(os.path.abspath(db_path))
            self.is_vault = False

        if initialize:
            self.init_db()
