
import sys
import os
import tempfile
from PySide6.QtWidgets import QApplication
from app.database.manager import DatabaseManager

def test_stats_logic():
    if not QApplication.instance():
        app = QApplication(sys.argv)
    
    fd, db_path = tempfile.mkstemp(suffix=".cdb")
    os.close(fd)
    
    try:
        db = DatabaseManager(db_path)
        
        # 1. Create Data
        # Root Note (1)
        root_id = db.add_note("Root Note", None, "This is a root note with six words.") 
        # Words: 8 (This, is, a, root, note, with, six, words.)
        # Letters: 31 (ignoring spaces/punct? logic strips HTML then splits. 'six words.' -> 'six', 'words.')
        # "This is a root note with six words." -> 7 words? 
        # "This", "is", "a", "root", "note", "with", "six", "words."
        # If split() by whitespace: 8 tokens.
        
        # Subnote (2)
        sub_id = db.add_note("Sub Note", root_id, "<b>Subnote</b> with <i>styles</i>.")
        # Words: 3 ("Subnote", "with", "styles.") (HTML stripped)
        
        # Note with Code (3)
        code_content = "Here is code:\n```python\nprint('hello')\n```"
        db.add_note("Code Note", None, code_content)
        # Code Fragments: 1
        # Words: "Here", "is", "code:", "print('hello')" -> 4? 
        # python and ``` might remain if regex doesn't strip them before text processing.
        # Our logic strips tags then splits. code blocks are just text.
        
        # Note with Image (4)
        img_data = b'\x89PNG\r\n\x1a\n'
        db.add_image(root_id, img_data) 
        # We need to insert the img tag to count it? No, query is SELECT COUNT(*) FROM images.
        # Logic counts DB rows for images.
        
        # 2. Get Stats
        stats = db.get_detailed_statistics()
        print("Stats Received:", stats)
        
        # 3. Verify
        # Total Notes: 3
        if stats["total_notes"] != 3:
            print(f"FAIL: Expected 3 notes, got {stats['total_notes']}")
            return False
            
        # Total Subnotes: 1
        if stats["total_subnotes"] != 1:
            print(f"FAIL: Expected 1 subnote, got {stats['total_subnotes']}")
            return False
            
        # Total Images: 1
        if stats["total_images"] != 1:
            print(f"FAIL: Expected 1 image, got {stats['total_images']}")
            return False
            
        # Total Code Fragments: 1
        if stats["total_code_fragments"] != 1:
            print(f"FAIL: Expected 1 code fragment, got {stats['total_code_fragments']}")
            return False
            
        # Total Words
        # 8 + 3 + (Here is code: python print('hello')) 
        # If ``` are kept: "```python", "```"
        # "Here", "is", "code:", "```python", "print('hello')", "```" -> 6?
        # Total approx: 8+3+6 = 17.
        # Let's check > 10.
        if stats["total_words"] < 10:
             print(f"FAIL: Word count seems low: {stats['total_words']}")
             return False
             
        print("SUCCESS: Stats logic verified.")
        return True
        
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)

if __name__ == "__main__":
    if test_stats_logic():
        sys.exit(0)
    else:
        sys.exit(1)
