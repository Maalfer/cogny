from PySide6.QtGui import QStandardItem

class NoteItem(QStandardItem):
    def __init__(self, note_id: int, title: str, is_folder: bool = False):
        super().__init__(title)
        self.note_id = note_id
        self.is_folder = is_folder
        self.setEditable(False)
