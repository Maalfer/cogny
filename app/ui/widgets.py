from PySide6.QtWidgets import QPlainTextEdit, QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QLineEdit, QFrame, QGraphicsDropShadowEffect, QWidget, QListWidget, QListWidgetItem, QColorDialog, QComboBox
from PySide6.QtCore import Qt, Signal, QSize, QSettings
from PySide6.QtGui import QColor

class TitleEditor(QPlainTextEdit):
    return_pressed = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setTabChangesFocus(True)
        self.textChanged.connect(self.update_height)
        self.update_height()

    def update_height(self):
        doc_height = self.document().size().height()
        margins = self.contentsMargins()
        new_height = int(doc_height + 35) 
        if new_height < 60: new_height = 60
        self.setFixedHeight(new_height)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_height()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if not (event.modifiers() & Qt.ShiftModifier):
               self.return_pressed.emit()
               return
        super().keyPressEvent(event)

# --- MODERN DIALOGS ---

class ModernDialog(QDialog):
    def __init__(self, title, message, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)
        
        # Main Container (Rounded, Shadow)
        self.container = QFrame()
        self.container.setStyleSheet("""
            QFrame {
                background-color: #2D2D2D;
                border: 1px solid #3F3F3F;
                border-radius: 12px;
            }
        """)
        
        # Shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 100))
        shadow.setOffset(0, 5)
        self.container.setGraphicsEffect(shadow)
        
        self.layout.addWidget(self.container)
        
        # Content Layout
        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(20, 20, 20, 20)
        self.content_layout.setSpacing(15)
        self.container.setLayout(self.content_layout)
        
        # Title
        if title:
            self.title_label = QLabel(title)
            self.title_label.setStyleSheet("color: #FFFFFF; font-size: 18px; font-weight: bold; border: none;")
            self.content_layout.addWidget(self.title_label)
            
        # Message
        if message:
            self.msg_label = QLabel(message)
            self.msg_label.setWordWrap(True)
            self.msg_label.setStyleSheet("color: #CCCCCC; font-size: 14px; border: none;")
            self.content_layout.addWidget(self.msg_label)
            
        # Button Area
        self.button_layout = QHBoxLayout()
        self.button_layout.addStretch()
        self.content_layout.addLayout(self.button_layout)

    def add_button(self, text, role="normal", callback=None):
        btn = QPushButton(text)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedHeight(32)
        
        if role == "primary":
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #3b82f6; 
                    color: white; 
                    border-radius: 6px;
                    padding: 0 16px;
                    font-weight: bold;
                    border: none;
                }
                QPushButton:hover { background-color: #2563eb; }
                QPushButton:pressed { background-color: #1d4ed8; }
            """)
        elif role == "danger":
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #ef4444; 
                    color: white; 
                    border-radius: 6px;
                    padding: 0 16px;
                    font-weight: bold;
                    border: none;
                }
                QPushButton:hover { background-color: #dc2626; }
                QPushButton:pressed { background-color: #b91c1c; }
            """)
        else:
            # Secondary / Cancel
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #3F3F3F; 
                    color: #E0E0E0; 
                    border-radius: 6px;
                    padding: 0 15px;
                    border: none;
                }
                QPushButton:hover { background-color: #4B4B4B; }
            """)
            
        if callback:
            btn.clicked.connect(callback)
        else:
            if role in ["primary", "danger"]:
                btn.clicked.connect(self.accept)
            else:
                btn.clicked.connect(self.reject)
                
        self.button_layout.addWidget(btn)
        return btn

class ModernInfo(ModernDialog):
    @staticmethod
    def show(parent, title, message):
        dlg = ModernInfo(title, message, parent)
        dlg.exec()

    def __init__(self, title, message, parent=None):
        super().__init__(title, message, parent)
        self.add_button("Aceptar", "primary")

class ModernAlert(ModernDialog):
    @staticmethod
    def show(parent, title, message):
        dlg = ModernAlert(title, message, parent)
        dlg.exec()

    def __init__(self, title, message, parent=None):
        super().__init__(title, message, parent)
        self.add_button("Cerrar", "danger")

class ModernConfirm(ModernDialog):
    @staticmethod
    def show(parent, title, message, yes_text="Sí", no_text="Cancelar"):
        dlg = ModernConfirm(title, message, yes_text, no_text, parent)
        return dlg.exec() == QDialog.Accepted

    def __init__(self, title, message, yes_text, no_text, parent=None):
        super().__init__(title, message, parent)
        self.add_button(no_text, "normal")
        self.add_button(yes_text, "primary")

class ModernInput(ModernDialog):
    @staticmethod
    def get_text(parent, title, label, text=""):
        dlg = ModernInput(title, label, text, parent)
        if dlg.exec() == QDialog.Accepted:
            return dlg.input.text(), True
        return "", False

    def __init__(self, title, label, text, parent=None):
        super().__init__(title, label, parent)
        
        self.input = QLineEdit(text)
        self.input.setStyleSheet("""
            QLineEdit {
                background-color: #1E1E1E;
                color: #FFFFFF;
                border: 1px solid #3F3F3F;
                border-radius: 6px;
                padding: 8px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 1px solid #3b82f6;
            }
        """)
        # Insert input before buttons
        self.content_layout.insertWidget(2, self.input)
        
        self.add_button("Cancelar", "normal")
        self.add_button("Aceptar", "primary")
        
        self.input.returnPressed.connect(self.accept)
        self.input.setFocus()

class ModernSelection(ModernDialog):
    @staticmethod
    def get_item(parent, title, label, items, current=0, editable=False):
        dlg = ModernSelection(title, label, items, current, parent)
        if dlg.exec() == QDialog.Accepted:
            # Return item, ok
            item = dlg.list_widget.currentItem()
            if item:
                return item.text(), True
        return None, False

    def __init__(self, title, label, items, current, parent=None):
        super().__init__(title, label, parent)
        
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: #1E1E1E;
                color: #FFFFFF;
                border: 1px solid #3F3F3F;
                border-radius: 6px;
                padding: 4px;
                font-size: 14px;
                outline: none;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 4px;
            }
            QListWidget::item:selected {
                background-color: #3b82f6;
                color: white;
            }
            QListWidget::item:hover:!selected {
                background-color: #2D2D2D;
            }
        """)
        
        for item_text in items:
            self.list_widget.addItem(item_text)
            
        if 0 <= current < len(items):
            self.list_widget.setCurrentRow(current)
            
        self.content_layout.insertWidget(2, self.list_widget)
        
        self.add_button("Cancelar", "normal")
        self.add_button("Seleccionar", "primary")
        
        self.list_widget.doubleClicked.connect(self.accept)

