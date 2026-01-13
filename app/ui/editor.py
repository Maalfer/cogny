from PySide6.QtWidgets import QTextEdit, QToolButton, QApplication
from PySide6.QtCore import QUrl, QByteArray, QBuffer, QIODevice, Qt, QSize
from PySide6.QtGui import QImage, QTextDocument, QColor, QTextFormat, QIcon, QGuiApplication, QTextCursor
from app.database.manager import DatabaseManager
from app.ui.themes import ThemeManager

class NoteEditor(QTextEdit):
    def __init__(self, db_manager: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.cursorPositionChanged.connect(self.update_highlighting)
        self.textChanged.connect(self.update_code_block_visuals)
        self.textChanged.connect(self.update_copy_buttons)
        self.verticalScrollBar().valueChanged.connect(self.update_copy_buttons_position)
        
        self.copy_buttons = []
        self.current_theme = "Light"
        self.apply_theme("Light") # Default

    def apply_theme(self, theme_name: str):
        self.current_theme = theme_name
        
        # Get base style
        style = ThemeManager.get_editor_style(theme_name)
        
        # Inject dynamic font size
        font_size = getattr(self, "current_font_size", 14)
        # We append a specific rule for NoteEditor
        style += f"\nNoteEditor {{ font-size: {font_size}pt; }}"
        
        self.setStyleSheet(style)
        self.code_bg_color = ThemeManager.get_code_bg_color(theme_name)
        
        # Revert Native Margins (Reset to default/0 allows CSS to handle padding)
        doc = self.document()
        root_frame = doc.rootFrame()
        frame_fmt = root_frame.frameFormat()
        frame_fmt.setLeftMargin(0)
        frame_fmt.setRightMargin(0)
        frame_fmt.setTopMargin(0)
        frame_fmt.setBottomMargin(0)
        root_frame.setFrameFormat(frame_fmt)
        
        self.update_code_block_visuals()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_margins()
        self.update_copy_buttons_position()

    def showEvent(self, event):
        super().showEvent(event)
        self.update_margins()

    def wheelEvent(self, event):
        # Disable Ctrl + Scroll for Zoom as per user request
        # if event.modifiers() & Qt.ControlModifier:
        #     event.ignore() # Or accept and do nothing? 
        #     # If we ignore, parent might handle it? 
        #     # Better to just let default scrolling happen or do nothing if Ctrl is held?
        #     # Standard behavior for Ctrl+Scroll is usually nothing if we don't handle it, 
        #     # or some apps scroll faster.
        #     # User said "quitarlo", implies no zoom.
        #     # If I just call super(), QTextEdit might have built-in zoom?
        #     # QTextEdit DOES have built-in Ctrl+Scroll zoom.
        #     # To block it, we must accept the event and do nothing IF Ctrl is pressed.
        
        if event.modifiers() & Qt.ControlModifier:
             # Block native zoom and our custom zoom
             pass
        else:
             super().wheelEvent(event)


    def update_margins(self):
        # Dynamic Centered Layout
        max_content_width = 1200

        current_width = self.width()
        
        if current_width > max_content_width:
             margin = (current_width - max_content_width) // 2
        else:
             margin = 30 # Minimum padding
             
        # Apply to Viewport Margins
        # Left, Top, Right, Bottom
        self.setViewportMargins(margin, 20, margin, 20)

    def update_copy_buttons(self):
        # 1. Identify start blocks of code
        code_blocks = []
        block = self.document().begin()
        while block.isValid():
            state = block.userState()
            # We look for the START definition line.
            # In our highlighter:
            # - Start line has state assigned (2,3,4,5) AND previous state was 0 or 100.
            # - But wait, previousBlockState() is not easily accessible from 'block' directly in iteration without querying keys.
            # - Easier: Check text. If it starts with ``` and has state > 0.
            
            if state > 0:
                 txt = block.text().strip()
                 if txt.startswith("```"):
                     # This is a start block (or end block? End block is state 100).
                     # Highlighter sets state 100 for end block.
                     if state != 100:
                         code_blocks.append(block)
            
            block = block.next()
            
        # 2. Recycle/Create buttons
        needed = len(code_blocks)
        current = len(self.copy_buttons)
        
        if needed > current:
            for _ in range(needed - current):
                # Reparent to viewport to match cursorRect coordinates exactly
                btn = QToolButton(self.viewport())
                btn.setText("Copy")
                btn.setCursor(Qt.PointingHandCursor)
                btn.clicked.connect(self.copy_code_block)
                self.copy_buttons.append(btn)
        
        # 3. Assign blocks and show/hide
        for i, btn in enumerate(self.copy_buttons):
            if i < needed:
                btn.show()
                # Store current block info for click handler
                btn.setProperty("block_position", code_blocks[i].position())
            else:
                btn.hide()
        
        self.update_copy_buttons_position()

    def update_copy_buttons_position(self):
        # ... (scanning logic) ...
        # We need to recreate the scanning loop or just focus on the button update part.
        # Since replace_file_content replaces a chunk, I need to be careful with context.
        # I'll replace the loop inside update_copy_buttons_position.
        
        button_idx = 0
        block = self.document().begin()
        
        while block.isValid():
            state = block.userState()
            if state > 0 and state != 100:
                 txt = block.text().strip()
                 if txt.startswith("```"):
                     if button_idx < len(self.copy_buttons):
                         btn = self.copy_buttons[button_idx]
                         
                         # Get precise rect
                         temp_cursor = self.textCursor()
                         temp_cursor.setPosition(block.position())
                         rect = self.cursorRect(temp_cursor)
                         
                         btn_width = 40
                         btn_height = 20
                         btn.resize(btn_width, btn_height)
                         
                         # Horizontal: Far right with margin (15px) inside total width
                         x = self.viewport().width() - btn_width - 15
                         
                         # Vertical: Precise Centering on the line
                         # rect.height() is the line height of the first line (```bash)
                         y = rect.top() + (rect.height() - btn_height) / 2
                         
                         btn.move(x, y)
                         btn.setProperty("block_position", block.position())
                         
                         button_idx += 1
            block = block.next()

    # Custom Zoom Handling
    
    # Text Zoom: Adjusts font size only.
    def textZoomIn(self):
        self._adjust_font_size(1)

    def textZoomOut(self):
        self._adjust_font_size(-1)

    def _adjust_font_size(self, delta):
        # We need to maintain the current font size state
        current_pt = getattr(self, "current_font_size", 14) # Default 14pt
        new_pt = max(8, current_pt + delta)
        self.current_font_size = new_pt
        
        # Apply via stylesheet to override any default
        # We need to get current theme style and append/modify font-size
        # But modify apply_theme to use this variable is cleaner.
        # Let's just re-apply theme.
        self.apply_theme(self.current_theme)

    # Image Zoom: Adjusts image size only.
    def imageZoomIn(self):
        try:
             self.image_scale = getattr(self, "image_scale", 1.0) * 1.1
             self.update_image_sizes()
        except Exception as e:
             print(f"ERROR in imageZoomIn: {e}")

    def imageZoomOut(self):
        try:
             self.image_scale = getattr(self, "image_scale", 1.0) / 1.1
             self.update_image_sizes()
        except Exception as e:
             print(f"ERROR in imageZoomOut: {e}")
             
    # Legacy aliases/overrides if needed, but we will call specific methods from main window.
    # We should override native zoomIn/zoomOut to do nothing or map to textZoom to prevent confusion if shortcuts traverse?
    def zoomIn(self, range=1):
        self.textZoomIn()
        
    def zoomOut(self, range=1):
        self.textZoomOut()

    def update_image_sizes(self):
        """Updates all image formats to match the current scale."""
        scale = getattr(self, "image_scale", 1.0)
        base_width = 600 # Our standard width
        
        cursor = self.textCursor()
        cursor.beginEditBlock()
        
        block = self.document().begin()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                fmt = frag.charFormat()
                if fmt.isImageFormat():
                    img_fmt = fmt.toImageFormat()
                    
                    # We assume 600 is base. 
                    # If we supported variable base sizes, we'd need to store original size.
                    # For now, uniform 600 is the app's style.
                    new_width = int(base_width * scale)
                    img_fmt.setWidth(new_width)
                    
                    # Apply
                    # access selection
                    cursor.setPosition(frag.position())
                    cursor.setPosition(frag.position() + frag.length(), QTextCursor.KeepAnchor)
                    cursor.setCharFormat(img_fmt)
                    
                it += 1
            block = block.next()
            
        cursor.endEditBlock()

    def copy_code_block(self):
        sender = self.sender()
        if not sender: return
        
        pos = sender.property("block_position")
        block = self.document().findBlock(pos)
        
        if not block.isValid(): return
        
        # Extract Code
        # Iterate from next block until end of code block (starts with ``` or state changes)
        code_text = []
        
        curr = block.next()
        while curr.isValid():
            txt = curr.text()
            if txt.strip() == "```":
                break
            # Handle userState check just in case text check fails?
            # Highlighter sets state 100 for end ```
            if curr.userState() == 100:
                break
            if curr.userState() == 0: # Should not happen inside logic
                break
                
            code_text.append(txt)
            curr = curr.next()
            
        full_text = "\n".join(code_text)
        QGuiApplication.clipboard().setText(full_text)
        
        # Feedback (Optional: Change text to "Copied!" temporarily)
        sender.setText("Copied!")
        from PySide6.QtCore import QTimer
        QTimer.singleShot(2000, lambda b=sender: b.setText("Copy"))
        
    def insert_attachment(self, att_id, filename):
        # We use a standard file icon. 
        # Base64 encoded generic file icon (small paperclip or doc symbol)
        # Using a simple UTF-8 char for now or a resource?
        # Better: Basic SVG data URI or simple text link with emoji?
        # User wants "icon seen in each note".
        # Let's use a simple inline HTML with emoji for simplicity and guaranteed rendering without external assets.
        # 📎 <a href="...">filename</a>
        
        html = f'&nbsp;<span style="font-size: 16px;">📎</span>&nbsp;<a href="attachment://{att_id}" style="color: #4A90E2; text-decoration: none;">{filename}</a>&nbsp;'
        self.textCursor().insertHtml(html)

    def keyPressEvent(self, event):
        # 1. Handler for Image Deletion Safety
        if event.key() in (Qt.Key_Backspace, Qt.Key_Delete):
            cursor = self.textCursor()
            check_cursor = None
            
            if cursor.hasSelection():
                check_cursor = cursor
            else:
                # Create a temporary cursor to peek at what will be deleted
                check_cursor = QTextCursor(cursor)
                if event.key() == Qt.Key_Backspace:
                    if not check_cursor.atStart():
                         check_cursor.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor)
                elif event.key() == Qt.Key_Delete:
                     if not check_cursor.atEnd():
                         check_cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor)
            
            # If we have a valid range to check
            if check_cursor and (check_cursor.hasSelection() or (not cursor.hasSelection() and check_cursor.position() != cursor.position())):
                if self.cursor_contains_image(check_cursor):
                    from PySide6.QtWidgets import QMessageBox
                    ret = QMessageBox.question(self, "Delete Image", 
                                               "Are you sure you want to delete the selected image(s)?",
                                               QMessageBox.Yes | QMessageBox.No)
                    if ret != QMessageBox.Yes:
                        return # Cancel deletion

        # 2. Handler for Markdown Horizontal Rules
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            cursor = self.textCursor()
            block = cursor.block()
            text = block.text().strip()
            
            # Check for Markdown Horizontal Rule patterns (3 or more chars)
            import re
            if re.match(r'^[-*_]{3,}$', text):
                cursor.beginEditBlock()
                
                # Clear the current line (the dashes)
                cursor.select(QTextCursor.BlockUnderCursor)
                cursor.removeSelectedText()
                
                # Insert HR
                cursor.insertHtml("<hr>")
                
                # Insert a new block after the HR so the user can continue typing
                cursor.insertBlock()
                
                cursor.endEditBlock()
                
                # Scroll to cursor to keep focus visible
                self.ensureCursorVisible()
                return # Consume the event
                
        super().keyPressEvent(event)

    def cursor_contains_image(self, cursor):
        """Checks if the given cursor range contains an image."""
        # Use a separate iterator cursor to ensure we don't modify the input
        # Note: 'cursor' passed might be self.textCursor() (selection) or a temp one.
        # Iterate over fragments in the selection.
        
        # Optimization: if it's a single char, just check charFormat
        if abs(cursor.anchor() - cursor.position()) == 1:
             # We need to check the exact char. 
             # QTextImageFormat is on the character.
             # If we moved Left, existing cursor is [pos-1, pos] (anchor, pos) relative?
             # 'cursor' logic depends on who created it.
             # Let's iterate block/fragments which is robust.
             pass
             
        start = min(cursor.anchor(), cursor.position())
        end = max(cursor.anchor(), cursor.position())
        
        doc = self.document()
        block = doc.findBlock(start)
        end_block = doc.findBlock(end)
        
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                
                # Check intersection
                frag_start = frag.position()
                frag_end = frag_start + frag.length()
                
                # If fragment overlaps with selection
                if frag_end > start and frag_start < end:
                    if frag.charFormat().isImageFormat():
                        return True
                        
                it += 1
                
            if block == end_block:
                break
            block = block.next()
            
        return False

    def mouseReleaseEvent(self, event):
        anchor = self.anchorAt(event.pos())
        if anchor:
            if anchor.startswith("attachment://"):
                att_id = int(anchor.replace("attachment://", ""))
                self.open_attachment(att_id)
                return
        super().mouseReleaseEvent(event)

    def open_attachment(self, att_id):
        # Retrieve from DB
        data_row = self.db.get_attachment(att_id)
        if not data_row:
            return
            
        filename, data = data_row
        
        # Save to temp file
        import tempfile
        import os
        from PySide6.QtGui import QDesktopServices
        
        # We try to keep the extension
        name, ext = os.path.splitext(filename)
        
        # Create temp file. 
        # delete=False so we can open it with external app.
        # We should ideally track these to delete on exit, but OS handles temp cleanup eventually.
        try:
            fd, path = tempfile.mkstemp(suffix=ext, prefix=f"cogni_{name}_")
            with os.fdopen(fd, 'wb') as f:
                f.write(data)
            
            # Open
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        except Exception as e:
            print(f"Error opening attachment: {e}")

    def update_code_block_visuals(self):
        # Use QTextBlockFormat for background color. 
        # This ensures it respects indentation and margins (unlike ExtraSelection).
        
        # Prevent Recursion (setBlockFormat triggers textChanged)
        self.blockSignals(True)
        try:
            # 1. Get Color
            color = getattr(self, "code_bg_color", QColor("#EEF1F4"))
            
            cursor = self.textCursor()
            cursor.beginEditBlock()
            
            block = self.document().begin()
            while block.isValid():
                state = block.userState()
                
                # Create Modifier Format
                fmt = block.blockFormat()
                
                if state > 0:
                    # Inside Code Block: Apply Background
                    if fmt.background().color() != color:
                        fmt.setBackground(color)
                        cursor.setPosition(block.position())
                        cursor.setBlockFormat(fmt)
                else:
                    # Normal Text: Clear Background
                    if fmt.background().style() != Qt.NoBrush:
                         fmt.clearBackground()
                         cursor.setPosition(block.position())
                         cursor.setBlockFormat(fmt)
                
                block = block.next()
                
            cursor.endEditBlock()
        finally:
            self.blockSignals(False)
        
        # Clear ExtraSelections (legacy cleanup)
        self.setExtraSelections([])

    def update_highlighting(self):
        # Notify highlighter about the active block
        if hasattr(self.document(), "findBlock"):
            cursor = self.textCursor()
            block = self.document().findBlock(cursor.position())
            
            # We assume highlighter is attached to document.
            # We can access it via findChildren or cleaner, the main window set it.
            # But syntax highlighter is not easily accessible from document() public API in Python wrapper sometimes.
            # However, QSyntaxHighlighter.document() exists.
            # We can store a reference if we passed it, but we didn't pass highlighter to editor.
            # MainWindow created Highlighter(editor.document()).
            
            # Workaround: MainWindow stores it. But editor needs to trigger rehighlight.
            # Better: NoteEditor doesn't own highlighter. Logic should be in MainWindow?
            # Or: NoteEditor emits signal?
            # Or: We find the highlighter.
            
            # Let's try to access it via parent? No.
            # Let's assign it to the editor in MainWindow!
            
            if hasattr(self, "highlighter") and self.highlighter:
                if self.highlighter.active_block != block:
                     prev_block = self.highlighter.active_block
                     self.highlighter.active_block = block
                     
                     # Rehighlight current and previous
                     self.highlighter.rehighlightBlock(block)
                     if prev_block and prev_block.isValid():
                         self.highlighter.rehighlightBlock(prev_block)

    def canInsertFromMimeData(self, source):
        if source.hasImage():
            return True
        return super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source):
        if source.hasImage():
            image = source.imageData()
            if isinstance(image, QImage):
                # Convert QImage to bytes (PNG)
                ba = QByteArray()
                buffer = QBuffer(ba)
                buffer.open(QIODevice.WriteOnly)
                image.save(buffer, "PNG")
                data = ba.data()
                
                if hasattr(self, "current_note_id") and self.current_note_id is not None:
                    image_id = self.db.add_image(self.current_note_id, data)
                    
                    # Insert HTML
                    html = f'<img src="image://db/{image_id}" />'
                    self.textCursor().insertHtml(html)
                    return
        
        super().insertFromMimeData(source)

    def loadResource(self, type, name):
        if type == QTextDocument.ImageResource:
            url = name.toString() if isinstance(name, QUrl) else str(name)
            if url.startswith("image://db/"):
                try:
                    image_id = int(url.split("/")[-1])
                    blob = self.db.get_image(image_id)
                    if blob:
                        img = QImage()
                        img.loadFromData(blob)
                        return self._process_image(img)
                except Exception as e:
                    print(f"Error loading image: {e}")
        
        return super().loadResource(type, name)

    def _process_image(self, image: QImage) -> QImage:
        """Process image to enforce uniform style: 
           - Fixed Width (600px)
           - Rounded Corners (12px)
        """
        target_width = 600
        
        # 1. Scale uniform width
        # Use SmoothTransformation for quality
        if image.width() != target_width:
             image = image.scaledToWidth(target_width, Qt.SmoothTransformation)
             
        # 2. Apply Rounded Corners
        # Create a new transparent image of same size
        out_img = QImage(image.size(), QImage.Format_ARGB32)
        out_img.fill(Qt.transparent)
        
        from PySide6.QtGui import QPainter, QBrush, QPainterPath
        
        painter = QPainter(out_img)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Create rounded path
        path = QPainterPath()
        rect = out_img.rect()
        path.addRoundedRect(0, 0, rect.width(), rect.height(), 12, 12)
        
        # Clip to path and draw original image
        painter.setClipPath(path)
        painter.drawImage(0, 0, image)
        painter.end()
        
        return out_img
