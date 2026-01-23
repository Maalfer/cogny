from PySide6.QtWidgets import QTextEdit, QToolButton, QApplication, QAbstractScrollArea
from PySide6.QtCore import QUrl, QByteArray, QBuffer, QIODevice, Qt, QSize
from PySide6.QtGui import QImage, QTextDocument, QColor, QTextFormat, QIcon, QGuiApplication, QTextCursor, QKeySequence, QTextLength
from app.ui.themes import ThemeManager
import os
import re

class NoteEditor(QTextEdit):
    # Class-level image cache shared across instances
    _image_cache = {}  # {image_id: QImage}
    _image_cache_order = []  # For LRU eviction
    _max_cached_images = 100  # Limit memory usage
    
    def __init__(self, file_manager, parent=None):
        super().__init__(parent)
        self.fm = file_manager
        self.cursorPositionChanged.connect(self.update_highlighting)
        # Optimized: Use contentsChange for incremental updates instead of full textChanged scan
        self.document().contentsChange.connect(self.on_contents_change)
        self.textChanged.connect(self.update_copy_buttons)
        self.verticalScrollBar().valueChanged.connect(self.update_copy_buttons_position)
        
        self.copy_buttons = []
        self.current_theme = "Light"
        self.current_font_size = 14
        self.current_editor_bg = None
        self.is_loading = False # Performance flag
        
        

        
        self.apply_theme("Light") # Default

    def set_loading_state(self, loading: bool):
        self.is_loading = loading

    def setReadOnly(self, ro):
        super().setReadOnly(ro)
        if hasattr(self, "highlighter") and self.highlighter:
            self.highlighter.rehighlight()

            
    def _wrap_selection(self, start_marker, end_marker=None):
        """Wraps selected text or inserts markers if empty."""
        if end_marker is None:
            end_marker = start_marker
            
        cursor = self.textCursor()
        if cursor.hasSelection():
            text = cursor.selectedText()
            
            # Smart Toggle: Check if already wrapped
            if text.startswith(start_marker) and text.endswith(end_marker) and len(text) >= len(start_marker) + len(end_marker):
                # Remove markers (Unwrap)
                # Slice text to remove start_marker and end_marker
                new_text = text[len(start_marker) : -len(end_marker)]
                cursor.insertText(new_text)
            else:
                # Add markers (Wrap)
                cursor.insertText(f"{start_marker}{text}{end_marker}")
        else:
            # No selection: insert markers and put cursor in middle
            cursor.insertText(f"{start_marker}{end_marker}")
            cursor.movePosition(QTextCursor.Left, QTextCursor.MoveAnchor, len(end_marker))
            self.setTextCursor(cursor)
        
        self.setFocus()

    def toggle_bold(self):
        self._wrap_selection("**")

    def toggle_italic(self):
        self._wrap_selection("*")

    def toggle_underline(self):
        self._wrap_selection("<u>", "</u>")

    def toggle_highlight(self):
        self._wrap_selection("==", "==")

    def toggle_header(self, level: int):
        """
        Toggles header at the current cursor line.
        If line starts with same header level, removes it.
        If different level, changes it.
        If none, adds it.
        """
        cursor = self.textCursor()
        # Ensure we operate on the block (line)
        cursor.movePosition(QTextCursor.StartOfBlock)
        cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
        
        line_text = cursor.selectedText()
        target_prefix = "#" * level + " "
        
        # Check existing headers
        import re
        match = re.match(r"^(#+)\s+(.*)", line_text)
        
        if match:
            existing_hashes = match.group(1)
            content = match.group(2)
            
            if len(existing_hashes) == level:
                # Same level -> Toggle OFF (remove header)
                new_text = content
            else:
                # Different level -> Change
                new_text = f"{target_prefix}{content}"
        else:
            # No header -> Add
            new_text = f"{target_prefix}{line_text}"
            
        cursor.insertText(new_text)





    def apply_theme(self, theme_name: str, editor_bg: str = None, text_color: str = None, global_bg: str = None):
        self.current_theme = theme_name
        
        if editor_bg is not None:
             self.current_editor_bg = editor_bg
        
        style = ThemeManager.get_editor_style(theme_name, self.current_editor_bg, text_color, global_bg)
        font_size = getattr(self, "current_font_size", 14)
        
        self.setStyleSheet(style)
        self.code_bg_color = ThemeManager.get_code_bg_color(theme_name)
        
        font = self.font()
        font.setPointSize(font_size)
        self.setFont(font)
        
        # Reset document margins
        doc = self.document()
        root_frame = doc.rootFrame()
        frame_fmt = root_frame.frameFormat()
        frame_fmt.setLeftMargin(0)
        frame_fmt.setRightMargin(0)
        frame_fmt.setTopMargin(0)
        frame_fmt.setBottomMargin(0)
        root_frame.setFrameFormat(frame_fmt)
        
        self.update_extra_selections()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_margins()
        self.update_copy_buttons_position()

    def showEvent(self, event):
        super().showEvent(event)
        self.update_margins()

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            pass  # Block Ctrl+Scroll zoom
        else:
            self.manual_scroll(event)

    def manual_scroll(self, event):
        """Manually handles scroll events."""
        vbar = self.verticalScrollBar()
        delta = event.angleDelta().y()
        
        # Prioritize pixelDelta for high-res trackpads
        if not event.pixelDelta().isNull():
            delta = event.pixelDelta().y()
        else:
            # Standard mouse wheel: 120 units usually ~3 lines. 
            # Let's approximate decent speed.
            delta = int(delta / 2) 
            
        
        # Subtract because positive delta (scrolling away/up) means moving UP document (decreasing value)
        vbar.setValue(vbar.value() - delta)
        event.accept()


    def update_margins(self):
        # Dynamic Centered Layout
        max_content_width = 800

        current_width = self.width()
        
        if current_width > max_content_width:
             margin = (current_width - max_content_width) // 2
        else:
             margin = 30
             
        self.setViewportMargins(margin, 20, margin, 20)

    def update_copy_buttons(self):
        code_blocks = []
        block = self.document().begin()
        while block.isValid():
            state = block.userState()
            if state > 0:
                 txt = block.text().strip()
                 if txt.startswith("```") and state != 100:
                     code_blocks.append(block)
            block = block.next()
            
        needed = len(code_blocks)
        current = len(self.copy_buttons)
        
        if needed > current:
            for _ in range(needed - current):
                btn = QToolButton(self.viewport())
                btn.setText("Copy")
                btn.setCursor(Qt.PointingHandCursor)
                btn.clicked.connect(self.copy_code_block)
                self.copy_buttons.append(btn)
        
        for i, btn in enumerate(self.copy_buttons):
            if i < needed:
                btn.show()
                btn.setProperty("block_position", code_blocks[i].position())
            else:
                btn.hide()
        
        self.update_copy_buttons_position()

    def update_copy_buttons_position(self):
        button_idx = 0
        block = self.document().begin()
        
        while block.isValid():
            state = block.userState()
            if state > 0 and state != 100:
                 txt = block.text().strip()
                 if txt.startswith("```"):
                     if button_idx < len(self.copy_buttons):
                         btn = self.copy_buttons[button_idx]
                         
                         temp_cursor = self.textCursor()
                         temp_cursor.setPosition(block.position())
                         rect = self.cursorRect(temp_cursor)
                         
                         btn_width = 40
                         btn_height = 20
                         btn.resize(btn_width, btn_height)
                         
                         x = self.viewport().width() - btn_width - 15
                         y = rect.top() + (rect.height() - btn_height) / 2
                         
                         btn.move(x, y)
                         btn.setProperty("block_position", block.position())
                         
                         button_idx += 1
            block = block.next()

    def textZoomIn(self):
        self._adjust_font_size(1)

    def textZoomOut(self):
        self._adjust_font_size(-1)

    def insert_table(self, rows=2, cols=2):
        from PySide6.QtGui import QTextTableFormat
        from PySide6.QtCore import Qt
        
        cursor = self.textCursor()
        fmt = QTextTableFormat()
        fmt.setCellPadding(5)
        fmt.setCellSpacing(0)
        fmt.setBorder(1)
        fmt.setWidth(QTextLength(QTextLength.PercentageLength, 100))
        
        cursor.insertTable(rows, cols, fmt)
        self.setTextCursor(cursor)

    def insert_code_block(self, language="python"):
        """Inserts a markdown code block for the specified language."""
        cursor = self.textCursor()
        # Ensure we are at start of line or insert newline
        # cursor.movePosition(QTextCursor.StartOfBlock, QTextCursor.KeepAnchor)
        # if cursor.selectedText().strip():
        #     cursor.insertText("\n")
        
        # Simple insertion
        cursor.insertText(f"```{language}\n\n```")
        # Move cursor back up one line
        cursor.movePosition(QTextCursor.Up)
        self.setTextCursor(cursor)
        self.setFocus()

    def _adjust_font_size(self, delta):
        self.current_font_size = max(8, self.current_font_size + delta)
        self.apply_theme(self.current_theme)

    def imageZoomIn(self):
        self.image_scale = getattr(self, "image_scale", 1.0) * 1.1
        self.update_image_sizes()

    def imageZoomOut(self):
        self.image_scale = getattr(self, "image_scale", 1.0) / 1.1
        self.update_image_sizes()
    # We should override native zoomIn/zoomOut to do nothing or map to textZoom to prevent confusion if shortcuts traverse?
    def zoomIn(self, range=1):
        self.textZoomIn()
        
    def zoomOut(self, range=1):
        self.textZoomOut()

    def update_image_sizes(self):
        """Updates all image formats to match the current scale, respecting intrinsic size."""
        scale = getattr(self, "image_scale", 1.0)
        max_width = 800 # Constraint width
        
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
                    name = img_fmt.name()
                    
                    # Attempt to get original image size from document resources
                    from PySide6.QtGui import QTextDocument
                    # Try to retrieve the cached image or resource
                    variant = self.document().resource(QTextDocument.ImageResource, name)
                    
                    if variant:
                         # variant is QVariant containing QImage or QPixmap
                         img = variant # PySide6 auto-unwraps usually, or we cast
                         if img and not img.isNull():
                              original_width = img.width()
                              
                              # Smart Scaling Logic:
                              # 1. Start with original width * zoom
                              target_width = original_width * scale
                              
                              # 2. If it exceeds our max column width, clamp it (downscale)
                              #    But if it's smaller, KEEP it smaller (don't upscale/blur)
                              limit = max_width * scale
                              
                              if target_width > limit:
                                  final_width = int(limit)
                              else:
                                  # Don't artificialy stretch small icons/screenshots
                                  final_width = int(target_width)

                              img_fmt.setWidth(final_width)
                              
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
        
        code_text = []
        curr = block.next()
        while curr.isValid():
            txt = curr.text()
            if txt.strip() == "```" or curr.userState() == 100 or curr.userState() == 0:
                break
            code_text.append(txt)
            curr = curr.next()
            
        full_text = "\n".join(code_text)
        QGuiApplication.clipboard().setText(full_text)
        
        sender.setText("Copied!")
        from PySide6.QtCore import QTimer
        QTimer.singleShot(2000, lambda b=sender: b.setText("Copy"))
        
    # insert_attachment removed


    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Backspace, Qt.Key_Delete):
            cursor = self.textCursor()
            check_cursor = None
            
            if cursor.hasSelection():
                check_cursor = cursor
            else:
                check_cursor = QTextCursor(cursor)
                if event.key() == Qt.Key_Backspace:
                    if not check_cursor.atStart():
                         check_cursor.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor)
                elif event.key() == Qt.Key_Delete:
                     if not check_cursor.atEnd():
                         check_cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor)
            
            if check_cursor and (check_cursor.hasSelection() or (not cursor.hasSelection() and check_cursor.position() != cursor.position())):
                # Removed attachment deletion logic
                if self.cursor_contains_image(check_cursor):
                    from PySide6.QtWidgets import QMessageBox
                    ret = QMessageBox.question(self, "Eliminar Imagen", 
                                               "¿Estás seguro de que quieres eliminar la(s) imagen(es) seleccionada(s)?",
                                               QMessageBox.Yes | QMessageBox.No)
                    if ret != QMessageBox.Yes:
                        return

        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            cursor = self.textCursor()
            block = cursor.block()
            text = block.text().strip()
            
            import re
            if re.match(r'^[-*_]{3,}$', text):
                cursor.beginEditBlock()
                cursor.select(QTextCursor.BlockUnderCursor)
                cursor.removeSelectedText()
                cursor.insertHtml("<hr>")
                cursor.insertBlock()
                cursor.endEditBlock()
                self.ensureCursorVisible()
                return
                
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

        return False

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        
        # --- TABLE CONTEXT MENU ---
        # Obtain cursor at MOUSE position, not current caret position
        cursor = self.cursorForPosition(event.pos())
        table = cursor.currentTable()
        if table:
            menu.addSeparator()
            
            # Table Actions
            menu.addAction("Insertar Fila Arriba", lambda: table.insertRows(table.cellAt(cursor).row(), 1))
            menu.addAction("Insertar Fila Abajo", lambda: table.insertRows(table.cellAt(cursor).row() + 1, 1))
            menu.addSeparator()
            menu.addAction("Insertar Columna Izquierda", lambda: table.insertColumns(table.cellAt(cursor).column(), 1))
            menu.addAction("Insertar Columna Derecha", lambda: table.insertColumns(table.cellAt(cursor).column() + 1, 1))
            menu.addSeparator()
            menu.addAction("Eliminar Fila", lambda: table.removeRows(table.cellAt(cursor).row(), 1))
            menu.addAction("Eliminar Columna", lambda: table.removeColumns(table.cellAt(cursor).column(), 1))
            menu.addSeparator()
            # Delete Table: Select range and remove
            def delete_table():
                cursor.setPosition(table.firstCursorPosition().position() - 1)
                cursor.setPosition(table.lastCursorPosition().position() + 1, QTextCursor.KeepAnchor)
                cursor.removeSelectedText()
                
            menu.addAction("Eliminar Tabla", delete_table)
            
            menu.exec(event.globalPos())
            return
            
        super().contextMenuEvent(event)



    def mouseDoubleClickEvent(self, event):
        # Prevent double click from doing anything special with attachments
        anchor = self.anchorAt(event.pos())
        if anchor and anchor.startswith("attachment://"):
            return
            
        # Fallback check
        # cursor = self.cursorForPosition(event.pos())
        # is_att, _, _ = self.cursor_contains_attachment(cursor)
        # if is_att:
        #    return
            
        super().mouseDoubleClickEvent(event)

    def mouseReleaseEvent(self, event):
        # Handle Internal Links Navigation
        cursor = self.cursorForPosition(event.pos())
        anchor = self.anchorAt(event.pos()) # Standard HTML links
        
        # Check for wiki-style internal links [[#Header]]
        block = cursor.block()
        text = block.text()
        
        # We need to check if the click was *inside* a [[#...]] pattern
        # Simple proximity check around cursor
        pos_in_block = cursor.positionInBlock()
        
        import re
        # Find all link matches in the line
        for match in re.finditer(r"\[\[(#.*?)\]\]", text):
            start = match.start()
            end = match.end()
            if start <= pos_in_block <= end:
                target = match.group(1) # "#Header"
                self.scroll_to_header(target)
                return

        super().mouseReleaseEvent(event)

    def scroll_to_header(self, header_target):
        """
        Scrolls to the header matching the target string (e.g. #Introducción).
        Case-insensitive match.
        """
        target_clean = header_target.lstrip('#').strip().lower()
        
        block = self.document().begin()
        while block.isValid():
            text = block.text().strip()
            if text.startswith("#"):
                # Clean header text: remove hashes and strip
                # e.g. "## Introducción" -> "introducción"
                # "## Conceptos Clave" -> "conceptos clave"
                header_content = re.sub(r"^#+\s*", "", text).lower().strip()
                
                if header_content == target_clean:
                    # Found!
                    cursor = self.textCursor()
                    cursor.setPosition(block.position())
                    self.setTextCursor(cursor)
                    self.ensureCursorVisible()
                    center_cursor = self.cursorRect(cursor).center()
                    # self.verticalScrollBar().setValue(...) # ensureCursorVisible handles it usually
                    return
            block = block.next()

    def generate_toc(self):
        """Generates a Table of Contents at the current cursor position."""
        toc_lines = ["## Índice"]
        
        block = self.document().begin()
        while block.isValid():
            text = block.text().strip()
            if text.startswith("#"):
                match = re.match(r"^(#+)\s+(.*)", text)
                if match:
                    hashes = match.group(1)
                    title = match.group(2).strip()
                    level = len(hashes)
                    
                    if title.lower() == "índice": # Skip the TOC header itself
                         block = block.next()
                         continue
                         
                    # Create Link: [[#Title]]
                    link = f"[[#{title}]]"
                    
                    # Indent
                    indent = "  " * (level - 1)
                    toc_lines.append(f"{indent}* {link}")
                    
            block = block.next()
            
        if len(toc_lines) > 1:
            cursor = self.textCursor()
            cursor.insertText("\n".join(toc_lines) + "\n\n")




    def on_contents_change(self, position, charsRemoved, charsAdded):
        if getattr(self, "is_loading", False):
            return
            
        # Trigger visual update logic deferred to allow highlighter to update states
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self.update_extra_selections)

    def update_extra_selections(self):
        """Updates background colors and other visuals using ExtraSelections (does not affect Undo stack)."""
        extra_selections = []
        
        # 1. Code Block Backgrounds
        code_bg_color = getattr(self, "code_bg_color", QColor("#EEF1F4"))
        
        block = self.document().begin()
        while block.isValid():
            state = block.userState()
            
            if state > 0: # Inside Code Block (any positive state, including 100 for end)
                # But typically state > 0 means "is code".
                # User implementation: state=1 (generic), state>=2 (lang).
                # We want background for these.
                
                from PySide6.QtWidgets import QTextEdit
                sel = QTextEdit.ExtraSelection()
                sel.format.setBackground(code_bg_color)
                sel.format.setProperty(QTextFormat.FullWidthSelection, True) 
                
                cursor = self.textCursor()
                cursor.setPosition(block.position())
                cursor.setPosition(block.position() + block.length(), QTextCursor.KeepAnchor) # Include newline to ensure empty lines are painted and FullWidth works
                sel.cursor = cursor
                extra_selections.append(sel)
                
            block = block.next()
            
        self.setExtraSelections(extra_selections)
        
        # 2. Update Copy Buttons positions if needed
        self.update_copy_buttons()

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
                
                # Setup Buffer
                buffer.open(QIODevice.WriteOnly)
                image.save(buffer, "PNG")
                # Explicit conversion to bytes
                data = ba.data() 
                
                # Generate Filename (timestamp or UUID)
                import time
                filename = f"image_{int(time.time()*1000)}.png"
                
                # Save to FS
                try:
                    rel_path_root = self.fm.save_image(data, filename)
                    
                    full_abs_path = os.path.join(self.fm.root_path, rel_path_root)
                    
                    # Optimization: Pre-process and cache the image to avoid reloading it from disk immediately
                    # This skips disk read + PNG decompression in loadResource
                    processed_img = self._process_image(image)
                    self._cache_image(full_abs_path, processed_img) # Key is absolute path
                    
                    # Calculate relative path from current note to image
                    # rel_path_root is "images/file.png"
                    
                    final_link_path = rel_path_root
                    if hasattr(self, "current_note_path") and self.current_note_path:
                         import os
                         # We need to go from Note DIR to Image
                         # Note path is relative to root.
                         note_rel_dir = os.path.dirname(self.current_note_path)
                         
                         # relpath(target, start)
                         # We use relative paths for the Markdown link so it's portable
                         final_link_path = os.path.relpath(rel_path_root, note_rel_dir)
                    
                    # Normalize slashes
                    url_path = final_link_path.replace("\\", "/")
                    
                    # Insert Markdown
                    self.textCursor().insertText(f"![Image]({url_path})")
                    
                    # Insert WYSIWYG Image
                    # CRITICAL: Use ABSOLUTE path for the visual insertion to guarantee loadResource works
                    # without complex relative resolution guesswork during the insert event.
                    # loadResource will still be called, but with an absolute path check first.
                    
                    from PySide6.QtGui import QTextImageFormat
                    fmt = QTextImageFormat()
                    # We use the absolute path for the runtime object name/source
                    fmt.setName(full_abs_path)
                    # fmt.setWidth(600) # REMOVED hardcoded width to allow CSS control (max-width: 100%)
                    self.textCursor().insertImage(fmt)
                    
                except Exception as e:
                    print(f"Error saving image: {e}")
            return
        return super().insertFromMimeData(source)
    
    
    # Async Loading Components
    _loading_images = set() # Set of image paths currently being loaded
    _thread_pool = None
    
    @classmethod
    def get_thread_pool(cls):
        if cls._thread_pool is None:
            from PySide6.QtCore import QThreadPool
            cls._thread_pool = QThreadPool()
            cls._thread_pool.setMaxThreadCount(4) 
        return cls._thread_pool



    def _process_image(self, image: QImage) -> QImage:
        """Wrapper for static method to maintain compatibility."""
        return self._process_image_static(image)


    def loadResource(self, type, name):
        import os
        from PySide6.QtGui import QTextDocument, QImage
        from PySide6.QtCore import QUrl
        
        if type == QTextDocument.ImageResource:
            url = name.toString() if isinstance(name, QUrl) else str(name)
            path = url
            if isinstance(name, QUrl) and name.isLocalFile():
                path = name.toLocalFile()
            
            # Normalize path for consistency
            path = os.path.normpath(path)
            
            # 1. Fast Check: Cache Hit
            if path in NoteEditor._image_cache:
                return NoteEditor._image_cache[path]
            
            # 2. Fast Check: Already Loading
            if path in NoteEditor._loading_images:
                return self._get_placeholder_image()
            
            # 3. Async Load (Handles path resolution, searching, and loading)
            # We delegate ALL non-cached loading to the background thread.
            # This avoids UI freezes and handles complicated path lookups.
            # print(f"DEBUG: loadResource starting async load for {path}")
            self._start_async_image_load(path)
            
            return self._get_placeholder_image()

        return super().loadResource(type, name)

    def _get_placeholder_image(self):
        # We need to cache per-theme or recreate if theme changes.
        # Simple approach: Check if cached image matches current theme preference.
        # Or just don't cache deeply if we want it dynamic.
        
        cache_key = f"_placeholder_img_{self.current_theme}"
        if not hasattr(NoteEditor, cache_key):
             # Create a simple placeholder
             img = QImage(600, 100, QImage.Format_ARGB32) # Generic size
             
             if self.current_theme == "Dark":
                 bg_color = QColor("#27272a") # Zinc-800
                 text_color = QColor("#71717a") # Zinc-500
             else:
                 bg_color = QColor("#f4f4f5") # Zinc-100
                 text_color = QColor("#a1a1aa") # Zinc-400
                 
             img.fill(bg_color)
             
             from PySide6.QtGui import QPainter, QPen
             p = QPainter(img)
             p.setPen(QPen(text_color))
             font = p.font()
             font.setPixelSize(14)
             p.setFont(font)
             p.drawText(img.rect(), Qt.AlignCenter, "Cargando imagen...")
             p.end()
             setattr(NoteEditor, cache_key, img)
             
        return getattr(NoteEditor, cache_key)

    def _start_async_image_load(self, path):
        NoteEditor._loading_images.add(path)
        
        loader = ImageLoader(path, self._process_image_static, self.fm.root_path)
        loader.signals.finished.connect(self._on_image_loaded)
        
        pool = self.get_thread_pool()
        pool.start(loader)

    def preload_images(self, paths, on_finish_callback=None):
        """
        Pre-loads a list of image paths into the cache in background.
        Calls on_finish_callback() when all are done or failed (best effort).
        """
        if not paths:
            if on_finish_callback:
                on_finish_callback()
            return

        # Filter out already cached
        needed = [p for p in paths if p not in NoteEditor._image_cache]
        
        if not needed:
            if on_finish_callback:
                on_finish_callback()
            return
            
        # We need a way to track progress for this specific batch
        # We'll use a simple counter mechanism or a group loader
        # Since this is likely called once during splash, we can keep it simple.
        
        # Keep references to prevent GC premature collection crashing signals
        # We attach it to the editor instance to persist until done
        self._active_preloaders = []
        
        total = len(needed)
        processed = 0

        def check_done():
            nonlocal processed
            processed += 1
            if processed >= total:
                if on_finish_callback:
                    # Enforce Main Thread for UI updates (callback starts rendering)
                    from PySide6.QtCore import QTimer
                    QTimer.singleShot(0, self, on_finish_callback)
                
                # Defer cleanup to ensure signals finish emitting and Python doesn't GC objects mid-flight
                from PySide6.QtCore import QTimer
                # We use a helper to clear
                def cleanup():
                     self._active_preloaders = []
                QTimer.singleShot(500, self, cleanup)
                    
        # Launch loaders
        for path in needed:
            # We reuse ImageLoader but we need to intercept the finished signal 
            # to decrement our local counter, while ALSO updating the cache globally.
            
            loader = ImageLoader(path, self._process_image_static, self.fm.root_path)
            
            # CRITICAL: Disable autoDelete to prevent C++ from deleting the object
            # while Python still holds a reference or signals are emitting.
            # We will let Python GC handle it when we clear _active_preloaders.
            loader.setAutoDelete(False)
            self._active_preloaders.append(loader)
            
            # Connect to global cache update first
            loader.signals.finished.connect(self._on_image_loaded_no_ui) 
            
            # Then connect to our progress tracker
            # We need to wrap check_done to accept arguments or ignore them
            loader.signals.finished.connect(lambda p, i: check_done())
            
            pool = self.get_thread_pool()
            pool.start(loader)

    def _on_image_loaded_no_ui(self, path, image):
        """Callback for preloading that only updates cache, no UI repaint."""
        self._cache_image(path, image)

    @staticmethod
    def _process_image_static(image):
        # Static version used by worker thread
        # Fix: Don't force resize to 600px which blurs small images (upscaling) and large images (fast downscale)
        # Instead, only downscale really large images to reasonable size for performance, using SmoothTransformation
        
        max_width = 1200
        if image.width() > max_width:
             image = image.scaledToWidth(max_width, Qt.SmoothTransformation)
        
        return image

    def _on_image_loaded(self, path, image):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QTextDocument
        
        if path in NoteEditor._loading_images:
            NoteEditor._loading_images.remove(path)
            
        # Add to Cache
        self._cache_image(path, image)
        
        # Update Document Resources
        # Since we set the name to the Absolute Path in render_images, 
        # that IS the key.
        doc = self.document()
        
        # We try both URL and String forms to be safe
        doc.addResource(QTextDocument.ImageResource, QUrl.fromLocalFile(path), image)
        doc.addResource(QTextDocument.ImageResource, QUrl(path), image)
        
        # Force Layout Update
        self.viewport().update()
        
        # Update image sizes to respect new image dimensions
        self.update_image_sizes()
        
        # Force redraw
        doc.markContentsDirty(0, doc.characterCount())
        
        # Line wrap hack
        mode = self.lineWrapMode()
        self.setLineWrapMode(self.LineWrapMode.NoWrap if mode == self.LineWrapMode.WidgetWidth else self.LineWrapMode.WidgetWidth)
        self.setLineWrapMode(mode)

    
    def render_images(self, start_pos=0, end_pos=None):
        """
        Scans the document for Markdown image links and inserts QTextImageFormat objects.
        Supports incremental rendering via start_pos/end_pos.
        """
        text = self.toPlainText()
        if end_pos is None:
            end_pos = len(text)
            
        # Optimization: Only scan the relevant substring (plus some context if needed?)
        # For simplicity, we scan the whole text but only process matches within range.
        # Scanning large text is fast; inserting images is expensive.
        # Ideally, we substring: substring = text[start_pos:end_pos]
        # But offsets need adjustment.
        
        cursor = self.textCursor()
        
        # 1. Collect all matches (Standard + WikiLink)
        matches = []
        
        # A. Standard Markdown: ![alt](url)
        from PySide6.QtCore import QRegularExpression
        regex_std = QRegularExpression(r"!\[.*?\]\((.*?)\)")
        
        # Use match iterator on the global text but verify range
        # Note: If text is HUGE, substring extraction might be better for regex PERF.
        # Let's try substring extraction for the scope.
        search_text = text[start_pos:end_pos]
        
        it_std = regex_std.globalMatch(search_text)
        while it_std.hasNext():
            m = it_std.next()
            # Adjust offsets to global
            g_start = start_pos + m.capturedStart()
            g_end = start_pos + m.capturedEnd()
            matches.append((g_start, g_end, m.captured(1), False))
            
        # B. Obsidian WikiLink: ![[filename|options]] or ![[filename]]
        regex_wiki = QRegularExpression(r"!\[\[(.*?)\]\]")
        it_wiki = regex_wiki.globalMatch(search_text)
        while it_wiki.hasNext():
            m = it_wiki.next()
            content = m.captured(1)
            if "|" in content:
                filename = content.split("|")[0]
            else:
                filename = content
            
            g_start = start_pos + m.capturedStart()
            g_end = start_pos + m.capturedEnd()
            matches.append((g_start, g_end, filename.strip(), True))
            
        # Sort matches by start position (descending) to prevent offset drift
        # Wait, if we use beginEditBlock and fixed offsets...
        # If we insert images, we replace characters? No, we insert AT position.
        # But we are NOT replacing the text code `![...]`. We are inserting the image
        # typically *after* or *as replacement*?
        # Original code: `cursor.setPosition(end); cursor.insertImage(...)`
        # This appends the image object AFTER the markdown text. It doesn't replace it.
        # So we process descending is still good practice.
        matches.sort(key=lambda x: x[0], reverse=True)
        
        if not matches: return

        cursor.beginEditBlock()
        try:
            for start, end, target, is_wikilink in matches:
                cursor.setPosition(end)
                
                from PySide6.QtGui import QTextImageFormat
                fmt = QTextImageFormat()
                fmt.setName(target) 
                # fmt.setWidth(600) # Removed hardcoded width to allow update_image_sizes to handle it
                
                cursor.insertImage(fmt)
        finally:
            cursor.endEditBlock()

    def append_chunk(self, chunk_text):
        """Appends text chunk and renders images and tables only within that chunk."""
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        start_pos = cursor.position()
        cursor.insertText(chunk_text)
        end_pos = cursor.position()
        
        # Render images and tables in the new chunk
        self.render_images(start_pos, end_pos)
        self.render_tables(start_pos, end_pos)

    def render_tables(self, start_pos=0, end_pos=None):
        """
        Scans the document for markdown table syntax and converts them to QTextTable objects.
        Supports incremental rendering via start_pos/end_pos.
        """
        text = self.toPlainText()
        if end_pos is None:
            end_pos = len(text)
        
        # Find all markdown tables in the specified range
        # A markdown table has lines that start with | and contain |
        lines = text.split('\n')
        
        # Track positions for replacement
        tables_to_render = []
        current_table_lines = []
        table_start_pos = 0
        line_pos = 0
        
        for i, line in enumerate(lines):
            line_start = line_pos
            line_end = line_pos + len(line)
            line_pos = line_end + 1  # +1 for newline
            
            # Check line is in our rendering range
            if line_end < start_pos or line_start > end_pos:
                if current_table_lines:
                    # End of range, finalize table if any
                    tables_to_render.append((table_start_pos, current_table_lines))
                    current_table_lines = []
                continue
            
            stripped = line.strip()
            
            # Check if this is a table line
            if stripped.startswith('|') and stripped.endswith('|'):
                if not current_table_lines:
                    table_start_pos = line_start
                current_table_lines.append(line)
            else:
                # Not a table line - finalize current table if any
                if current_table_lines:
                    tables_to_render.append((table_start_pos, current_table_lines))
                    current_table_lines = []
        
        # Don't forget last table
        if current_table_lines:
            tables_to_render.append((table_start_pos, current_table_lines))
        
        if not tables_to_render:
            return
        
        # Process tables in reverse order to avoid position drift
        cursor = self.textCursor()
        cursor.beginEditBlock()
        
        try:
            for table_start, table_lines in reversed(tables_to_render):
                # Parse the table
                if len(table_lines) < 2:
                    continue  # Need at least header + separator
                
                # Calculate table end position
                table_text = '\n'.join(table_lines)
                table_end = table_start + len(table_text)
                
                # Parse rows
                rows_data = []
                header_row = None
                
                for idx, line in enumerate(table_lines):
                    # Clean the line
                    cells = [cell.strip() for cell in line.strip('|').split('|')]
                    
                    # Skip separator line (contains only -, :, and spaces)
                    if idx == 1 and all(set(cell.replace('-', '').replace(':', '').replace(' ', '')) == set() for cell in cells):
                        continue
                    
                    if header_row is None:
                        header_row = cells
                    else:
                        rows_data.append(cells)
                
                if not header_row:
                    continue
                
                # Create the QTextTable
                num_cols = len(header_row)
                num_rows = len(rows_data) + 1  # +1 for header
                
                # Select and remove the markdown text
                cursor.setPosition(table_start)
                cursor.setPosition(table_end, QTextCursor.KeepAnchor)
                cursor.removeSelectedText()
                
                # Insert the table
                from PySide6.QtGui import QTextTableFormat, QTextCharFormat
                fmt = QTextTableFormat()
                fmt.setCellPadding(5)
                fmt.setCellSpacing(0)
                fmt.setBorder(1)
                fmt.setWidth(QTextLength(QTextLength.PercentageLength, 100))
                
                table = cursor.insertTable(num_rows, num_cols, fmt)
                
                # Fill header
                for col, header_text in enumerate(header_row):
                    cell = table.cellAt(0, col)
                    cell_cursor = cell.firstCursorPosition()
                    
                    # Make header bold
                    header_fmt = QTextCharFormat()
                    header_fmt.setFontWeight(700)
                    cell_cursor.setCharFormat(header_fmt)
                    cell_cursor.insertText(header_text)
                
                # Fill data rows
                for row_idx, row_data in enumerate(rows_data):
                    for col, cell_text in enumerate(row_data):
                        if col < num_cols:  # Safety check
                            cell = table.cellAt(row_idx + 1, col)
                            cell_cursor = cell.firstCursorPosition()
                            cell_cursor.insertText(cell_text)
                
        finally:
            cursor.endEditBlock()


    def _cache_image(self, image_id, image):
        """Add image to cache with LRU eviction. Key can be int or str."""
        # Evict oldest if at capacity
        while len(NoteEditor._image_cache) >= NoteEditor._max_cached_images:
            if NoteEditor._image_cache_order:
                oldest_id = NoteEditor._image_cache_order.pop(0)
                NoteEditor._image_cache.pop(oldest_id, None)
            else:
                break
        
        NoteEditor._image_cache[image_id] = image
        NoteEditor._image_cache_order.append(image_id)
    
    def clear_image_cache(cls):
        """Clear the image cache."""
        cls._image_cache.clear()
        cls._image_cache_order.clear()



