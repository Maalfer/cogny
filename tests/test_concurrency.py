
import unittest
import sys
import os
import threading
import time
import sqlite3
from concurrent.futures import ThreadPoolExecutor

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database.manager import DatabaseManager

class TestConcurrency(unittest.TestCase):
    def setUp(self):
        self.db_name = "test_concurrency.cdb"
        if os.path.exists(self.db_name):
            os.remove(self.db_name)
        self.db = DatabaseManager(self.db_name)
        
    def tearDown(self):
        if os.path.exists(self.db_name):
            os.remove(self.db_name)

    def test_concurrent_reads_writes(self):
        # Stress test with multiple threads reading and writing
        # Without WAL mode, this should likely fail with "database is locked"
        
        exceptions = []
        
        def writer_task(thread_id):
            try:
                # Create separate standard connection or use Manager
                # Manager creates new connection each time so it's thread-safe-ish
                # as long as SQLite handles the locking.
                for i in range(50):
                    self.db.add_note(f"Note {thread_id}-{i}", None)
            except Exception as e:
                exceptions.append(e)

        def reader_task():
            try:
                for _ in range(50):
                    self.db.search_notes_fts("Note")
            except Exception as e:
                exceptions.append(e)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for i in range(5):
                futures.append(executor.submit(writer_task, i))
            for i in range(5):
                futures.append(executor.submit(reader_task))
                
            for f in futures:
                f.result()
                
        if exceptions:
            print(f"Caught {len(exceptions)} exceptions:")
            for e in exceptions[:5]:
                print(e)
            self.fail(f"Concurrency test failed with {len(exceptions)} exceptions")

    def test_fts_update_concurrency(self):
        # Specifically test updates triggering FTS triggers while reading
        self.db.add_note("Target Note", None)
        note_id = self.db.get_all_notes()[0][0]
        
        exceptions = []
        
        def update_task():
            try:
                for i in range(50):
                    self.db.update_note(note_id, f"Updated Title {i}", "Content")
            except Exception as e:
                exceptions.append(e)
                
        def search_task():
            try:
                for _ in range(50):
                    self.db.search_notes_fts("Updated")
            except Exception as e:
                exceptions.append(e)
                
        with ThreadPoolExecutor(max_workers=4) as executor:
            f1 = executor.submit(update_task)
            f2 = executor.submit(search_task)
            f1.result()
            f2.result()
            
        if exceptions:
             self.fail(f"Concurrency update test failed with {len(exceptions)} exceptions")

if __name__ == "__main__":
    unittest.main()
