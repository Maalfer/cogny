from PySide6.QtWidgets import QPlainTextEdit
from PySide6.QtCore import Qt, Signal

class TitleEditor(QPlainTextEdit):
    return_pressed = Signal()
    editing_finished = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setTabChangesFocus(True)
        
        # Connect signals for auto-resize
        self.textChanged.connect(self.update_height)
        self.blockCountChanged.connect(self.update_height)
        self.update_height()

    def update_height(self):
        """Auto-adjust height based on content"""
        # Ensure minimal height based on font
        fm = self.fontMetrics()
        min_doc_height = fm.height()
        
        doc_height = self.document().size().height()
        # Fallback if doc_height is 0 (uninitialized layout)
        if doc_height < min_doc_height:
            doc_height = min_doc_height
            
        margins = self.contentsMargins()
        # Add buffer for top/bottom padding defined in stylesheet (usually 20px+10px)
        
        # Simple heuristic: height + 30 buffer -> Reduced to 10 to match padding (10+0=10px) (Tightest possible)
        total_height = int(doc_height + margins.top() + margins.bottom())
        self.setFixedHeight(total_height + 10)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if not (event.modifiers() & Qt.ShiftModifier):
               self.return_pressed.emit()
               # self.editing_finished.emit(self.toPlainText()) # Triggered by focusOut via return_pressed
               return
        super().keyPressEvent(event)

    def focusOutEvent(self, event):
        self.editing_finished.emit(self.toPlainText())
        super().focusOutEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_margins()
        self.update_height()

    def showEvent(self, event):
        super().showEvent(event)
        self.update_margins()
        self.update_height()

    def update_margins(self):
        # Dynamic Centered Layout (Synced with NoteEditor)
        max_content_width = 800 

        current_width = self.width()
        
        if current_width > max_content_width:
             margin = (current_width - max_content_width) // 2
        else:
             margin = 30
             
        self.setViewportMargins(margin, 0, margin, 0)
