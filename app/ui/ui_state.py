from PySide6.QtCore import QSettings

class UiStateMixin:
    def closeEvent(self, event):
        settings = QSettings()
        if self.editor_area.current_note_id is not None:
             settings.setValue("last_note_id", self.editor_area.current_note_id)
        else:
             settings.remove("last_note_id")
             
        super().closeEvent(event)

    def restore_state(self):
        settings = QSettings()
        last_id = settings.value("last_note_id", type=int)
        
        # We need to tell Sidebar to select this note
        # But Sidebar's model load is async? No, it's inside init currently.
        if last_id:
             self.sidebar.select_note(last_id)
