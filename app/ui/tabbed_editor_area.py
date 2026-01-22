from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QTabBar, QPushButton
from PySide6.QtCore import Signal, Qt, QSize
from PySide6.QtGui import QIcon, QFont
from app.ui.editor_area import EditorArea
import os

class TabbedEditorArea(QWidget):
    """Manages multiple note editors in tabs, similar to a web browser."""
    status_message = Signal(str, int)
    note_renamed = Signal(str, str)
    
    def __init__(self, file_manager, parent=None):
        super().__init__(parent)
        self.fm = file_manager
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Tab Widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(False)  # We'll use custom close buttons
        self.tab_widget.setMovable(True)
        self.tab_widget.setDocumentMode(True)
        
        # Signals
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        
        layout.addWidget(self.tab_widget)
        
        # Customize tab bar close buttons
        self.setup_tab_close_buttons()
        
        # Create first tab (empty placeholder)
        self.create_new_tab("Sin nota", None)
    
    def setup_tab_close_buttons(self):
        """Setup custom close button styling."""
        # We'll update close buttons when tabs are added
        pass
    
    def create_new_tab(self, title, note_id):
        """Creates a new tab with an EditorArea instance."""
        # Create new editor area
        editor_area = EditorArea(self.fm, self)
        
        # Store note_id as attribute on the widget
        editor_area._tab_note_id = note_id
        
        # Connect signals
        editor_area.status_message.connect(self.status_message)
        editor_area.note_renamed.connect(self.note_renamed)
        
        # Add to tabs
        index = self.tab_widget.addTab(editor_area, title)
        
        # Custom Tooltip (Breadcrumb)
        tooltip = self._get_tooltip_text(note_id)
        self.tab_widget.setTabToolTip(index, tooltip)
        
        # Customize close button for this tab
        self._customize_tab_close_button(index)
        
        return editor_area
    
    def _customize_tab_close_button(self, index):
        """Add a custom styled close button to a tab."""
        # Create custom close button
        close_btn = QPushButton("×")
        close_btn.setFixedSize(QSize(18, 18))
        close_btn.setFont(QFont("Arial", 12, QFont.Bold))
        close_btn.setFlat(True)
        close_btn.setStyleSheet("""
            QPushButton {
                border: none;
                border-radius: 9px;
                background: transparent;
                color: #888;
                padding: 0px;
            }
            QPushButton:hover {
                background: rgba(239, 68, 68, 0.2);
                color: #ef4444;
            }
            QPushButton:pressed {
                background: rgba(239, 68, 68, 0.3);
            }
        """)
        
        # Connect to close tab
        close_btn.clicked.connect(lambda: self.tab_widget.tabCloseRequested.emit(index))
        
        # Set as tab button
        self.tab_widget.tabBar().setTabButton(index, QTabBar.RightSide, close_btn)
    
    def open_note_in_new_tab(self, note_id, is_folder=False, title=None):
        """Opens a note in a new tab."""
        print(f"DEBUG TabbedEditor: open_note_in_new_tab called - note_id={note_id}, title={title}")
        # Determine display title
        if not title and note_id:
            title = os.path.basename(note_id)
            if title.endswith('.md'):
                title = title[:-3]
        
        
        # Allow opening the same note in multiple tabs
        # Optionally, we could switch to existing tab instead:
        # for i in range(self.tab_widget.count()):
        #     editor = self.tab_widget.widget(i)
        #     if editor and getattr(editor, '_tab_note_id', None) == note_id:
        #         self.tab_widget.setCurrentIndex(i)
        #         return
        
        
        # Create new tab
        print(f"DEBUG TabbedEditor: Creating new tab for '{title}'")
        editor_area = self.create_new_tab(title or "Nueva nota", note_id)
        
        # Load the note
        if note_id:
            editor_area.load_note(note_id, is_folder, title)
        
        # Switch to the new tab
        self.tab_widget.setCurrentIndex(self.tab_widget.count() - 1)
    
    def open_note_in_current_tab(self, note_id, is_folder=False, title=None):
        """Opens a note in the current tab (replaces current content)."""
        current_index = self.tab_widget.currentIndex()
        if current_index == -1:
            # No tabs, create one
            self.open_note_in_new_tab(note_id, is_folder, title)
            return
        
        # Get current editor
        editor_area = self.tab_widget.widget(current_index)
        
        # Determine display title
        if not title and note_id:
            title = os.path.basename(note_id)
            if title.endswith('.md'):
                title = title[:-3]
        
        # Update tab title and note_id
        self.tab_widget.setTabText(current_index, title or "Sin nota")
        editor_area._tab_note_id = note_id
        
        # Update Tooltip
        tooltip = self._get_tooltip_text(note_id)
        self.tab_widget.setTabToolTip(current_index, tooltip)
        
        # Load the note
        if note_id:
            editor_area.load_note(note_id, is_folder, title)
            
    def _get_tooltip_text(self, note_id):
        """Generates a breadcrumb-style tooltip from the note path."""
        if not note_id:
            return "Sin nota"
            
        # Remove extension
        display_path = note_id
        if display_path.endswith(".md"):
             display_path = display_path[:-3]
             
        # Normalize separators
        display_path = display_path.replace("\\", "/")
        
        # Create breadcrumb format
        parts = display_path.split('/')
        return " / ".join(parts)
    
    def close_tab(self, index):
        """Closes a tab at the given index."""
        # Don't allow closing the last tab
        if self.tab_widget.count() <= 1:
            # Instead of closing, just clear it
            editor_area = self.tab_widget.widget(index)
            editor_area.clear()
            self.tab_widget.setTabText(index, "Sin nota")
            editor_area._tab_note_id = None
            return
        
        # Save current note before closing
        editor_area = self.tab_widget.widget(index)
        if editor_area and editor_area.current_note_id:
            editor_area.save_current_note()
        
        # Remove tab
        self.tab_widget.removeTab(index)
    
    def on_tab_changed(self, index):
        """Called when user switches tabs."""
        if index == -1:
            return
        
        # Save previous tab's note
        # (handled automatically by focus events)
        pass
    
    def save_current_note(self):
        """Saves the note in the active tab."""
        current_index = self.tab_widget.currentIndex()
        if current_index >= 0:
            editor_area = self.tab_widget.widget(current_index)
            if editor_area:
                return editor_area.save_current_note()
    
    def get_current_editor(self):
        """Returns the current EditorArea instance."""
        current_index = self.tab_widget.currentIndex()
        if current_index >= 0:
            return self.tab_widget.widget(current_index)
        return None
    
    @property
    def current_note_id(self):
        """Returns the note_id of the active tab."""
        current_index = self.tab_widget.currentIndex()
        if current_index >= 0:
            editor = self.tab_widget.widget(current_index)
            return getattr(editor, '_tab_note_id', None)
        return None
    
    def set_file_manager(self, file_manager):
        """Updates the file manager for all tabs."""
        self.fm = file_manager
        for i in range(self.tab_widget.count()):
            editor_area = self.tab_widget.widget(i)
            if editor_area:
                editor_area.set_file_manager(file_manager)
    
    def switch_theme(self, theme_name, text_color=None, global_bg=None):
        """Applies theme to all tabs."""
        for i in range(self.tab_widget.count()):
            editor_area = self.tab_widget.widget(i)
            if editor_area:
                editor_area.switch_theme(theme_name, text_color, global_bg)
    
    # Backward compatibility properties
    @property
    def text_editor(self):
        """Returns the current tab's text editor for backward compatibility."""
        editor = self.get_current_editor()
        return editor.text_editor if editor else None
    
    @property
    def title_edit(self):
        """Returns the current tab's title editor for backward compatibility."""
        editor = self.get_current_editor()
        return editor.title_edit if editor else None
    
    def load_note(self, note_id, is_folder=False, title=None, **kwargs):
        """Loads note in current tab - for backward compatibility."""
        self.open_note_in_current_tab(note_id, is_folder, title)
    
    @property
    def note_loaded(self):
        """Returns the note_loaded signal from current editor."""
        editor = self.get_current_editor()
        return editor.note_loaded if editor else None
    
    def clear(self):
        """Clears the current tab's content."""
        editor = self.get_current_editor()
        if editor:
            editor.clear()
    
    def attach_file(self):
        """Attaches file in current tab."""
        editor = self.get_current_editor()
        if editor:
            editor.attach_file()