class ThemeSettingsDialog(ModernDialog):
    @staticmethod
    def show_dialog(parent):
        dlg = ThemeSettingsDialog(parent)
        if dlg.exec() == QDialog.Accepted:
             return True
        return False

    def __init__(self, parent=None):
        super().__init__("Configuración de Tema", None, parent)
        self.settings = QSettings()
        
        # Grid-like layout manually
        # Row 1: Base Theme
        row1 = QHBoxLayout()
        tk_label = QLabel("Tema Base:")
        tk_label.setStyleSheet("color: #CCCCCC; font-size: 14px;")
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Light", "Dark"])
        current_theme = self.settings.value("theme", "Dark")
        self.theme_combo.setCurrentText(current_theme)
        self.theme_combo.setStyleSheet("""
            QComboBox {
                background-color: #1E1E1E;
                color: white;
                border: 1px solid #3F3F3F;
                border-radius: 4px;
                padding: 4px;
            }
        """)
        row1.addWidget(tk_label)
        row1.addWidget(self.theme_combo)
        self.content_layout.addLayout(row1)
        
        # Row 2: Editor BG
        row2 = QHBoxLayout()
        editor_label = QLabel("Fondo del Editor:")
        editor_label.setStyleSheet("color: #CCCCCC; font-size: 14px;")
        
        self.editor_bg_btn = QPushButton("Elegir Color")
        self.editor_bg_btn.setCursor(Qt.PointingHandCursor)
        self.current_editor_bg = self.settings.value("theme_custom_editor_bg", "")
        self.update_btn_style(self.editor_bg_btn, self.current_editor_bg)
        self.editor_bg_btn.clicked.connect(self.pick_editor_bg)
        
        row2.addWidget(editor_label)
        row2.addWidget(self.editor_bg_btn)
        self.content_layout.addLayout(row2)
        
        # Row 3: Sidebar BG
        row3 = QHBoxLayout()
        sidebar_label = QLabel("Fondo de la Barra Lateral:")
        sidebar_label.setStyleSheet("color: #CCCCCC; font-size: 14px;")
        
        self.sidebar_bg_btn = QPushButton("Elegir Color")
        self.sidebar_bg_btn.setCursor(Qt.PointingHandCursor)
        self.current_sidebar_bg = self.settings.value("theme_custom_sidebar_bg", "")
        self.update_btn_style(self.sidebar_bg_btn, self.current_sidebar_bg)
        self.sidebar_bg_btn.clicked.connect(self.pick_sidebar_bg)
        
        row3.addWidget(sidebar_label)
        row3.addWidget(self.sidebar_bg_btn)
        self.content_layout.addLayout(row3)
        
        # Row 4: Reset Button
        reset_btn = QPushButton("Restaurar Valores por Defecto")
        reset_btn.setCursor(Qt.PointingHandCursor)
        reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #3F3F3F;
                color: #E0E0E0;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 6px;
                margin-top: 10px;
            }
            QPushButton:hover { background-color: #4F4F4F; }
        """)
        reset_btn.clicked.connect(self.reset_defaults)
        self.content_layout.addWidget(reset_btn)
        
        self.add_button("Cancelar", "normal")
        self.add_button("Guardar y Aplicar", "primary", self.save_settings)
        
    def update_btn_style(self, btn, color_str):
        if color_str:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color_str};
                    color: {'black' if self.is_light(color_str) else 'white'};
                    border: 1px solid #555555;
                    border-radius: 4px;
                    padding: 6px;
                }}
            """)
            btn.setText(color_str)
        else:
             btn.setStyleSheet("""
                QPushButton {
                    background-color: #3F3F3F;
                    color: #E0E0E0;
                    border: 1px solid #555555;
                    border-radius: 4px;
                    padding: 6px;
                }
             """)
             btn.setText("Default")

    def is_light(self, color_str):
        c = QColor(color_str)
        return c.lightness() > 128

    def pick_editor_bg(self):
        c = QColorDialog.getColor(QColor(self.current_editor_bg) if self.current_editor_bg else Qt.white, self, "Seleccionar Fondo del Editor")
        if c.isValid():
            self.current_editor_bg = c.name()
            self.update_btn_style(self.editor_bg_btn, self.current_editor_bg)

    def pick_sidebar_bg(self):
        c = QColorDialog.getColor(QColor(self.current_sidebar_bg) if self.current_sidebar_bg else Qt.white, self, "Seleccionar Fondo de la Barra Lateral")
        if c.isValid():
            self.current_sidebar_bg = c.name()
            self.update_btn_style(self.sidebar_bg_btn, self.current_sidebar_bg)

    def reset_defaults(self):
        self.current_editor_bg = ""
        self.current_sidebar_bg = ""
        self.update_btn_style(self.editor_bg_btn, "")
        self.update_btn_style(self.sidebar_bg_btn, "")
        # Reset combo to Dark? Or keep current?
        # User said "volve r a poner todo como estaba al principio" -> Usually default.
        self.theme_combo.setCurrentText("Dark")

    def save_settings(self):
        self.settings.setValue("theme", self.theme_combo.currentText())
        self.settings.setValue("theme_custom_editor_bg", self.current_editor_bg)
        self.settings.setValue("theme_custom_sidebar_bg", self.current_sidebar_bg)
        self.accept()
