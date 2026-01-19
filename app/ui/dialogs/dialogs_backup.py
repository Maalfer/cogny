from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QComboBox, QLineEdit, QHBoxLayout, QFrame
from PySide6.QtCore import Qt, QSettings
from app.ui.widgets import ModernDialog, ModernInput

class BackupDialog(ModernDialog):
    def __init__(self, parent=None):
        super().__init__("Crear Copia de Seguridad", None, parent)
        
        # 1. Format Selection
        row1 = QHBoxLayout()
        fmt_label = QLabel("Formato:")
        fmt_label.setStyleSheet("color: #e4e4e7;" if self.current_theme in ["Dark", "Dracula", "AnuPpuccin"] else "color: #18181b;")
        
        self.format_combo = QComboBox()
        self.format_combo.addItems([".zip (Recomendado)", ".tar.gz"])
        self.format_combo.currentIndexChanged.connect(self.on_format_changed)
        
        # Style Combo
        if self.current_theme in ["Dark", "Dracula", "AnuPpuccin"]:
            combo_style = """
                QComboBox {
                    background-color: #27272a;
                    color: #e4e4e7;
                    border: 1px solid #3f3f46;
                    border-radius: 6px;
                    padding: 6px;
                }
                QComboBox::drop-down { border: none; }
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
                QComboBox::drop-down { border: none; }
            """
        self.format_combo.setStyleSheet(combo_style)
        
        row1.addWidget(fmt_label)
        row1.addWidget(self.format_combo)
        self.content_layout.addLayout(row1)
        
        # 2. Password (Optional)
        self.pass_frame = QFrame()
        pass_layout = QVBoxLayout(self.pass_frame)
        pass_layout.setContentsMargins(0, 10, 0, 0)
        
        pass_label = QLabel("Contraseña (Opcional):")
        pass_label.setStyleSheet("color: #e4e4e7;" if self.current_theme in ["Dark", "Dracula", "AnuPpuccin"] else "color: #18181b;")
        
        self.pass_input = QLineEdit()
        self.pass_input.setPlaceholderText("Dejar vacío para sin protección")
        self.pass_input.setEchoMode(QLineEdit.Password)
        
        # Style Input
        if self.current_theme in ["Dark", "Dracula", "AnuPpuccin"]:
            input_style = """
                QLineEdit {
                    background-color: #27272a;
                    color: #e4e4e7;
                    border: 1px solid #3f3f46;
                    border-radius: 6px;
                    padding: 8px;
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
                }
            """
        self.pass_input.setStyleSheet(input_style)
        
        pass_layout.addWidget(pass_label)
        pass_layout.addWidget(self.pass_input)
        
        self.content_layout.addWidget(self.pass_frame)
        
        # Actions
        self.AddButton("Cancelar", "normal", self.reject)
        self.AddButton("Crear Respaldo", "primary", self.accept)

    def on_format_changed(self, index):
        # Disable password for tar
        is_tar = "tar" in self.format_combo.currentText()
        self.pass_input.setEnabled(not is_tar)
        if is_tar:
            self.pass_input.setPlaceholderText("No soportado para .tar")
            self.pass_input.clear()
        else:
             self.pass_input.setPlaceholderText("Dejar vacío para sin protección")

    # Override helper to fix casing from ModernDialog adaptation if needed
    def AddButton(self, text, role, callback):
        self.add_button(text, role, callback)
    
    def get_data(self):
        fmt = "zip" if "zip" in self.format_combo.currentText() else "tar"
        pwd = self.pass_input.text()
        return fmt, pwd
