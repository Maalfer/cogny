
import sys
from PySide6.QtWidgets import QApplication
from app.ui.editor import NoteEditor
from app.database.manager import DatabaseManager
from PySide6.QtGui import QImage, QTextCursor, QTextImageFormat
from PySide6.QtCore import QByteArray, QBuffer, QIODevice

def test_image_scaling():
    if not QApplication.instance():
        app = QApplication(sys.argv)
    else:
        app = QApplication.instance()
        
    db = DatabaseManager(":memory:")
    editor = NoteEditor(db)
    editor.show()
    
    # 1. Insert Dummy Image
    # Create simple red image
    img = QImage(100, 100, QImage.Format_ARGB32)
    img.fill(0xFFFF0000) # Red
    
    # Add to DB to simulate real usage
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    data = ba.data()
    
    # Hack: Add directly to DB tables if we can, or assume insert_attachment logic
    # Editor uses 'image://db/id'
    # We need to manually insert into 'images' table
    cursor = db._get_connection().cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS images (id INTEGER PRIMARY KEY, note_id INTEGER, data BLOB)")
    cursor.execute("INSERT INTO images (note_id, data) VALUES (1, ?)", (data,))
    img_id = cursor.lastrowid
    
    # Insert HTML
    editor.textCursor().insertHtml(f'<img src="image://db/{img_id}" />')
    
    app.processEvents()
    
    # 2. Find Image Format
    doc = editor.document()
    
    # Iterate to find the image char
    cursor = QTextCursor(doc)
    found = False
    initial_width = 0
    
    # Scan document
    block = doc.begin()
    while block.isValid():
        it = block.begin()
        while not it.atEnd():
            frag = it.fragment()
            fmt = frag.charFormat()
            if fmt.isImageFormat():
                img_fmt = fmt.toImageFormat()
                print(f"Found Image. Width: {img_fmt.width()}, Height: {img_fmt.height()}")
                initial_width = img_fmt.width()
                found = True
                
                # Check actual size if 0?
                # QTextImageFormat returns 0 if not set, but loadResource handles it.
                # If width is 0, it uses intrinsic size. 
                # Our editor _process_image returns 600px intrinsic.
                # So format might report 0 or 600?
                # If setHtml logic set it? No.
                
                # We want to CHANGE it using setWidth
            it += 1
        block = block.next()
        
    if not found:
        print("FAIL: Image not found in document.")
        return False
        
    # 3. Apply Resize (Scale 2.0x)
    print("--- Resizing ---")
    
    # Re-iterate and modify
    new_width = 200 # Force explicit size
    if initial_width > 0:
        new_width = initial_width * 2
        
    cursor.movePosition(QTextCursor.Start)
    while not cursor.atEnd():
        # Move char by char? Efficient? No.
        # Move by iter?
        # We need to select the character to setCharFormat.
        
        # Next char
        cursor.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor)
        fmt = cursor.charFormat()
        
        if fmt.isImageFormat():
            img_fmt = fmt.toImageFormat()
            img_fmt.setWidth(new_width)
            img_fmt.setName(img_fmt.name()) # Keep name
            cursor.setCharFormat(img_fmt)
            print(f"Updated Width to {new_width}")
            
        cursor.clearSelection()
        
    # 4. Verify
    # Check if format persisted
    cursor.movePosition(QTextCursor.Start)
    cursor.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor) # Assuming image is first
    fmt = cursor.charFormat()
    
    if fmt.isImageFormat():
        w = fmt.toImageFormat().width()
        print(f"Verified Width: {w}")
        if w == new_width:
            print("SUCCESS: Image resized.")
            return True
        else:
            print("FAIL: Resize didn't persist.")
            return False

    return False

if __name__ == "__main__":
    if test_image_scaling():
        sys.exit(0)
    else:
        sys.exit(1)
