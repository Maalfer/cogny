
from PySide6.QtWidgets import QToolBar
from PySide6.QtGui import QAction, QIcon
from PySide6.QtCore import Qt

class FormatToolbar(QToolBar):
    def __init__(self, parent=None, text_editor=None):
        super().__init__("Barra de Formato", parent)
        self.setObjectName("FormatToolbarV2")
        self.setMovable(False)
        self.text_editor = text_editor
        self.setVisible(True) # Visible by default
        self._setup_actions()
        
    def _setup_actions(self):
        if not self.text_editor:
            return


        # Undo
        action_undo = QAction("↶", self)
        action_undo.setToolTip("Deshacer")
        action_undo.triggered.connect(self.text_editor.undo)
        font = action_undo.font()
        font.setBold(True)
        action_undo.setFont(font)
        self.addAction(action_undo)

        # Redo
        action_redo = QAction("↷", self)
        action_redo.setToolTip("Rehacer")
        action_redo.triggered.connect(self.text_editor.redo)
        action_redo.setFont(font)
        self.addAction(action_redo)

        self.addSeparator()

        # Bold
        action_bold = QAction("N", self) # N for Negrita (Spanish)
        action_bold.setToolTip("Negrita (Bold)")
        action_bold.triggered.connect(self.text_editor.toggle_bold)
        action_bold.setText("N")
        font = action_bold.font()
        font.setBold(True)
        action_bold.setFont(font)
        self.addAction(action_bold)
        
        # Italic
        action_italic = QAction("K", self)
        action_italic.setToolTip("Cursiva (Italic)")
        action_italic.triggered.connect(self.text_editor.toggle_italic)
        font = action_italic.font()
        font.setItalic(True)
        action_italic.setText("K")
        action_italic.setFont(font)
        self.addAction(action_italic)
        
        # Underline
        action_underline = QAction("S", self)
        action_underline.setToolTip("Subrayado (Underline)")
        action_underline.triggered.connect(self.text_editor.toggle_underline)
        font = action_underline.font()
        font.setUnderline(True)
        action_underline.setText("S")
        action_underline.setFont(font)
        self.addAction(action_underline)

        # Highlight
        # Use system icon if available, else Unicode marker
        icon = QIcon.fromTheme("format-text-highlight")
        if icon.isNull():
             # Fallback to yellow highlighter unicode if system icon missing
             action_highlight = QAction("🖍", self)
        else:
             action_highlight = QAction(icon, "Resaltar", self)
             
        action_highlight.setToolTip("Resaltar (Highlight)")
        action_highlight.triggered.connect(self.text_editor.toggle_highlight)
        self.addAction(action_highlight)

        self.addSeparator()

        # Headers
        for i in range(1, 4):
            action = QAction(f"H{i}", self)
            action.setToolTip(f"Título {i}")
            # Use distinct font size for icon? 
            # Or just bold text
            font = action.font()
            font.setBold(True)
            action.setFont(font)
            
            # Capture variable i in lambda default arg
            action.triggered.connect(lambda checked=False, level=i: self.text_editor.toggle_header(level))
            self.addAction(action)

        self.addSeparator()

        # Insert Table
        action_table = QAction("Tabla", self)
        action_table.setToolTip("Insertar Tabla (2x2)")
        # Using lambda safely since self is retained
        action_table.triggered.connect(lambda: self.text_editor.insert_table(2, 2))
        self.addAction(action_table)
        
        # Insert TOC
        action_toc = QAction("Índice", self)
        action_toc.setToolTip("Insertar Índice (TOC)")
        action_toc.triggered.connect(self.text_editor.generate_toc)
        font = action_toc.font()
        font.setBold(True)
        action_toc.setFont(font)
        self.addAction(action_toc)
        
        # Insert Code Block
        action_code = QAction("Code", self)
        action_code.setToolTip("Insertar Bloque de Código (Python)")
        action_code.triggered.connect(lambda: self.text_editor.insert_code_block("python"))
        font = action_code.font()
        font.setBold(True)
        action_code.setFont(font)
        self.addAction(action_code)
