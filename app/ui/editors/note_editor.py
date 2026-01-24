from PySide6.QtWidgets import QTextEdit, QToolButton
from PySide6.QtCore import QUrl, QByteArray, QBuffer, QIODevice, Qt, QTimer
from PySide6.QtGui import QImage, QTextDocument, QColor, QTextFormat, QGuiApplication, QTextCursor, QKeySequence, QTextLength
from app.ui.themes import ThemeManager
from app.features.images.loader import ImageHandler
import os
import re

class NoteEditor(QTextEdit):
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
        # Simple insertion
        cursor.insertText(f"```{language}\\\n\\\n```")
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
                    
                    variant = self.document().resource(QTextDocument.ImageResource, name)
                    
                    if variant:
                         img = variant 
                         if img and not img.isNull():
                              original_width = img.width()
                              
                              # Smart Scaling Logic
                              target_width = original_width * scale
                              limit = max_width * scale
                              
                              if target_width > limit:
                                  final_width = int(limit)
                              else:
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
            
        full_text = "\\n".join(code_text)
        QGuiApplication.clipboard().setText(full_text)
        
        sender.setText("Copied!")
        QTimer.singleShot(2000, lambda b=sender: b.setText("Copy"))

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
                if self.cursor_contains_image(check_cursor):
                    from app.ui.components.dialogs import ModernConfirm
                    # Using ModernConfirm instead of QMessageBox directly for consistency
                    ret = ModernConfirm.show(self, "Eliminar Imagen", 
                                               "¿Estás seguro de que quieres eliminar la(s) imagen(es) seleccionada(s)?")
                    if not ret:
                        return

        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            cursor = self.textCursor()
            block = cursor.block()
            text = block.text().strip()
            
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
        start = min(cursor.anchor(), cursor.position())
        end = max(cursor.anchor(), cursor.position())
        
        doc = self.document()
        block = doc.findBlock(start)
        end_block = doc.findBlock(end)
        
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                
                frag_start = frag.position()
                frag_end = frag_start + frag.length()
                
                if frag_end > start and frag_start < end:
                    if frag.charFormat().isImageFormat():
                        return True
                        
                it += 1
                
            if block == end_block:
                break
            block = block.next()
            
        return False

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        
        cursor = self.cursorForPosition(event.pos())
        
        # Check if cursor is on an image or inside an image link
        hit_image = False
        image_path = None
        
        # 1. Check Image Format (Rendered Image)
        fmt = cursor.charFormat()
        if fmt.isImageFormat():
            hit_image = True
            image_path = fmt.toImageFormat().name()
        
        # 1b. Check Right Side (Cursor might be BEFORE the image if clicked on left half)
        if not hit_image:
             cursor_right = QTextCursor(cursor)
             cursor_right.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor)
             if cursor_right.charFormat().isImageFormat():
                 hit_image = True
                 image_path = cursor_right.charFormat().toImageFormat().name()
            
        # 2. Check Text Link (Source Mode) if 1 failed
        if not hit_image:
             # Basic regex check around cursor... complex. 
             # Simpler: check anchor
             anchor = self.anchorAt(event.pos())
             if anchor:
                 # Check if it looks like an image
                 if anchor.lower().endswith(('.png','.jpg','.jpeg','.gif','.webp','.svg')):
                     hit_image = True
                     image_path = anchor
                     
        if hit_image and image_path:
            menu.addSeparator()
            action_show = menu.addAction("Abrir en explorador de archivos")
            # Resolve path here or inside helper? Helper takes absolute or relative?
            # Helper takes absolute. We need to resolve relative paths against Vault Root.
            # But duplicate logic?
            # Let's import show_in_explorer and do lightweight resolution here or let helper handle?
            # Our helper only takes path.
            # NoteEditor knows FM root.
            
            # Helper logic:
            def open_helper():
                from app.utils.system_utils import show_in_explorer
                final_path = image_path
                if not os.path.isabs(final_path) and not final_path.startswith("file:"):
                     final_path = os.path.join(self.fm.root_path, final_path)
                show_in_explorer(final_path)
                
            action_show.triggered.connect(open_helper)
            menu.addSeparator()

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
            
            def delete_table():
                cursor.setPosition(table.firstCursorPosition().position() - 1)
                cursor.setPosition(table.lastCursorPosition().position() + 1, QTextCursor.KeepAnchor)
                cursor.removeSelectedText()
                
            menu.addAction("Eliminar Tabla", delete_table)
            
            menu.exec(event.globalPos())
            return
            
        super().contextMenuEvent(event)

    def mouseDoubleClickEvent(self, event):
        anchor = self.anchorAt(event.pos())
        if anchor and anchor.startswith("attachment://"):
            return
        super().mouseDoubleClickEvent(event)

    def mouseReleaseEvent(self, event):
        cursor = self.cursorForPosition(event.pos())
        
        block = cursor.block()
        text = block.text()
        pos_in_block = cursor.positionInBlock()
        
        for match in re.finditer(r"\[\[(#.*?)\]\]", text):
            start = match.start()
            end = match.end()
            if start <= pos_in_block <= end:
                target = match.group(1) # "#Header"
                self.scroll_to_header(target)
                return

        super().mouseReleaseEvent(event)

    def scroll_to_header(self, header_target):
        target_clean = header_target.lstrip('#').strip().lower()
        
        block = self.document().begin()
        while block.isValid():
            text = block.text().strip()
            if text.startswith("#"):
                header_content = re.sub(r"^#+\s*", "", text).lower().strip()
                
                if header_content == target_clean:
                    cursor = self.textCursor()
                    cursor.setPosition(block.position())
                    self.setTextCursor(cursor)
                    self.ensureCursorVisible()
                    return
            block = block.next()

    def generate_toc(self):
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
                    
                    if title.lower() == "índice":
                         block = block.next()
                         continue
                         
                    link = f"[[#{title}]]"
                    indent = "  " * (level - 1)
                    toc_lines.append(f"{indent}* {link}")
                    
            block = block.next()
            
        if len(toc_lines) > 1:
            cursor = self.textCursor()
            cursor.insertText("\\n".join(toc_lines) + "\\n\\n")

    def on_contents_change(self, position, charsRemoved, charsAdded):
        if getattr(self, "is_loading", False):
            return
        QTimer.singleShot(0, self.update_extra_selections)

    def update_extra_selections(self):
        extra_selections = []
        code_bg_color = getattr(self, "code_bg_color", QColor("#EEF1F4"))
        
        block = self.document().begin()
        while block.isValid():
            state = block.userState()
            
            if state > 0: 
                sel = QTextEdit.ExtraSelection()
                sel.format.setBackground(code_bg_color)
                sel.format.setProperty(QTextFormat.FullWidthSelection, True) 
                
                cursor = self.textCursor()
                cursor.setPosition(block.position())
                cursor.setPosition(block.position() + block.length(), QTextCursor.KeepAnchor)
                sel.cursor = cursor
                extra_selections.append(sel)
                
            block = block.next()
            
        self.setExtraSelections(extra_selections)
        self.update_copy_buttons()

    def update_highlighting(self):
        if hasattr(self.document(), "findBlock"):
            cursor = self.textCursor()
            block = self.document().findBlock(cursor.position())
            
            if hasattr(self, "highlighter") and self.highlighter:
                if self.highlighter.active_block != block:
                     prev_block = self.highlighter.active_block
                     self.highlighter.active_block = block
                     
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
                ba = QByteArray()
                buffer = QBuffer(ba)
                buffer.open(QIODevice.WriteOnly)
                image.save(buffer, "PNG")
                data = ba.data()
                
                import time
                filename = f"image_{int(time.time()*1000)}.png"
                self._save_and_insert_image(data, filename, image)
            return

        if source.hasUrls():
            processed_any = False
            for url in source.urls():
                if url.isLocalFile():
                    path = url.toLocalFile()
                    ext = os.path.splitext(path)[1].lower()
                    if ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.svg']:
                        try:
                            with open(path, 'rb') as f:
                                data = f.read()
                            
                            filename = os.path.basename(path)
                            image = QImage(path)
                            self._save_and_insert_image(data, filename, image)
                            processed_any = True
                        except Exception as e:
                            print(f"Error reading pasted image file: {e}")
                    elif ext == '.md':
                        # Handle Markdown File Paste -> Import to Vault
                        try:
                            filename = os.path.basename(path)
                            with open(path, 'r', encoding='utf-8') as f:
                                content = f.read()
                            
                            # Determine save folder (same logic as images or root?)
                            # Usually notes go to Root or Current Folder.
                            # Let's import to Root by default for simplicity or ask?
                            # For "Vibe", importing to Root is standard Obsidian-like behavior if not configured.
                            # We use FileManager.save_note logic.
                            
                            # Check if exists
                            target_path = filename # Relative to root
                            
                            # Safeguard: Check file size (limit to 10MB to prevent UI freeze on accidental huge file paste)
                            if os.path.getsize(path) > 10 * 1024 * 1024:
                                print(f"WARNING: skipped pasting huge file {path}")
                                continue

                            # We should probably use FileManager's unique name logic if exists
                            # But FileManager.save_note overwrites.
                            # Let's check existence first.
                            counter = 1
                            base, _ = os.path.splitext(filename)
                            
                            MAX_ITER = 1000
                            while self.fm.file_exists(target_path) and counter < MAX_ITER:
                                target_path = f"{base}_{counter}.md"
                                counter += 1
                            
                            if counter >= MAX_ITER:
                                print("ERROR: Could not find unique filename after 1000 tries.")
                                continue
                                
                            self.fm.save_note(target_path, content)
                            
                            # Insert Link
                            # Use wiki link
                            link_name = os.path.splitext(os.path.basename(target_path))[0]
                            self.textCursor().insertText(f"[[{link_name}]]")
                            processed_any = True
                            
                            # from app.ui.components.dialogs import ModernInfo # circular import risk?
                            # Feedback is nice
                            # Feedback is nice
                            # ModernInfo.show(self, "Nota Importada", f"Se ha copiado '{filename}' a la bóveda.")
                            
                        except Exception as e:
                            print(f"Error importing pasted note: {e}")
            
            if processed_any:
                return

        if source.hasText():
            self.insertPlainText(source.text())
            return
            
        return super().insertFromMimeData(source)

    def _save_and_insert_image(self, data, filename, qimage_obj=None):
        try:
            from PySide6.QtCore import QSettings
            settings = QSettings()
            target_folder = settings.value("attachment_folder", "/").strip()
            if not target_folder: target_folder = "/"
            
            if target_folder == "/" or target_folder == "\\" or not target_folder:
                target_folder = "." 
            
            # Save Image
            rel_path_root = self.fm.save_image(data, filename, folder=target_folder)
            full_abs_path = os.path.join(self.fm.root_path, rel_path_root)
            
            if qimage_obj:
                img_proc = ImageHandler.process_image_static(qimage_obj)
                ImageHandler.cache_image(full_abs_path, img_proc)
            
            # Use WikiLink for cleaner, robust referencing (Search-based)
            # ![[filename]]
            # This avoids the confusing ../ relative paths for user
            base_filename = os.path.basename(rel_path_root) # Ensure just filename if in root/images
            
            # If in subfolder like 'images/', we might want [[images/filename]] or just [[filename]] if unique?
            # Standard Obsidian: [[filename]] finds it anywhere.
            # But if specific folder is desired?
            # Let's use [[filename]] as it is most magical/vibe.
            # But if collision?
            # Let's use the rel_path if it's not in root?
            # If in root: [[image.png]]
            # If in images/: [[images/image.png]] (Valid wikilink too, or [[image.png]] works)
            
            # Simplest Strategy: [[filename]] and rely on smart loader. 
            # But for clarity, if it is in a subfolder, maybe show it?
            # User wants Root. So [[image.png]] is perfect.
            
            final_link_text = f"![[{base_filename}]]"
            self.textCursor().insertText(final_link_text)
            
            try:
                from PySide6.QtGui import QTextImageFormat
                fmt = QTextImageFormat()
                fmt.setName(full_abs_path) # Use absolute path for immediate display
                
                # Verify image validity before insertion
                if qimage_obj and not qimage_obj.isNull():
                     # Scale if needed for initial display performance? 
                     # No, let render logic handle it.
                     pass
                else:
                     print("WARNING: Pasted image object is null or invalid.")

                self.textCursor().insertImage(fmt)
                print(f"DEBUG: Inserted image {full_abs_path}")
            except Exception as insert_err:
                print(f"ERROR inserting QImage content: {insert_err}")
            
        except Exception as e:
            print(f"Error processing pasted image: {e}")
            import traceback
            traceback.print_exc()
            from app.ui.components.dialogs import ModernAlert
            # Try/Except to prevent crash if dialog fails (e.g. recursion)
            try:
                # ModernAlert.show(self, "Error al Pegar Imagen", str(e))
                pass
            except:
                pass

    def loadResource(self, type, name):
        from PySide6.QtGui import QImage
        
        if type == QTextDocument.ImageResource:
            url = name.toString() if isinstance(name, QUrl) else str(name)
            path = url
            if isinstance(name, QUrl) and name.isLocalFile():
                path = name.toLocalFile()
            
            path = os.path.normpath(path)
            
            # 1. Fast Check: Cache Hit
            cached = ImageHandler.get_cached_image(path)
            if cached:
                return cached
            
            # 2. Fast Check: Already Loading
            if ImageHandler.is_loading(path):
                return self._get_placeholder_image()
            
            # 3. Async Load
            self._start_async_image_load(path)
            
            return self._get_placeholder_image()

        return super().loadResource(type, name)

    def _get_placeholder_image(self):
        cache_key = f"_placeholder_img_{self.current_theme}"
        if not hasattr(NoteEditor, cache_key):
             img = QImage(600, 100, QImage.Format_ARGB32) 
             
             if self.current_theme == "Dark":
                 bg_color = QColor("#27272a") 
                 text_color = QColor("#71717a") 
             else:
                 bg_color = QColor("#f4f4f5") 
                 text_color = QColor("#a1a1aa") 
                 
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
        ImageHandler.load_async(path, self.fm.root_path, self._on_image_loaded)

    def _on_image_loaded(self, path, image):
        ImageHandler.mark_finished(path)
        
        # Add to Cache
        ImageHandler.cache_image(path, image)
        
        doc = self.document()
        doc.addResource(QTextDocument.ImageResource, QUrl.fromLocalFile(path), image)
        doc.addResource(QTextDocument.ImageResource, QUrl(path), image)
        
        self.viewport().update()
        self.update_image_sizes()
        doc.markContentsDirty(0, doc.characterCount())
        
        # Line wrap hack to force layout recalc
        mode = self.lineWrapMode()
        self.setLineWrapMode(self.LineWrapMode.NoWrap if mode == self.LineWrapMode.WidgetWidth else self.LineWrapMode.WidgetWidth)
        self.setLineWrapMode(mode)

    @classmethod
    def clear_image_cache(cls):
        ImageHandler.clear_cache()

    def preload_images(self, paths, on_finish_callback=None):
        """Pre-loads a list of image paths into the cache in background."""
        # For simplicity, we just trigger load_async for all without a group callback 
        # because tracking is complex across threads. 
        # But for splash screen, we need completion.
        
        # Simplified implementation using ImageHandler
        if not paths:
            if on_finish_callback: on_finish_callback()
            return

        needed = [p for p in paths if not ImageHandler.get_cached_image(p)]
        if not needed:
            if on_finish_callback: on_finish_callback()
            return

        total = len(needed)
        processed = 0
        
        def check(p, i):
            nonlocal processed
            processed += 1
            if processed >= total:
                if on_finish_callback:
                    QTimer.singleShot(0, lambda: on_finish_callback())

        for path in needed:
            ImageHandler.load_async(path, self.fm.root_path, check)

    def render_images(self, start_pos=0, end_pos=None):
        text = self.toPlainText()
        if end_pos is None:
            end_pos = len(text)
            
        cursor = self.textCursor()
        matches = []
        
        from PySide6.QtCore import QRegularExpression
        regex_std = QRegularExpression(r"!\[.*?\]\((.*?)\)")
        search_text = text[start_pos:end_pos]
        
        it_std = regex_std.globalMatch(search_text)
        while it_std.hasNext():
            m = it_std.next()
            g_start = start_pos + m.capturedStart()
            g_end = start_pos + m.capturedEnd()
            matches.append((g_start, g_end, m.captured(1), False))
            
        regex_wiki = QRegularExpression(r"!\[\[(.*?)\]\]")
        it_wiki = regex_wiki.globalMatch(search_text)
        while it_wiki.hasNext():
            m = it_wiki.next()
            content = m.captured(1)
            filename = content.split("|")[0] if "|" in content else content
            g_start = start_pos + m.capturedStart()
            g_end = start_pos + m.capturedEnd()
            matches.append((g_start, g_end, filename.strip(), True))
            
        matches.sort(key=lambda x: x[0], reverse=True)
        
        if not matches: return

        cursor.beginEditBlock()
        try:
            for start, end, target, is_wikilink in matches:
                cursor.setPosition(end)
                from PySide6.QtGui import QTextImageFormat
                fmt = QTextImageFormat()
                fmt.setName(target) 
                cursor.insertImage(fmt)
        finally:
            cursor.endEditBlock()

    def append_chunk(self, chunk_text):
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        start_pos = cursor.position()
        cursor.insertText(chunk_text)
        end_pos = cursor.position()
        self.render_images(start_pos, end_pos)
        self.render_tables(start_pos, end_pos)

    def render_tables(self, start_pos=0, end_pos=None):
        text = self.toPlainText()
        if end_pos is None:
            end_pos = len(text)
        
        lines = text.split('\\n')
        tables_to_render = []
        current_table_lines = []
        table_start_pos = 0
        line_pos = 0
        
        for i, line in enumerate(lines):
            line_start = line_pos
            line_end = line_pos + len(line)
            line_pos = line_end + 1
            
            if line_end < start_pos or line_start > end_pos:
                if current_table_lines:
                    tables_to_render.append((table_start_pos, current_table_lines))
                    current_table_lines = []
                continue
            
            stripped = line.strip()
            if stripped.startswith('|') and stripped.endswith('|'):
                if not current_table_lines:
                    table_start_pos = line_start
                current_table_lines.append(line)
            else:
                if current_table_lines:
                    tables_to_render.append((table_start_pos, current_table_lines))
                    current_table_lines = []
        
        if current_table_lines:
            tables_to_render.append((table_start_pos, current_table_lines))
        
        if not tables_to_render:
            return
        
        cursor = self.textCursor()
        cursor.beginEditBlock()
        try:
            for table_start, table_lines in reversed(tables_to_render):
                if len(table_lines) < 2: continue
                
                table_text = '\\n'.join(table_lines)
                table_end = table_start + len(table_text)
                
                rows_data = []
                header_row = None
                
                for idx, line in enumerate(table_lines):
                    cells = [cell.strip() for cell in line.strip('|').split('|')]
                    if idx == 1 and all(set(cell.replace('-', '').replace(':', '').replace(' ', '')) == set() for cell in cells):
                        continue
                    if header_row is None: header_row = cells
                    else: rows_data.append(cells)
                
                if not header_row: continue
                
                num_cols = len(header_row)
                num_rows = len(rows_data) + 1
                
                cursor.setPosition(table_start)
                cursor.setPosition(table_end, QTextCursor.KeepAnchor)
                cursor.removeSelectedText()
                
                from PySide6.QtGui import QTextTableFormat, QTextCharFormat
                fmt = QTextTableFormat()
                fmt.setCellPadding(5)
                fmt.setCellSpacing(0)
                fmt.setBorder(1)
                fmt.setWidth(QTextLength(QTextLength.PercentageLength, 100))
                
                table = cursor.insertTable(num_rows, num_cols, fmt)
                
                for col, header_text in enumerate(header_row):
                    cell = table.cellAt(0, col)
                    cell_cursor = cell.firstCursorPosition()
                    header_fmt = QTextCharFormat()
                    header_fmt.setFontWeight(700)
                    cell_cursor.setCharFormat(header_fmt)
                    cell_cursor.insertText(header_text)
                
                for row_idx, row_data in enumerate(rows_data):
                    for col, cell_text in enumerate(row_data):
                        if col < num_cols:
                            cell = table.cellAt(row_idx + 1, col)
                            cell_cursor = cell.firstCursorPosition()
                            cell_cursor.insertText(cell_text)
        finally:
            cursor.endEditBlock()

    # show_in_explorer removed (moved to app/utils/system_utils.py)

