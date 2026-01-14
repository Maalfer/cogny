import unittest
import unittest.mock
import threading
import time
import os
import random
from app.database.manager import DatabaseManager

class TestConcurrency(unittest.TestCase):
    def setUp(self):
        self.db_path = "test_stress.cdb"
        for ext in ["", "-wal", "-shm"]:
            path = self.db_path + ext
            if os.path.exists(path):
                os.remove(path)
        
        # Initialize DB with WAL mode
        self.db = DatabaseManager(self.db_path)
        self.db.init_db()

    def tearDown(self):
        # We need to close connections before removing?
        # DatabaseManager doesn't hold open connection globally, only per method.
        # But we should ensure threads are done.
        for ext in ["", "-wal", "-shm"]:
            path = self.db_path + ext
            if os.path.exists(path):
                os.remove(path)

    def test_concurrent_reads_and_writes(self):
        """Simulate high concurrency of reads and writes."""
        
        errors = []
        threads = []
        num_threads = 4
        ops_per_thread = 20
        
        # Pre-fill some data
        root_id = self.db.add_note("Root")
        
        def writer_task(tid):
            try:
                # Avoid re-running heavyweight init_db (backups/integrity) in threads
                with unittest.mock.patch.object(DatabaseManager, 'init_db', return_value=None):
                    db = DatabaseManager(self.db_path) 
                
                for i in range(ops_per_thread):
                    # Write
                    title = f"Note T{tid}-{i}"
                    db.add_note(title, parent_id=root_id, content="Some content " * 10)
                    time.sleep(random.uniform(0.001, 0.005))
            except Exception as e:
                errors.append(f"Writer {tid} failed: {e}")

        def reader_task(tid):
            try:
                with unittest.mock.patch.object(DatabaseManager, 'init_db', return_value=None):
                    db = DatabaseManager(self.db_path)
                for i in range(ops_per_thread):
                    # Read
                    notes = db.get_children(root_id)
                    # Verify integrity effectively by reading accessing results
                    _ = len(notes)
                    
                    # Also read a specific note if exists
                    if notes:
                        nid = notes[0][0] # Access by index or name? Row object.
                        # row['id'] if Row factory.
                        full_note = db.get_note(nid)
                    
                    time.sleep(random.uniform(0.001, 0.005))
            except Exception as e:
                errors.append(f"Reader {tid} failed: {e}")

        # Start Threads
        for i in range(num_threads // 2):
            t_w = threading.Thread(target=writer_task, args=(i,))
            t_r = threading.Thread(target=reader_task, args=(i,))
            threads.append(t_w)
            threads.append(t_r)
            t_w.start()
            t_r.start()
            
        # Join
        for t in threads:
            t.join()
            
        if errors:
            self.fail(f"Concurrency errors detected:\n" + "\n".join(errors))
            
        # Final Verification
        final_count = len(self.db.get_children(root_id))
        expected_min = (num_threads // 2) * ops_per_thread
        # Actually logic above purely adds.
        self.assertEqual(final_count, expected_min, f"Expected {expected_min} notes, found {final_count}")

if __name__ == "__main__":
    unittest.main()
