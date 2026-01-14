import sqlite3
from contextlib import contextmanager

class ConnectionMixin:
    def _get_connection(self):
        # Increased timeout to 30s to allow for concurrent operations without "database is locked"
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        
        # Performance & Concurrency Tuning
        conn.execute("PRAGMA journal_mode=WAL;") # Write-Ahead Logging allows concurrent readers
        conn.execute("PRAGMA synchronous=NORMAL;") # Faster, slightly less safe than FULL, but standard for desktop apps
        conn.execute("PRAGMA foreign_keys=ON;") # Enable foreign key constraints for CASCADE deletes
        conn.row_factory = sqlite3.Row # Access columns by name (faster C implementation than dict)
        
        return conn

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
