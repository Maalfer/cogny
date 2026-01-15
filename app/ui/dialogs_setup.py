from PySide6.QtWidgets import (QDialog, QVBoxLayout, QPushButton, QLabel, 
                                 QHBoxLayout, QFileDialog, QWidget, QFrame)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QFont, QPixmap
import os

class SetupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bienvenido a Cogny")
        self.setFixedSize(600, 400)
        self.selected_db_path = None
        
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
        
        # Icon (Assuming assets/logo.png exists relative to execution or we use standard path)
        # We'll try to load it safely
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
        btn_new = QPushButton("✨  Crear Nueva Base de Datos")
        btn_new.setCursor(Qt.PointingHandCursor)
        btn_new.clicked.connect(self.create_new_db)
        
        btn_open = QPushButton("📂  Abrir Base de Datos Existente")
        btn_open.setCursor(Qt.PointingHandCursor)
        btn_open.clicked.connect(self.open_existing_db)
        
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

    def create_new_db(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Crear Nueva Base de Datos", 
            os.path.expanduser("~/Documentos"), 
            "Cogny Database (*.cdb)"
        )
        if file_path:
            if not file_path.endswith(".cdb"):
                file_path += ".cdb"
            self.selected_db_path = file_path
            self.accept()

    def open_existing_db(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Abrir Base de Datos", 
            os.path.expanduser("~/Documentos"), 
            "Cogny Database (*.cdb)"
        )
        if file_path:
            self.selected_db_path = file_path
            self.accept()

    def start_draft_mode(self):
        # Magic string to signal temporary DB
        self.selected_db_path = "__TEMP__" 
        self.accept()
