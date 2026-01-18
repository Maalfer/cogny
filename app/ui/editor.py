from PySide6.QtWidgets import QTextEdit, QToolButton, QApplication
from PySide6.QtCore import QUrl, QByteArray, QBuffer, QIODevice, Qt, QSize
from PySide6.QtGui import QImage, QTextDocument, QColor, QTextFormat, QIcon, QGuiApplication, QTextCursor, QKeySequence, QTextLength
from app.ui.themes import ThemeManager

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

            
    def _wrap_selection(self, start_marker, end_marker=None):
        """Wraps selected text or inserts markers if empty."""
        if end_marker is None:
            end_marker = start_marker
            
        cursor = self.textCursor()
        if cursor.hasSelection():
            text = cursor.selectedText()
            # Basic toggle logic could be added here (check if already wrapped), 
            # but for now we just wrap.
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




    def apply_theme(self, theme_name: str, editor_bg: str = None):
        self.current_theme = theme_name
        
        if editor_bg is not None:
             self.current_editor_bg = editor_bg
        
        style = ThemeManager.get_editor_style(theme_name, self.current_editor_bg)
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
        
        self.update_code_block_visuals()

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
            super().wheelEvent(event)


    def update_margins(self):
        # Dynamic Centered Layout
        max_content_width = 1200

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
                    
                    new_width = int(base_width * scale)
                    img_fmt.setWidth(new_width)
                    
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
        # We disabled click-to-open for attachments.
        super().mouseReleaseEvent(event)



    def on_contents_change(self, position, charsRemoved, charsAdded):
        """Standard optimization: Only update blocks affected by the change."""
        if self.is_loading: return
        
        doc = self.document()
        
        # Determine range of change
        start_block = doc.findBlock(position)
        # End block is where the change ends (position + length of added text)
        # If charsRemoved > 0, we might have merged blocks, so checking current state at pos is usually enough?
        # Actually, safely check from start block to a reasonable lookahead or just until end of change.
        # But for code blocks, start/end of block tags matter. Status propagates.
        # So we should iterate from start block until ... status stops changing?
        # For simplicity in this optimization step:
        # Update from start_block to end of document? No, that's slow.
        # Update from start_block to end_block of the changed region.
        
        end_pos = position + charsAdded
        end_block = doc.findBlock(end_pos)
        
        # However, if we deleted a ```, the Whole rest of the document might change status.
        # Ideally, we should check if block state changed.
        # But QSyntaxHighlighter handles the state. We just apply Visuals based on it.
        # Since Visuals (Background) depend on State, and State depends on Highlighter...
        # We need to run AFTER highlighter. contentChange runs BEFORE highlighter usually?
        # Actually QTextDocument signals: contentsChange happens, then Highlighter updates.
        # So here, states might be stale?
        # Let's verify. If states are stale, we can't use this signal directly for visual update based on state.
        # We might need to listen to `highlighter.update`? PySide6 highlighter doesn't carry a signal.
        
        # Alternative: Use a timer to coalesce updates?
        # Or just trust that we can simply iterate the visible range or the whole doc if needed.
        # But we want to avoid iterating whole doc.
        
        # Valid Strategy:
        # 1. Update visual for modified range immediately (or via timer).
        # 2. If it's a structural change (contains ```), usually the user pauses typing.
        # Let's rely on the fact that for standard typing inside a block, only that block changes.
        
        self.update_code_block_visuals(start_block, end_block)

    def update_code_block_visuals(self, start_block=None, end_block_limit=None):
        # Use QTextBlockFormat for background color. 
        # This ensures it respects indentation and margins (unlike ExtraSelection).
        
        # Prevent Recursion (setBlockFormat triggers textChanged -> contentsChange might be triggered?)
        # contentsChange is triggered by structural changes. setBlockFormat DOES trigger it.
        # So blocking signals is CRITICAL.
        self.blockSignals(True)
        try:
            # 1. Get Color
            color = getattr(self, "code_bg_color", QColor("#EEF1F4"))
            
            cursor = self.textCursor()
            cursor.beginEditBlock()
            
            if start_block is None:
                block = self.document().begin()
            else:
                block = start_block
                
            while block.isValid():
                state = block.userState()
                
                # Check End Limit
                if end_block_limit and block.blockNumber() > end_block_limit.blockNumber():
                    # Optimization: If state matches previous behavior, we might stop?
                    # For now just stop at the modified range end.
                    # BUT if we are typing ``` start, the rest needs update.
                    # For strict correctness we should check if we changed the visual state.
                    # If we didn't change the visual state, we can simpler stop.
                    # Let's just process the range for speed. If scan is needed, user forces refresh or we assume highlighter handles?
                    # Actually, if I type ``` at top, the state changes for the whole doc.
                    # Highlighter updates states. I read them.
                    # If I read STALE states, I'm wrong.
                    # Since this runs on `contentsChange`, states might be STALE. 
                    # We might need `QTimer.singleShot(0, ...)` to run after highlighter.
                    break
                
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
        
        # ExtraSelections cleanup removed

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
                    fmt.setWidth(600) 
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

    def _start_async_image_load(self, path):
        NoteEditor._loading_images.add(path)
        
        loader = ImageLoader(path, self._process_image_static)
        loader.signals.finished.connect(self._on_image_loaded)
        
        pool = self.get_thread_pool()
        pool.start(loader)

    @staticmethod
    def _process_image_static(image):
        if image.isNull(): return image
        
        # Static version used by worker thread
        target_width = 600
        if image.width() != target_width:
             image = image.scaledToWidth(target_width, Qt.FastTransformation)
             
        out_img = QImage(image.size(), QImage.Format_ARGB32)
        out_img.fill(Qt.transparent)
        
        from PySide6.QtGui import QPainter, QPainterPath
        painter = QPainter(out_img)
        painter.setRenderHint(QPainter.Antialiasing)
        
        path = QPainterPath()
        rect = out_img.rect()
        path.addRoundedRect(0, 0, rect.width(), rect.height(), 12, 12)
        
        painter.setClipPath(path)
        painter.drawImage(0, 0, image)
        painter.end()
        return out_img

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
        if not hasattr(NoteEditor, "_placeholder_img"):
             # Create a simple gray placeholder
             img = QImage(600, 100, QImage.Format_ARGB32) # Generic size
             img.fill(QColor("#f0f0f0"))
             
             from PySide6.QtGui import QPainter, QPen
             p = QPainter(img)
             p.setPen(QPen(QColor("#bbbbbb")))
             p.drawText(img.rect(), Qt.AlignCenter, "Cargando imagen...")
             p.end()
             NoteEditor._placeholder_img = img
        return NoteEditor._placeholder_img

    def _start_async_image_load(self, path):
        NoteEditor._loading_images.add(path)
        
        from PySide6.QtCore import QRunnable, QObject, Signal, QImage
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
                from PySide6.QtGui import QImage
                target_path = self.path
                found = False
                
                if os.path.exists(target_path) and os.path.isfile(target_path):
                    found = True
                else:
                    # Smart Search
                    basename = os.path.basename(self.path)
                    print(f"DEBUG: Searching for {basename} in vault...")
                    
                    # 1. Quick check commonly used folders
                    candidates = [
                        os.path.join(self.root_path, "images", basename),
                        os.path.join(self.root_path, "adjuntos", basename), # lowercase
                        os.path.join(self.root_path, "Adjuntos", basename), # Title case
                        os.path.join(self.root_path, "assets", basename),
                        os.path.join(self.root_path, basename)
                    ]
                    
                    for c in candidates:
                        if os.path.exists(c) and os.path.isfile(c):
                            target_path = c
                            found = True
                            print(f"DEBUG: Found in quick candidate: {target_path}")
                            break
                    
                    # 2. Recursive Search (if not found in candidates)
                    if not found:
                         for root, dirs, files in os.walk(self.root_path):
                            dirs[:] = [d for d in dirs if not d.startswith('.')]
                            if basename in files:
                                target_path = os.path.join(root, basename)
                                found = True
                                print(f"DEBUG: Found via recursive walk: {target_path}")
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
                    print(f"DEBUG: Could not find image {self.path} anywhere.")
                                        
                # Always emit signal (with valid image or null) to cleanup loading state
                self.signals.finished.emit(self.path, img)

        loader = ImageLoader(path, self._process_image_static, self.fm.root_path)
        loader.signals.finished.connect(self._on_image_loaded)
        
        pool = self.get_thread_pool()
        pool.start(loader)

    @staticmethod
    def _process_image_static(image):
        # Static version used by worker thread
        target_width = 600
        if image.width() != target_width:
             image = image.scaledToWidth(target_width, Qt.FastTransformation)
             
        out_img = QImage(image.size(), QImage.Format_ARGB32)
        out_img.fill(Qt.transparent)
        
        from PySide6.QtGui import QPainter, QPainterPath, QBrush
        painter = QPainter(out_img)
        painter.setRenderHint(QPainter.Antialiasing)
        
        path = QPainterPath()
        rect = out_img.rect()
        path.addRoundedRect(0, 0, rect.width(), rect.height(), 12, 12)
        
        painter.setClipPath(path)
        painter.drawImage(0, 0, image)
        painter.end()
        return out_img

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
        
        # Force redraw
        doc.markContentsDirty(0, doc.characterCount())
        
        # Line wrap hack
        mode = self.lineWrapMode()
        self.setLineWrapMode(self.LineWrapMode.NoWrap if mode == self.LineWrapMode.WidgetWidth else self.LineWrapMode.WidgetWidth)
        self.setLineWrapMode(mode)

    
    def render_images(self):
        """Scans the document for Markdown image links (Standard & WikiLink) and inserts QTextImageFormat objects."""
        text = self.toPlainText()
        cursor = self.textCursor()
        
        # 1. Collect all matches (Standard + WikiLink)
        # We need to handle them in reverse order of position to avoid invalidating offsets.
        # Format: (start, end, image_source_or_name, is_wikilink)
        matches = []
        
        # A. Standard Markdown: ![alt](url)
        from PySide6.QtCore import QRegularExpression, QUrl
        regex_std = QRegularExpression(r"!\[.*?\]\((.*?)\)")
        it_std = regex_std.globalMatch(text)
        while it_std.hasNext():
            m = it_std.next()
            matches.append((m.capturedStart(), m.capturedEnd(), m.captured(1), False))
            
        # B. Obsidian WikiLink: ![[filename|options]] or ![[filename]]
        # Note: We need to capture the filename part before any '|'
        regex_wiki = QRegularExpression(r"!\[\[(.*?)\]\]")
        it_wiki = regex_wiki.globalMatch(text)
        while it_wiki.hasNext():
            m = it_wiki.next()
            content = m.captured(1)
            # Handle piping for dimensions: "image.png|100"
            if "|" in content:
                filename = content.split("|")[0]
            else:
                filename = content
            matches.append((m.capturedStart(), m.capturedEnd(), filename.strip(), True))
            
        # Sort matches by start position (descending) to process bottom-up
        matches.sort(key=lambda x: x[0], reverse=True)
        
        for start, end, target, is_wikilink in matches:
            # OPTIMIZATION: Use the target string directly.
            # We let loadResource handle the resolution lazily and correctly using the context (current_note_path).
            # This avoids ALL I/O in the layout pass.
            
            # Insert Image
            cursor.setPosition(end)
            
            from PySide6.QtGui import QTextImageFormat
            fmt = QTextImageFormat()
            fmt.setName(target) 
            fmt.setWidth(600) # Default
            
            cursor.insertImage(fmt)

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
    
    @classmethod
    def clear_image_cache(cls):
        """Clear the image cache (useful when switching databases)."""
        cls._image_cache.clear()
        cls._image_cache_order.clear()

    def _process_image(self, image: QImage) -> QImage:
        """Process image to enforce uniform style: 
           - Fixed Width (600px)
           - Rounded Corners (12px)
        """
        target_width = 600
        from PySide6.QtCore import Qt
        
        # 1. Scale uniform width
        # Use FastTransformation for performance (Smooth is too slow for large images)
        if image.width() != target_width:
             # print(f"DEBUG: Scaling image {image.width()}x{image.height()} -> {target_width}")
             image = image.scaledToWidth(target_width, Qt.FastTransformation)
             
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

# Worker Classes (Global Scope for Signals)
from PySide6.QtCore import QRunnable, QObject, Signal

class ImageLoaderSignals(QObject):
    finished = Signal(str, QImage)

class ImageLoader(QRunnable):
    def __init__(self, path, processor):
        super().__init__()
        self.path = path
        self.processor = processor
        self.signals = ImageLoaderSignals()
        
    def run(self):
        try:
            img = QImage(self.path)
            if not img.isNull():
                # Process off-thread
                processed = self.processor(img)
                self.signals.finished.emit(self.path, processed)
        except Exception as e:
            print(f"Async load error {self.path}: {e}")
