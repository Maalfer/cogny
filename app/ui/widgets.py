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
    # Removed update_height and resizeEvent to allow manual resizing via QSplitter
    pass

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
        
        self.settings = QSettings()
        self.current_theme = self.settings.value("theme", "Dark")
        
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)
        
        # Determine specific colors based on theme
        if self.current_theme in ["Dark", "Dracula"]:
            bg_color = "#18181b"
            border_color = "#3f3f46"
            text_color = "#e4e4e7"
            subtext_color = "#a1a1aa"
            shadow_color = QColor(0, 0, 0, 100)
        else:
            bg_color = "#ffffff"
            border_color = "#e4e4e7"
            text_color = "#18181b"
            subtext_color = "#52525b"
            shadow_color = QColor(0, 0, 0, 40)

        # Main Container (Rounded, Shadow)
        self.container = QFrame()
        self.container.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 12px;
            }}
        """)
        
        # Shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setColor(shadow_color)
        shadow.setOffset(0, 8)
        self.container.setGraphicsEffect(shadow)
        
        self.layout.addWidget(self.container)
        
        # Content Layout
        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(24, 24, 24, 24)
        self.content_layout.setSpacing(16)
        self.container.setLayout(self.content_layout)
        
        # Title
        if title:
            self.title_label = QLabel(title)
            self.title_label.setStyleSheet(f"color: {text_color}; font-size: 18px; font-weight: 600; border: none;")
            self.content_layout.addWidget(self.title_label)
            
        # Message
        if message:
            self.msg_label = QLabel(message)
            self.msg_label.setWordWrap(True)
            self.msg_label.setStyleSheet(f"color: {subtext_color}; font-size: 14px; border: none; line-height: 1.5;")
            self.content_layout.addWidget(self.msg_label)
            
        # Button Area
        self.button_layout = QHBoxLayout()
        self.button_layout.addStretch()
        self.content_layout.addLayout(self.button_layout)

    def add_button(self, text, role="normal", callback=None):
        btn = QPushButton(text)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedHeight(34)
        
        if self.current_theme in ["Dark", "Dracula"]:
            if role == "primary":
                # Blue-600 to Blue-700
                style = """
                    QPushButton {
                        background-color: #3b82f6; 
                        color: white; 
                        border-radius: 6px;
                        padding: 0 16px;
                        font-weight: 600;
                        border: none;
                    }
                    QPushButton:hover { background-color: #2563eb; }
                    QPushButton:pressed { background-color: #1d4ed8; }
                """
            elif role == "danger":
                # Red-500 to Red-600
                style = """
                    QPushButton {
                        background-color: #ef4444; 
                        color: white; 
                        border-radius: 6px;
                        padding: 0 16px;
                        font-weight: 600;
                        border: none;
                    }
                    QPushButton:hover { background-color: #dc2626; }
                    QPushButton:pressed { background-color: #b91c1c; }
                """
            else:
                # Zinc-800 to Zinc-700
                style = """
                    QPushButton {
                        background-color: #27272a; 
                        color: #e4e4e7; 
                        border: 1px solid #3f3f46;
                        border-radius: 6px;
                        padding: 0 16px;
                        font-weight: 500;
                    }
                    QPushButton:hover { background-color: #3f3f46; }
                    QPushButton:pressed { background-color: #52525b; }
                """
        else: # Light
            if role == "primary":
                # Blue-600 to Blue-700
                style = """
                    QPushButton {
                        background-color: #2563eb; 
                        color: white; 
                        border-radius: 6px;
                        padding: 0 16px;
                        font-weight: 600;
                        border: none;
                    }
                    QPushButton:hover { background-color: #1d4ed8; }
                    QPushButton:pressed { background-color: #1e40af; }
                """
            elif role == "danger":
                # Red-600 to Red-700
                style = """
                    QPushButton {
                        background-color: #dc2626; 
                        color: white; 
                        border-radius: 6px;
                        padding: 0 16px;
                        font-weight: 600;
                        border: none;
                    }
                    QPushButton:hover { background-color: #b91c1c; }
                    QPushButton:pressed { background-color: #991b1b; }
                """
            else:
                # White/Gray border
                style = """
                    QPushButton {
                        background-color: #ffffff; 
                        color: #18181b; 
                        border: 1px solid #e4e4e7;
                        border-radius: 6px;
                        padding: 0 16px;
                        font-weight: 500;
                    }
                    QPushButton:hover { background-color: #f4f4f5; }
                    QPushButton:pressed { background-color: #e4e4e7; border-color: #d4d4d8; }
                """

        btn.setStyleSheet(style)
            
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
        
        if self.current_theme in ["Dark", "Dracula"]:
            input_style = """
                QLineEdit {
                    background-color: #27272a;
                    color: #e4e4e7;
                    border: 1px solid #3f3f46;
                    border-radius: 6px;
                    padding: 8px;
                    font-size: 14px;
                }
                QLineEdit:focus {
                    border: 1px solid #3b82f6;
                    background-color: #18181b;
                }
            """
        else:
            input_style = """
                QLineEdit {
                    background-color: #ffffff;
                    color: #18181b;
                    border: 1px solid #e4e4e7;
                    border-radius: 6px;
                    padding: 8px;
                    font-size: 14px;
                }
                QLineEdit:focus {
                    border: 1px solid #2563eb;
                    background-color: #fcfcfc;
                }
            """

        self.input.setStyleSheet(input_style)
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
        
        if self.current_theme in ["Dark", "Dracula"]:
            list_style = """
                QListWidget {
                    background-color: #27272a;
                    color: #e4e4e7;
                    border: 1px solid #3f3f46;
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
                    background-color: #3f3f46;
                }
            """
        else:
            list_style = """
                QListWidget {
                    background-color: #ffffff;
                    color: #18181b;
                    border: 1px solid #e4e4e7;
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
                    background-color: #2563eb;
                    color: white;
                }
                QListWidget::item:hover:!selected {
                    background-color: #f4f4f5;
                }
            """
            
        self.list_widget.setStyleSheet(list_style)
        
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
        # We assume parent has config_manager if it's MainWindow
        if not hasattr(parent, 'config_manager'):
             print("Error: Parent does not have config_manager")
             return False
             
        dlg = ThemeSettingsDialog(parent.config_manager, parent)
        if dlg.exec() == QDialog.Accepted:
             return True
        return False

    def __init__(self, config_manager, parent=None):
        super().__init__("Configuración de Tema", None, parent)
        self.config_manager = config_manager

        
        # Grid-like layout manually
        # Row 1: Base Theme
        row1 = QHBoxLayout()
        tk_label = QLabel("Tema Base:")
        tk_label.setStyleSheet("color: #e4e4e7;" if self.current_theme in ["Dark", "Dracula"] else "color: #18181b;")
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Light", "Dark", "Dracula"])
        current_theme = self.config_manager.get("theme", "Dark")
        self.theme_combo.setCurrentText(current_theme)
        
        if self.current_theme in ["Dark", "Dracula"]:
            combo_style = """
                QComboBox {
                    background-color: #27272a;
                    color: #e4e4e7;
                    border: 1px solid #3f3f46;
                    border-radius: 6px;
                    padding: 6px;
                }
                QComboBox::drop-down {
                    border: none;
                }
            """
        else:
             combo_style = """
                QComboBox {
                    background-color: #ffffff;
                    color: #18181b;
                    border: 1px solid #e4e4e7;
                    border-radius: 6px;
                    padding: 6px;
                }
                QComboBox::drop-down {
                    border: none;
                }
            """
        self.theme_combo.setStyleSheet(combo_style)

        row1.addWidget(tk_label)
        row1.addWidget(self.theme_combo)
        self.content_layout.addLayout(row1)
        
        # Row 2: Editor BG
        row2 = QHBoxLayout()
        editor_label = QLabel("Fondo del Editor:")
        editor_label.setStyleSheet("color: #e4e4e7;" if self.current_theme in ["Dark", "Dracula"] else "color: #18181b;")
        
        self.editor_bg_btn = QPushButton("Elegir Color")
        self.editor_bg_btn.setCursor(Qt.PointingHandCursor)
        self.current_editor_bg = self.config_manager.get("theme_custom_editor_bg", "")
        self.update_btn_style(self.editor_bg_btn, self.current_editor_bg)
        self.editor_bg_btn.clicked.connect(self.pick_editor_bg)
        
        row2.addWidget(editor_label)
        row2.addWidget(self.editor_bg_btn)
        self.content_layout.addLayout(row2)
        
        # Row 3: Sidebar BG
        row3 = QHBoxLayout()
        sidebar_label = QLabel("Fondo de la Barra Lateral:")
        sidebar_label.setStyleSheet("color: #e4e4e7;" if self.current_theme in ["Dark", "Dracula"] else "color: #18181b;")
        
        self.sidebar_bg_btn = QPushButton("Elegir Color")
        self.sidebar_bg_btn.setCursor(Qt.PointingHandCursor)
        self.current_sidebar_bg = self.config_manager.get("theme_custom_sidebar_bg", "")
        self.update_btn_style(self.sidebar_bg_btn, self.current_sidebar_bg)
        self.sidebar_bg_btn.clicked.connect(self.pick_sidebar_bg)
        
        row3.addWidget(sidebar_label)
        row3.addWidget(self.sidebar_bg_btn)
        self.content_layout.addLayout(row3)
        
        # Row 4: Reset Button
        reset_btn = QPushButton("Restaurar Valores por Defecto")
        reset_btn.setCursor(Qt.PointingHandCursor)
        
        if self.current_theme in ["Dark", "Dracula"]:
            reset_style = """
                QPushButton {
                    background-color: #27272a;
                    color: #e4e4e7;
                    border: 1px solid #3f3f46;
                    border-radius: 6px;
                    padding: 8px;
                    margin-top: 10px;
                }
                QPushButton:hover { background-color: #3f3f46; }
            """
        else:
            reset_style = """
                QPushButton {
                    background-color: #ffffff;
                    color: #18181b;
                    border: 1px solid #e4e4e7;
                    border-radius: 6px;
                    padding: 8px;
                    margin-top: 10px;
                }
                QPushButton:hover { background-color: #f4f4f5; }
            """
        reset_btn.setStyleSheet(reset_style)
        
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
                    border-radius: 6px;
                    padding: 6px;
                }}
            """)
            btn.setText(color_str)
        else:
            if self.current_theme in ["Dark", "Dracula"]:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #27272a;
                        color: #e4e4e7;
                        border: 1px solid #3f3f46;
                        border-radius: 6px;
                        padding: 6px;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #ffffff;
                        color: #18181b;
                        border: 1px solid #e4e4e7;
                        border-radius: 6px;
                        padding: 6px;
                    }
                """)
            btn.setText("Por Defecto")

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
        self.theme_combo.setCurrentText("Dark")

    def save_settings(self):
        # Update Local Config
        self.config_manager.save_config(items={
            "theme": self.theme_combo.currentText(),
            "theme_custom_editor_bg": self.current_editor_bg,
            "theme_custom_sidebar_bg": self.current_sidebar_bg
        })
        
        # Update Global Settings (for startup)
        settings = QSettings()
        settings.setValue("theme", self.theme_combo.currentText())
        
        self.accept()
