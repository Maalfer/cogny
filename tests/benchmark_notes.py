import os
import time
import shutil
import sys
# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.manager import DatabaseManager
import app.database.connection
print(f"DEBUG: app.database.connection file: {app.database.connection.__file__}", flush=True)

DB_PATH = "benchmark.cdb"

def setup_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    # Remove backups
    if os.path.exists("backups"):
        shutil.rmtree("backups")

    db = DatabaseManager(DB_PATH)
    return db

def cleanup():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    if os.path.exists("backups"):
        shutil.rmtree("backups")

def benchmark():
    print("Starting benchmark...")
    try:
        db = setup_db()
        
        # Measure Insertion
        start_time = time.time()
        for i in range(1000):
            db.add_note(title=f"Note {i}", content=f"Content for note {i} " * 10)
        end_time = time.time()
        insert_time = end_time - start_time
        print(f"Time to insert 1000 notes: {insert_time:.4f} seconds ({1000/insert_time:.2f} notes/s)")

        # Measure Reading All individually (simulating traversing)
        start_time = time.time()
        notes = db.get_children(None) # Get root notes
        print(f"Root notes count: {len(notes)}")
        for note in notes:
            _ = db.get_note(note['id'])
        end_time = time.time()
        read_all_time = end_time - start_time
        print(f"Time to read 1000 notes individually: {read_all_time:.4f} seconds ({1000/read_all_time:.2f} notes/s)")

        # Measure get_all_notes
        start_time = time.time()
        all_notes = db.get_all_notes()
        end_time = time.time()
        get_all_time = end_time - start_time
        print(f"Time to get_all_notes: {get_all_time:.4f} seconds. Count: {len(all_notes)}")

    finally:
        cleanup()

if __name__ == "__main__":
    benchmark()
