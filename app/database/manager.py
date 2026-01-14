from .connection import ConnectionMixin
from .setup import SetupMixin
from .notes import NotesMixin
from .media import MediaMixin
from .search import SearchMixin

class DatabaseManager(ConnectionMixin, SetupMixin, NotesMixin, MediaMixin, SearchMixin):
    def __init__(self, db_path: str = "notes.cdb"):
        self.db_path = db_path
        self.init_db()
