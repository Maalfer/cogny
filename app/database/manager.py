from .connection import ConnectionMixin
from .setup import SetupMixin
from .notes import NotesMixin
from .media import MediaMixin
from .search import SearchMixin

class DatabaseManager(ConnectionMixin, SetupMixin, NotesMixin, MediaMixin, SearchMixin):
    def __init__(self, db_path: str = "notes.cdb", initialize: bool = True):
        self.db_path = db_path
        if initialize:
            self.init_db()
