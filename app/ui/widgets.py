from PySide6.QtWidgets import QPlainTextEdit
from PySide6.QtCore import Qt, Signal, QSize

class TitleEditor(QPlainTextEdit):
    return_pressed = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setTabChangesFocus(True)
        
        # Connect text change to resize
        self.textChanged.connect(self.update_height)
        self.update_height() # Initial set

    def update_height(self):
        # Calculate new height based on document contents
        doc_height = self.document().size().height()
        
        # Add some padding for the margins/borders defined in CSS
        # In CSS we have 20px top + 10px bottom padding.
        # document size usually excludes frame width if not careful, 
        # but QPlainTextEdit contentsRect is informative.
        # Let's try enforcing a min-height and setting fixed height.
        
        # We need to account for the widget's padding which is part of the "height" but not "document height".
        # From CSS: padding-top: 20px, padding-bottom: 10px. Total 30px.
        # Plus title font is huge (24pt).
        
        # A safer way: margins
        margins = self.contentsMargins()
        # Since we use stylesheet padding, getting exact margins via Python API might return 0 if not polished,
        # but let's assume ~35px offset (30px padding + 5px extra).
        
        # QPlainTextEdit's document().size() often returns layout size.
        # line count * line height.
        
        new_height = int(doc_height + 35) 
        
        # Enforce minimum for 1 line
        if new_height < 60: 
             new_height = 60
             
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
