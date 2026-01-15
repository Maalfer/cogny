import sqlite3
import threading
from contextlib import contextmanager

class ConnectionMixin:
    def _create_connection(self):
        # Increased timeout to 30s to allow for concurrent operations without "database is locked"
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        
        # Performance & Concurrency Tuning
        conn.execute("PRAGMA journal_mode=WAL;") # Write-Ahead Logging allows concurrent readers
        conn.execute("PRAGMA synchronous=NORMAL;") # Faster, slightly less safe than FULL, but standard for desktop apps
        conn.execute("PRAGMA foreign_keys=ON;") # Enable foreign key constraints for CASCADE deletes
        conn.row_factory = sqlite3.Row # Access columns by name (faster C implementation than dict)
        
        return conn

    def _get_connection(self):
        return self._create_connection()

    @property
    def _read_conn(self):
        if not hasattr(self, '_thread_local'):
            self._thread_local = threading.local()
        
        if not hasattr(self._thread_local, 'connection'):
            self._thread_local.connection = self._create_connection()
        return self._thread_local.connection

    def fetch_one(self, query: str, params: tuple = ()):
        """Execute a query and return one row using a cached connection."""
        cursor = self._read_conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchone()

    def fetch_all(self, query: str, params: tuple = ()):
        """Execute a query and return all rows using a cached connection."""
        cursor = self._read_conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()

    def transaction(self):
        """Helper to ensure connection closing and commit/rollback."""
        @contextmanager
        def _transaction():
            conn = self._get_connection()
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
        return _transaction()
