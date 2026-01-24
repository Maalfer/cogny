from PySide6.QtGui import QTextCursor, QTextTableFormat, QTextLength, QTextCharFormat, QColor
import re

class TableHandler:
    @staticmethod
    def render_tables(editor, start_pos=0, end_pos=None):
        text = editor.toPlainText()
        if end_pos is None:
            end_pos = len(text)
        
        lines = text.split('\n')
        tables_to_render = []
        current_table_lines = []
        table_start_pos = 0
        line_pos = 0
        
        for i, line in enumerate(lines):
            line_start = line_pos
            line_end = line_pos + len(line)
            line_pos = line_end + 1
            
            stripped = line.strip()
            # Relaxed check: allow rows that don't strictly end with |
            if stripped.startswith('|'):
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
        
        cursor = editor.textCursor()
        cursor.beginEditBlock()
        try:
            for table_start, table_lines in reversed(tables_to_render):
                if len(table_lines) < 2: continue
                
                # Check if table already exists at this position to avoid double rendering
                cursor.setPosition(table_start)
                if cursor.currentTable():
                    continue

                table_text = '\n'.join(table_lines)
                table_end = table_start + len(table_text)
                
                rows_data = []
                header_row = None
                
                for idx, line in enumerate(table_lines):
                    cells = [cell.strip() for cell in line.strip('|').split('|')]
                    # simple divider check
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
                
                fmt = QTextTableFormat()
                fmt.setCellPadding(5)
                fmt.setCellSpacing(0)
                fmt.setBorder(1)
                fmt.setWidth(QTextLength(QTextLength.PercentageLength, 100))
                
                table = cursor.insertTable(num_rows, num_cols, fmt)
                
                # Render Header
                for col, header_text in enumerate(header_row):
                    cell = table.cellAt(0, col)
                    cell_cursor = cell.firstCursorPosition()
                    header_fmt = QTextCharFormat()
                    header_fmt.setFontWeight(700)
                    cell_cursor.setCharFormat(header_fmt)
                    TableHandler._render_cell_content(cell_cursor, header_text, getattr(editor, "code_bg_color", "#EEF1F4"))
                
                # Render Rows
                for row_idx, row_data in enumerate(rows_data):
                    for col, cell_text in enumerate(row_data):
                        if col < num_cols:
                            cell = table.cellAt(row_idx + 1, col)
                            cell_cursor = cell.firstCursorPosition()
                            TableHandler._render_cell_content(cell_cursor, cell_text, getattr(editor, "code_bg_color", "#EEF1F4"))
        except Exception as e:
            print(f"Error rendering table: {e}")
            import traceback
            traceback.print_exc()
        finally:
            cursor.endEditBlock()

    @staticmethod
    def _render_cell_content(cursor, text, code_bg_color):
        """Renders rich text content within a table cell."""
        token_pattern = re.compile(r"(\*\*.*?\*\*|\*.*?\*|`.*?`)")
        parts = token_pattern.split(text)
        
        for part in parts:
            if not part: continue
            
            format = QTextCharFormat()
            content = part
            
            if part.startswith("**") and part.endswith("**") and len(part) > 4:
                format.setFontWeight(700)
                content = part[2:-2]
            elif part.startswith("*") and part.endswith("*") and len(part) > 2:
                format.setFontItalic(True)
                content = part[1:-1]
            elif part.startswith("`") and part.endswith("`") and len(part) > 2:
                format.setBackground(QColor(code_bg_color))
                format.setFontFamilies(["Consolas", "Monaco", "Courier New", "monospace"])
                content = part[1:-1]
            
            cursor.insertText(content, format)

    @staticmethod
    def insert_table(editor, rows=2, cols=2):
        cursor = editor.textCursor()
        fmt = QTextTableFormat()
        fmt.setCellPadding(5)
        fmt.setCellSpacing(0)
        fmt.setBorder(1)
        fmt.setWidth(QTextLength(QTextLength.PercentageLength, 100))
        
        cursor.insertTable(rows, cols, fmt)
        editor.setTextCursor(cursor)

    @staticmethod
    def handle_context_menu(editor, menu, cursor):
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
                # Safe deletion of table structure
                c = table.firstCursorPosition()
                c.setPosition(table.firstCursorPosition().position() - 1)
                c.setPosition(table.lastCursorPosition().position() + 1, QTextCursor.KeepAnchor)
                c.removeSelectedText()
                
            menu.addAction("Eliminar Tabla", delete_table)
