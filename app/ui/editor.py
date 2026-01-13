from PySide6.QtWidgets import QTextEdit, QToolButton, QApplication
from PySide6.QtCore import QUrl, QByteArray, QBuffer, QIODevice, Qt, QSize
from PySide6.QtGui import QImage, QTextDocument, QColor, QTextFormat, QIcon, QGuiApplication, QTextCursor, QKeySequence
from app.database.manager import DatabaseManager
from app.ui.themes import ThemeManager

class NoteEditor(QTextEdit):
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
        self.image_cache = {}

            
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

    def clear_image_cache(self):
        self.image_cache = {}


    def apply_theme(self, theme_name: str, editor_bg: str = None):
        self.current_theme = theme_name
        
        # Update stored custom bg if provided
        if editor_bg is not None:
             self.current_editor_bg = editor_bg
        
        # Get base style with stored bg
        style = ThemeManager.get_editor_style(theme_name, self.current_editor_bg)
        
        # Inject dynamic font size via setFont (CSS usually ignored for size if setHtml used)
        font_size = getattr(self, "current_font_size", 14)
        
        # Apply Stylesheet (Colors, Padding, etc.)
        self.setStyleSheet(style)
        self.code_bg_color = ThemeManager.get_code_bg_color(theme_name)
        
        # Apply Font Size directly to Widget and Document
        font = self.font()
        font.setPointSize(font_size)
        self.setFont(font)
        # Also helpful for proper parsing of new content
        # self.document().setDefaultFont(font) # Should cascade from widget, but being explicit helps
        
        # Revert Native Margins
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
        self.current_font_size = max(8, self.current_font_size + delta)
        self.apply_theme(self.current_theme) # Uses stored self.current_editor_bg automatically

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
        from PySide6.QtWidgets import QFileIconProvider
        from PySide6.QtCore import QFileInfo
        from PySide6.QtGui import QPixmap
        
        # Get System Icon
        info = QFileInfo(filename)
        icon_provider = QFileIconProvider()
        icon = icon_provider.icon(info)
        pixmap = icon.pixmap(48, 48) # Larger icon
        
        ba = QByteArray()
        buffer = QBuffer(ba)
        buffer.open(QIODevice.WriteOnly)
        pixmap.save(buffer, "PNG")
        base64_data = ba.toBase64().data().decode()
        
        # HTML with Table for Vertical Layout: Icon (Top), Filename (Bottom)
        # We wrap it in a table to ensure it acts as a structured unit.
        # HTML with Table for Vertical Layout: Icon (Top), Filename (Bottom)
        # Both wrapped in anchor for consistent behavior
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
                # Check for Attachments FIRST
                is_att, att_id, table_range = self.cursor_contains_attachment(check_cursor)
                # Check for Attachments FIRST
                is_att, att_id, table_range = self.cursor_contains_attachment(check_cursor)
                if is_att:
                    # Use shared interactive method (handles confirmation and deletion)
                    # We pass table_range if we have it, otherwise it relies on cursor but interactive expects range to clear text.
                    # Interactive method uses self.textCursor() if range is passed.
                    # Wait, if we call interactive, does it use the CURRENT cursor position?
                    # The interactive function clears text based on 'table_range'. 
                    # If 'table_range' is derived from check_cursor, it should be correct.
                    # But we should ensure we return True/consume event.
                    
                    self.delete_attachment_interactive(att_id, table_range)
                    return # Event consumed regardless of Yes/No? 
                    # Actually if No, we shouldn't consume 'Delete' key if it was just text?
                    # But here 'is_att' is True, so we are over an attachment.
                    # If user says No, we probably don't want standard 'delete' to happen which might corrupt the attachment HTML structure.
                    # So consuming is safer.
                    pass
                             
                # Check for Images (only if not an attachment, to avoid detecting the file icon as an image)
                elif self.cursor_contains_image(check_cursor):
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
                
                # Remove standard "Delete" action to avoid confusion for attachments
                for action in menu.actions():
                    text = action.text().replace("&", "") # Handle accelerator
                    # Check for "Delete" or standard shortcut
                    if text == "Delete" or action.shortcut() == QKeySequence.Delete:
                        menu.removeAction(action)
                        
                menu.addSeparator()
                
                # Open Action
                action_open = menu.addAction("Open File")
                # Fix: triggered emits (checked), so lambda must accept args or use *args
                action_open.triggered.connect(lambda *args: self.open_attachment(att_id))
                
                # Save As Action
                action_save = menu.addAction("Save File As...")
                action_save.triggered.connect(lambda *args: self.save_attachment_as(att_id))
                
                # Delete Action
                menu.addSeparator()
                action_delete = menu.addAction("Delete File")
                # Using lambda with captured variables
                action_delete.triggered.connect(lambda *args: self.delete_attachment_interactive(att_id, table_range))
                
                menu.exec(event.globalPos())
                return
            except ValueError:
                pass
            
        super().contextMenuEvent(event)

    def delete_attachment_interactive(self, att_id, table_range):
        from app.ui.widgets import ModernConfirm
        if ModernConfirm.show(self, "Delete File", "Are you sure you want to delete this file permanently from the database?", "Delete", "Cancel"):
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
        save_path, _ = QFileDialog.getSaveFileName(self, "Save Attachment", filename)
        
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
                    # Check Cache
                    if not hasattr(self, 'image_cache'):
                         self.image_cache = {}
                         
                    if url in self.image_cache:
                         return self.image_cache[url]
                         
                    image_id = int(url.split("/")[-1])
                    blob = self.db.get_image(image_id)
                    if blob:
                        img = QImage()
                        img.loadFromData(blob)
                        processed_img = self._process_image(img)
                        
                        # Cache it
                        self.image_cache[url] = processed_img
                        return processed_img
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
