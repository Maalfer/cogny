from PySide6.QtGui import QStandardItem

class NoteItem(QStandardItem):
    def __init__(self, note_id: int, title: str):
        super().__init__(title)
        self.note_id = note_id
        self.setEditable(False)