# Worker Classes (Global Scope for Signals)
from PySide6.QtCore import QRunnable, QObject, Signal
from PySide6.QtGui import QImage
import os

class ImageLoaderSignals(QObject):
    finished = Signal(str, QImage)

class ImageLoader(QRunnable):
    def __init__(self, path, processor, root_path):
        super().__init__()
        self.path = path
        self.processor = processor
        self.root_path = root_path
        self.signals = ImageLoaderSignals()
        
    def run(self):
        target_path = self.path
        found = False
        
        if os.path.exists(target_path) and os.path.isfile(target_path):
            found = True
        elif self.root_path:
            # Smart Search
            basename = os.path.basename(self.path)
            # print(f"DEBUG: Searching for {basename} in vault...")
            
            # 1. Quick check commonly used folders
            candidates = [
                os.path.join(self.root_path, "images", basename),
                os.path.join(self.root_path, "adjuntos", basename), 
                os.path.join(self.root_path, "Adjuntos", basename),
                os.path.join(self.root_path, "assets", basename),
                os.path.join(self.root_path, basename)
            ]
            
            for c in candidates:
                if os.path.exists(c) and os.path.isfile(c):
                    target_path = c
                    found = True
                    # print(f"DEBUG: Found in quick candidate: {target_path}")
                    break
            
            # 2. Recursive Search (if not found in candidates)
            if not found:
                    for root, dirs, files in os.walk(self.root_path):
                        dirs[:] = [d for d in dirs if not d.startswith('.')]
                        if basename in files:
                            target_path = os.path.join(root, basename)
                            found = True
                            # print(f"DEBUG: Found via recursive walk: {target_path}")
                            break

        img = QImage()
        if found:
            try:
                loaded = QImage(target_path)
                if not loaded.isNull():
                    img = loaded
                    if self.processor:
                        img = self.processor(img)
                else:
                    print(f"DEBUG: Failed to load QImage from {target_path}")
            except Exception as e:
                    print(f"ERROR: Image load exception: {e}")
        else:
            print(f"DEBUG: Could not find image {self.path} - Root: {self.root_path}")
                                
        self.signals.finished.emit(self.path, img)
