from PySide6.QtWidgets import (QDialog, QVBoxLayout, QListWidget, QListWidgetItem, 
                                 QPushButton, QHBoxLayout, QLabel)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon

class ReadLaterDialog(QDialog):
    note_selected = Signal(int) # Emits note_id when user wants to open it

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.setWindowTitle("Notas Guardadas (Ver más tarde)")
        self.resize(400, 500)
        self.setup_ui()
        self.load_notes()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Header
        lbl = QLabel("Tus notas pendientes:")
        lbl.setStyleSheet("font-weight: bold; font-size: 14px; margin-bottom: 5px;")
        layout.addWidget(lbl)

        # List
        self.list_widget = QListWidget()
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        layout.addWidget(self.list_widget)

        # Buttons
        btn_layout = QHBoxLayout()
        
        btn_open = QPushButton("Abrir")
        btn_open.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6; 
                color: white; 
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover { background-color: #2563eb; }
        """)
        btn_open.clicked.connect(self.on_open_clicked)
        btn_layout.addWidget(btn_open)

        btn_remove = QPushButton("Quitar de la lista")
        btn_remove.setStyleSheet("""
            QPushButton {
                background-color: #ef4444; 
                color: white; 
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover { background-color: #dc2626; }
        """)
        btn_remove.clicked.connect(self.on_remove_clicked)
        btn_layout.addWidget(btn_remove)
        
        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(self.close)
        btn_layout.addWidget(btn_close)

        layout.addLayout(btn_layout)

    def load_notes(self):
        self.list_widget.clear()
        notes = self.db.get_read_later_notes()
        
        if not notes:
            item = QListWidgetItem("No tienes notas guardadas.")
            item.setFlags(Qt.NoItemFlags)
            self.list_widget.addItem(item)
            return

        for nid, title, updated in notes:
            item = QListWidgetItem(f"{title}")
            item.setData(Qt.UserRole, nid)
            item.setToolTip(f"Actualizado: {updated}")
            self.list_widget.addItem(item)

    def on_item_double_clicked(self, item):
        self.on_open_clicked()

    def on_open_clicked(self):
        items = self.list_widget.selectedItems()
        if not items: return
        
        item = items[0]
        note_id = item.data(Qt.UserRole)
        
        if note_id:
            self.note_selected.emit(note_id)
            self.close()

    def on_remove_clicked(self):
        items = self.list_widget.selectedItems()
        if not items: return
        
        item = items[0]
        note_id = item.data(Qt.UserRole)
        
        if note_id:
            # Toggle off
            self.db.toggle_read_later(note_id)
            # Remove from list
            row = self.list_widget.row(item)
            self.list_widget.takeItem(row)
