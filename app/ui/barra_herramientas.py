
from PySide6.QtWidgets import QToolBar
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt

class FormatToolbar(QToolBar):
    def __init__(self, parent=None, text_editor=None):
        super().__init__("Barra de Formato", parent)
        self.setObjectName("FormatToolbar")
        self.text_editor = text_editor
        self.setVisible(True) # Visible by default
        self._setup_actions()
        
    def _setup_actions(self):
        if not self.text_editor:
            return

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
