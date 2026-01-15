from PySide6.QtWidgets import QTextEdit, QToolButton, QApplication
from PySide6.QtCore import QUrl, QByteArray, QBuffer, QIODevice, Qt, QSize
from PySide6.QtGui import QImage, QTextDocument, QColor, QTextFormat, QIcon, QGuiApplication, QTextCursor, QKeySequence, QTextLength
from app.database.manager import DatabaseManager
from app.ui.themes import ThemeManager

class NoteEditor(QTextEdit):
    # Class-level image cache shared across instances
    _image_cache = {}  # {image_id: QImage}
    _image_cache_order = []  # For LRU eviction
    _max_cached_images = 100  # Limit memory usage
    
    def __init__(self, db_manager: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.cursorPositionChanged.connect(self.update_highlighting)
        # Optimized: Use contentsChange for incremental updates instead of full textChanged scan
        self.document().contentsChange.connect(self.on_contents_change)
        self.textChanged.connect(self.update_copy_buttons)
        self.verticalScrollBar().valueChanged.connect(self.update_copy_buttons_position)
        
        self.copy_buttons = []
        self.current_theme = "Light"
        self.current_font_size = 14
        self.current_editor_bg = None
        self.apply_theme("Light") # Default

            
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
        
    def insert_attachment(self, att_id, filename):
        from PySide6.QtWidgets import QFileIconProvider
        from PySide6.QtCore import QFileInfo
        from PySide6.QtGui import QPixmap
        
        info = QFileInfo(filename)
        icon_provider = QFileIconProvider()
        icon = icon_provider.icon(info)
        pixmap = icon.pixmap(48, 48)
        
        ba = QByteArray()
        buffer = QBuffer(ba)
        buffer.open(QIODevice.WriteOnly)
        pixmap.save(buffer, "PNG")
        base64_data = ba.toBase64().data().decode()
        
        html = f"""
        <table border="0" style="margin-top: 10px; margin-bottom: 10px;">
            <tr>
                <td align="center">
                    <a href="attachment://{att_id}"><img src="data:image/png;base64,{base64_data}" width="48" height="48" /></a>
                </td>
            </tr>
            <tr>
                <td align="center">
                    <a href="attachment://{att_id}" style="color: #666; text-decoration: none; font-size: 10px;">{filename}</a>
                </td>
            </tr>
        </table>
        <br>
        """
        self.textCursor().insertHtml(html)

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
                is_att, att_id, table_range = self.cursor_contains_attachment(check_cursor)
                if is_att:
                    self.delete_attachment_interactive(att_id, table_range)
                    return
                              
                elif self.cursor_contains_image(check_cursor):
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

    def cursor_contains_attachment(self, cursor):
        """Checks if the given cursor range contains an attachment link.
           Returns: (Found_Bool, Attachment_ID, (StartPos, EndPos))
        """
        start = min(cursor.anchor(), cursor.position())
        end = max(cursor.anchor(), cursor.position())
        
        doc = self.document()
        
        # Check if we are inside a table structure that represents an attachment
        # Iterate over blocks in range
        block = doc.findBlock(start)
        end_block = doc.findBlock(end)
        
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                frag_start = frag.position()
                frag_end = frag_start + frag.length()
                
                # Intersection check
                if frag_end > start and frag_start < end:
                    fmt = frag.charFormat()
                    href = fmt.anchorHref()
                    if href.startswith("attachment://"):
                         try:
                             att_id = int(href.replace("attachment://", ""))
                             
                             # Identify the containing table range to ensure clean deletion
                             # If we are in a table, currentTable() might help if we use a cursor there.
                             # But we are iterating blocks.
                             # A block inside a table cell knows it's in a table (Qt internals).
                             # We can check textTable() for the cursor at this position.
                             temp_cursor = QTextCursor(doc)
                             temp_cursor.setPosition(frag_start)
                             table = temp_cursor.currentTable()
                             
                             if table:
                                 # Return the range of the whole table
                                 t_start = table.firstCursorPosition().position()
                                 t_end = table.lastCursorPosition().position()
                                 # We want to include the surrounding frame chars if possible?
                                 # Actually, selecting first to last pos of table content leaves the frame.
                                 # To remove the table, we need to select the range covering the table.
                                 # Table is usually an object in the parent frame.
                                 # Ideally: select range from position before table to position after.
                                 # But simplified: Just returning None for range lets default delete happen if we don't care about residuals.
                                 # But user complained about partial deletion.
                                 
                                 # Workaround: Select from start of table - 1 to end of table + 1?
                                 # Or uses `table.firstCursorPosition().block().position()` etc.
                                 # Let's try to get precise range.
                                 return True, att_id, (t_start - 1, t_end + 1)
                             else:
                                 return True, att_id, None
                         except:
                             return True, None, None
                             
                it += 1
                
            if block == end_block:
                break
            block = block.next()
            
        return False, None, None

    def contextMenuEvent(self, event):
        # 1. Determine Attachment ID and Range at mouse position
        anchor = self.anchorAt(event.pos())
        att_id = None
        table_range = None
        
        # We need to find the range to support deletion from UI
        cursor = self.cursorForPosition(event.pos())
        
        # Helper to scan for attachment at cursor block
        block = cursor.block()
        if block.isValid():
             it = block.begin()
             while not it.atEnd():
                 frag = it.fragment()
                 fmt = frag.charFormat()
                 href = fmt.anchorHref()
                 if href.startswith("attachment://"):
                     try:
                         found_id = int(href.replace("attachment://", ""))
                         
                         # If anchorAt found simple link, it matches. 
                         # If anchorAt failed but we found a fragment at cursor, use it.
                         # We check if cursor is roughly inside or we just take the first one in the block (simple structure assumption)?
                         # Better: Check point intersection.
                         # cursor.position() is a single point.
                         f_start = frag.position()
                         f_end = f_start + frag.length()
                         c_pos = cursor.position()
                         
                         # Check if click is within this fragment (inclusive)
                         # OR if we relied on anchorAt which implies we clicked the link
                         if (c_pos >= f_start and c_pos <= f_end) or (anchor == href):
                             att_id = found_id
                             
                             # Get Table Range
                             temp_cursor = QTextCursor(self.document())
                             temp_cursor.setPosition(f_start)
                             table = temp_cursor.currentTable()
                             if table:
                                 t_start = table.firstCursorPosition().position()
                                 t_end = table.lastCursorPosition().position()
                                 table_range = (t_start - 1, t_end + 1)
                             break
                     except ValueError:
                         pass
                 it += 1

        if att_id:
            try:
                menu = self.createStandardContextMenu()
                
                # Attachment Actions
                action_open = menu.addAction("Abrir Archivo")
                action_open.triggered.connect(lambda _: self.open_attachment(att_id))
                
                action_save_as = menu.addAction("Guardar Como...")
                action_save_as.triggered.connect(lambda _: self.save_attachment_as(att_id))
                
                # Remove standard delete if present to avoid confusion
                for action in menu.actions():
                    if "Delete" in action.text() or "Eliminar" in action.text():
                         menu.removeAction(action)
                         
                action_delete = menu.addAction("Eliminar Archivo")
                # Pass table_range to delete handler to remove text too
                action_delete.triggered.connect(lambda _: self.delete_attachment_interactive(att_id, table_range))
                
                menu.exec(event.globalPos())
                return 
            except ValueError:
                pass
                
        # --- TABLE CONTEXT MENU ---
        # Obtain cursor at MOUSE position, not current caret position
        cursor = self.cursorForPosition(event.pos())
        table = cursor.currentTable()
        if table:
            menu = self.createStandardContextMenu()
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

    def delete_attachment_interactive(self, att_id, table_range):
        from app.ui.widgets import ModernConfirm
        if ModernConfirm.show(self, "Eliminar Archivo", "¿Estás seguro de que quieres eliminar este archivo permanentemente de la base de datos?", "Eliminar", "Cancelar"):
             # DB Delete
             self.db.delete_attachment(att_id)
             
             # UI Delete
             if table_range:
                 cursor = self.textCursor()
                 cursor.setPosition(table_range[0])
                 cursor.setPosition(table_range[1], QTextCursor.KeepAnchor)
                 cursor.removeSelectedText()

    def mouseDoubleClickEvent(self, event):
        # Prevent double click from doing anything special with attachments
        anchor = self.anchorAt(event.pos())
        if anchor and anchor.startswith("attachment://"):
            return
            
        # Fallback check
        cursor = self.cursorForPosition(event.pos())
        is_att, _, _ = self.cursor_contains_attachment(cursor)
        if is_att:
            return
            
        super().mouseDoubleClickEvent(event)

    def mouseReleaseEvent(self, event):
        # We disabled click-to-open for attachments.
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
        import subprocess
        import sys
        from PySide6.QtGui import QDesktopServices
        
        # We try to keep the extension
        name, ext = os.path.splitext(filename)
        
        try:
            fd, path = tempfile.mkstemp(suffix=ext, prefix=f"cogni_{name}_")
            with os.fdopen(fd, 'wb') as f:
                f.write(data)
            
            # Open using subprocess and xdg-open for Linux (more robust)
            if sys.platform.startswith('linux'):
                 subprocess.Popen(['xdg-open', path])
            else:
                 QDesktopServices.openUrl(QUrl.fromLocalFile(path))
                 
        except Exception as e:
            print(f"Error opening attachment: {e}")

    def save_attachment_as(self, att_id):
        from PySide6.QtWidgets import QFileDialog
        
        # Retrieve from DB
        data_row = self.db.get_attachment(att_id)
        if not data_row:
            return
            
        filename, data = data_row
        
        # Ask user for location
        save_path, _ = QFileDialog.getSaveFileName(self, "Guardar Adjunto", filename)
        
        if save_path:
            try:
                with open(save_path, 'wb') as f:
                     f.write(data)
            except Exception as e:
                print(f"Error saving attachment: {e}")

    def on_contents_change(self, position, charsRemoved, charsAdded):
        """Standard optimization: Only update blocks affected by the change."""
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
                    
                    # Check cache first (LRU)
                    if image_id in NoteEditor._image_cache:
                        # Move to end of LRU order (most recently used)
                        if image_id in NoteEditor._image_cache_order:
                            NoteEditor._image_cache_order.remove(image_id)
                        NoteEditor._image_cache_order.append(image_id)
                        return NoteEditor._image_cache[image_id]
                    
                    # Load from database
                    blob = self.db.get_image(image_id)
                    if blob:
                        img = QImage()
                        img.loadFromData(blob)
                        processed_img = self._process_image(img)
                        
                        # Add to cache with LRU eviction
                        self._cache_image(image_id, processed_img)
                        return processed_img
                except Exception as e:
                    print(f"Error loading image: {e}")
        
        return super().loadResource(type, name)
    
    def _cache_image(self, image_id, image):
        """Add image to cache with LRU eviction."""
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
