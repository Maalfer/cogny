from PySide6.QtWidgets import (QDialog, QVBoxLayout, QPushButton, QLabel, 
                                 QHBoxLayout, QFileDialog, QWidget, QFrame, QLineEdit)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QFont, QPixmap
import os

class CreateVaultDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Crear Nueva Bóveda")
        self.setFixedSize(500, 250)
        self.vault_path = None
        
        # Styles
        self.setStyleSheet("""
            QDialog { background-color: #2b2b2b; color: #ffffff; }
            QLineEdit { padding: 8px; border-radius: 4px; border: 1px solid #555; background: #3d3d3d; color: white; }
            QLabel { color: #ddd; }
            QPushButton { padding: 8px 16px; border-radius: 4px; background: #007acc; color: white; border: none; }
            QPushButton:hover { background: #0098ff; }
            QPushButton#Browse { background: #444; }
            QPushButton#Cancel { background: #444; }
        """)
        
        layout = QVBoxLayout(self)
        
        # Vault Name
        layout.addWidget(QLabel("Nombre de la Bóveda:"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Ej: Mis Notas")
        layout.addWidget(self.name_input)
        
        # Location
        layout.addWidget(QLabel("Guardar en (Carpeta Padre):"))
        loc_layout = QHBoxLayout()
        self.location_input = QLineEdit()
        self.location_input.setText(os.path.expanduser("~/Documentos"))
        self.btn_browse = QPushButton("Explorar...")
        self.btn_browse.setObjectName("Browse")
        self.btn_browse.clicked.connect(self.browse_location)
        loc_layout.addWidget(self.location_input)
        loc_layout.addWidget(self.btn_browse)
        layout.addLayout(loc_layout)
        
        layout.addStretch()
        
        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_create = QPushButton("Crear Bóveda")
        self.btn_create.clicked.connect(self.create_vault)
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setObjectName("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_create)
        layout.addLayout(btn_layout)

    def browse_location(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta Padre", self.location_input.text())
        if dir_path:
            self.location_input.setText(dir_path)

    def create_vault(self):
        name = self.name_input.text().strip()
        location = self.location_input.text().strip()
        
        if not name:
            # Simple validation visual cue could be added here
            return
            
        full_path = os.path.join(location, name)
        
        if os.path.exists(full_path):
            # If folder exists, we could warn, but for now we proceed 
            # (treating it as opening if user insists, or creating inside if empty)
            # Better: Make sure we don't overwrite blindly, but user said "create new".
            # For this context, we accept using existing folder if it matches intent,
            # but ideally we want a NEW folder.
            pass
        else:
            try:
                os.makedirs(full_path)
            except Exception as e:
                print(f"Error creating directory: {e}")
                return

        self.vault_path = full_path
        self.accept()

class SetupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bienvenido a Cogny")
        self.setFixedSize(600, 400)
        self.selected_vault_path = None
        
        # Load Styles directly here for simplicity or use theme manager
        # Using a dark-ish theme by default for the setup dialog for "premium" look
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QPushButton {
                background-color: #3d3d3d;
                border: 1px solid #555;
                border-radius: 8px;
                color: white;
                padding: 15px;
                font-size: 16px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #4d4d4d;
                border-color: #777;
            }
            QPushButton:pressed {
                background-color: #222;
            }
            QLabel {
                color: #ddd;
            }
            QLabel#Title {
                font-size: 24px;
                font-weight: bold;
                color: #fff;
            }
            QLabel#Subtitle {
                font-size: 14px;
                color: #aaa;
                margin-bottom: 20px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(40, 40, 40, 40)

        # Header
        header_layout = QHBoxLayout()
        
        # Icon
        icon_label = QLabel()
        logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../assets/logo.png")
        if os.path.exists(logo_path):
             pixmap = QPixmap(logo_path).scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
             icon_label.setPixmap(pixmap)
        
        text_layout = QVBoxLayout()
        title = QLabel("Bienvenido a Cogny")
        title.setObjectName("Title")
        subtitle = QLabel("Tu base de conocimiento inteligente.")
        subtitle.setObjectName("Subtitle")
        text_layout.addWidget(title)
        text_layout.addWidget(subtitle)
        
        header_layout.addWidget(icon_label)
        header_layout.addLayout(text_layout)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        layout.addSpacing(20)

        # Actions
        btn_new = QPushButton("✨  Crear Nueva Bóveda")
        btn_new.setCursor(Qt.PointingHandCursor)
        btn_new.clicked.connect(self.create_new_vault)
        
        btn_open = QPushButton("📂  Abrir Bóveda Existente")
        btn_open.setCursor(Qt.PointingHandCursor)
        btn_open.clicked.connect(self.open_existing_vault)
        
        btn_draft = QPushButton("📝  Empezar sin Guardar (Borrador)")
        btn_draft.setCursor(Qt.PointingHandCursor)
        btn_draft.clicked.connect(self.start_draft_mode)

        layout.addWidget(btn_new)
        layout.addWidget(btn_open)
        layout.addWidget(btn_draft)
        
        layout.addStretch()
        
        version_label = QLabel("v1.0.0")
        version_label.setAlignment(Qt.AlignRight)
        version_label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(version_label)

    def create_new_vault(self):
        # Re-use the dialog but rename attributes if needed
        dialog = CreateVaultDialog(self)
        if dialog.exec():
            self.selected_vault_path = dialog.vault_path
            self.accept()

    def open_existing_vault(self):
        dir_path = QFileDialog.getExistingDirectory(
            self, 
            "Abrir Bóveda (Seleccionar Carpeta)", 
            os.path.expanduser("~/Documentos"),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        if dir_path:
            self.selected_vault_path = dir_path
            self.accept()

    def start_draft_mode(self):
        # Magic string to signal temporary 
        self.selected_vault_path = "__TEMP__" 
        self.accept()
