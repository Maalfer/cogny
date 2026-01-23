from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QMenuBar, QToolButton, QMenu
from PySide6.QtCore import Qt, Signal, QPoint, QSize
from PySide6.QtGui import QIcon, QPainter, QColor
from PySide6.QtSvgWidgets import QSvgWidget
import os


class CustomTitleBar(QWidget):
    """Custom title bar with minimize, maximize, and close buttons."""
    
    minimize_clicked = Signal()
    maximize_clicked = Signal()
    close_clicked = Signal()
    sidebar_toggle_clicked = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self._dragging = False
        self._drag_position = QPoint()
        
        self.setFixedHeight(40)
        self.setObjectName("CustomTitleBar")
        
        # Main Layout
        layout = QHBoxLayout()
        layout.setContentsMargins(8, 0, 0, 0)  # Reduced left margin since no logo
        layout.setSpacing(4)
        self.setLayout(layout)
        
        # Search Widget (will be set later)
        self.search_btn = None
        self.search_widget = None
        self.toggle_btn = None
        
        # Menu Bar (will be set later)
        # Menu Bar (will be set later)
        self.menu_bar = None
        self.hamburger_btn = None
        self.sidebar_btn = None
        
        
        # Spacer
        layout.addStretch()
        
        # Spacer Right
        layout.addStretch()
        
        # Window Control Buttons
        self.minimize_btn = self._create_window_button("minimize")
        self.maximize_btn = self._create_window_button("maximize")
        self.close_btn = self._create_window_button("close")
        
        self.minimize_btn.clicked.connect(self.minimize_clicked.emit)
        self.maximize_btn.clicked.connect(self._on_maximize_clicked)
        self.close_btn.clicked.connect(self.close_clicked.emit)
        
        layout.addWidget(self.minimize_btn)
        layout.addWidget(self.maximize_btn)
        layout.addWidget(self.close_btn)
    
    def add_search_widget(self, search_widget):
        """Add collapsible search widget to title bar."""
        if self.search_widget:
            self.layout().removeWidget(self.search_widget)
            self.search_widget.setParent(None)
            if self.search_btn:
                self.layout().removeWidget(self.search_btn)
                self.search_btn.setParent(None)
        
        self.search_widget = search_widget
        if search_widget:
            # Create Toggle Button
            self.search_btn = QPushButton()
            
            # Load SVG Icon
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            icon_path = os.path.join(base_dir, "assets", "icons", "search.svg")
            
            self.search_btn.setIcon(QIcon(icon_path))
            self.search_btn.setIconSize(QSize(20, 20)) # Adjust size as needed
            
            self.search_btn.setFixedSize(32, 30)
            self.search_btn.setFlat(True)
            self.search_btn.setCursor(Qt.PointingHandCursor)
            self.search_btn.setToolTip("Buscar (Ctrl+K)")
            self.search_btn.setStyleSheet("""
                QPushButton {
                    border: none;
                    background: transparent;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background: rgba(0, 0, 0, 0.1);
                }
            """)
            
            
            # Insert after sidebar toggle (Index 0=Hamburger, 1=Sidebar)
            # So Search is 2, Widget is 3
            current_idx = 2
            if self.sidebar_btn:
                 current_idx = self.layout().indexOf(self.sidebar_btn) + 1
                 
            self.layout().insertWidget(current_idx, self.search_btn)
            self.layout().insertWidget(current_idx + 1, self.search_widget)
            
            # Configure Search Widget
            search_widget.setVisible(False)
            search_widget.setFixedWidth(250)
            search_widget.setStyleSheet("""
                QLineEdit {
                    border: 1px solid rgba(128, 128, 128, 0.3);
                    border-radius: 4px;
                    padding: 4px 8px;
                    background: rgba(255, 255, 255, 0.1);
                    color: inherit;
                }
                QLineEdit:focus {
                    border: 1px solid #3b82f6;
                    background: rgba(255, 255, 255, 0.2);
                }
            """)
            
            # Connect Signals
            self.search_btn.clicked.connect(self._toggle_search)
            
    def _toggle_search(self):
        """Toggle search widget visibility."""
        if not self.search_widget: return
        
        is_visible = self.search_widget.isVisible()
        self.search_widget.setVisible(not is_visible)
        
        if not is_visible:
            self.search_widget.setFocus()

    def add_toggle_button(self, action):
        """Add a toggle button (QAction proxy) to the title bar."""
        """Add a toggle button (QAction proxy) to the title bar."""
        if self.toggle_btn:
            self.layout().removeWidget(self.toggle_btn)
            self.toggle_btn.setParent(None)
        
        self.toggle_btn = QToolButton()
        self.toggle_btn.setDefaultAction(action)
        self.toggle_btn.setAutoRaise(True)
        self.toggle_btn.setFixedSize(32, 30)
        self.toggle_btn.setCursor(Qt.PointingHandCursor)
        # Style matches search button
        self.toggle_btn.setStyleSheet("""
            QToolButton {
                border: none;
                background: transparent;
                border-radius: 4px;
            }
            QToolButton:hover {
                background: rgba(0, 0, 0, 0.1);
            }
        """)

        # Calculate index: We want to insert BEFORE the spacer.
        # But simply iterating indices is safer.
        # Order: Hamburger(0), Sidebar(1), SearchBtn(2), SearchWidget(3), Toggle(4) ... Spacer ... WindowControls
        
        current_idx = 0
        if self.search_widget:
             current_idx = self.layout().indexOf(self.search_widget) + 1
        elif self.search_btn:
             current_idx = self.layout().indexOf(self.search_btn) + 1
        elif self.sidebar_btn:
             current_idx = self.layout().indexOf(self.sidebar_btn) + 1
        elif self.hamburger_btn:
             current_idx = self.layout().indexOf(self.hamburger_btn) + 1
             
        self.layout().insertWidget(current_idx, self.toggle_btn)

            
    def set_menu_bar(self, menu_bar):
        """Set the menu bar to display in the title bar."""
        if self.menu_bar:
            # Remove old menu bar if exists
            self.layout().removeWidget(self.menu_bar)
            self.menu_bar.setParent(None)
        
        self.menu_bar = menu_bar
        if menu_bar:
            # Create Hamburger Button if it doesn't exist
            if not self.hamburger_btn:
                self.hamburger_btn = QPushButton()
                
                # Load SVG Icon
                base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
                icon_path = os.path.join(base_dir, "assets", "icons", "menu.svg")
                
                self.hamburger_btn.setIcon(QIcon(icon_path))
                self.hamburger_btn.setIconSize(QSize(20, 20))
                self.hamburger_btn.setFixedSize(40, 40)
                self.hamburger_btn.setFlat(True)
                self.hamburger_btn.setCursor(Qt.PointingHandCursor)
                self.hamburger_btn.setStyleSheet("""
                    QPushButton {
                        border: none;
                        background: transparent;
                        border-radius: 4px;
                    }
                    QPushButton:hover {
                        background: rgba(0, 0, 0, 0.1);
                    }
                """)
                self.hamburger_btn.clicked.connect(self._show_hamburger_menu)
                
                # Insert at the very beginning of the MAIN layout (Left side)
                self.layout().insertWidget(0, self.hamburger_btn)
                
            # Create Sidebar Toggle Button if it doesn't exist
            if not self.sidebar_btn:
                self.sidebar_btn = QPushButton()
                
                base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
                icon_path = os.path.join(base_dir, "assets", "icons", "sidebar.svg")
                
                self.sidebar_btn.setIcon(QIcon(icon_path))
                self.sidebar_btn.setIconSize(QSize(20, 20))
                self.sidebar_btn.setFixedSize(40, 40)
                self.sidebar_btn.setFlat(True)
                self.sidebar_btn.setCursor(Qt.PointingHandCursor)
                self.sidebar_btn.setStyleSheet("""
                    QPushButton {
                        border: none;
                        background: transparent;
                        border-radius: 4px;
                    }
                    QPushButton:hover {
                        background: rgba(0, 0, 0, 0.1);
                    }
                """)
                self.sidebar_btn.clicked.connect(self.sidebar_toggle_clicked.emit)
                self.sidebar_btn.setToolTip("Mostrar/Ocultar Barra Lateral")
                
                # Insert at index 1 (after hamburger)
                self.layout().insertWidget(1, self.sidebar_btn)
    
    def _show_hamburger_menu(self):
        """Show the menu bar actions as a popup menu."""
        if not self.menu_bar: return
        
        # Create a popup menu
        popup_menu = QMenu(self)
        
        # Add actions from the actual menu bar
        # Note: top-level menus in QMenuBar are "addMenu" which returns a QMenu. 
        # But QMenuBar keeps them as actions.
        for action in self.menu_bar.actions():
            popup_menu.addAction(action)
            
        # Show menu at button position
        pos = self.hamburger_btn.mapToGlobal(QPoint(0, self.hamburger_btn.height()))
        popup_menu.exec(pos)
    
    def _create_window_button(self, button_type):
        """Create a window control button with SVG icon."""
        btn = QPushButton()
        btn.setFixedSize(46, 40)
        btn.setObjectName(f"{button_type}Button")
        btn.setFlat(True)
        btn.setCursor(Qt.PointingHandCursor)
        
        # Set icon based on type using SVG paths
        if button_type == "minimize":
            btn.setText("−")  # Unicode minus
            btn.setStyleSheet("""
                QPushButton {
                    border: none;
                    background: transparent;
                    font-size: 16px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: #e5e5e5;
                }
                QPushButton:pressed {
                    background: #cccccc;
                }
            """)
        elif button_type == "maximize":
            btn.setText("□")  # Unicode square
            btn.setStyleSheet("""
                QPushButton {
                    border: none;
                    background: transparent;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background: #e5e5e5;
                }
                QPushButton:pressed {
                    background: #cccccc;
                }
            """)
        elif button_type == "close":
            btn.setText("✕")  # Unicode X
            btn.setStyleSheet("""
                QPushButton {
                    border: none;
                    background: transparent;
                    font-size: 16px;
                }
                QPushButton:hover {
                    background: #c42b1c;
                    color: white;
                }
                QPushButton:pressed {
                    background: #a52313;
                    color: white;
                }
            """)
        
        return btn
    
    def set_title(self, title):
        """Update window title."""
        # Title label removed, this is now a no-op or could update window title directly if needed
        if self.parent_window:
             self.parent_window.setWindowTitle(title)
    
    def update_maximize_icon(self, is_maximized):
        """Update maximize button icon based on window state."""
        if is_maximized:
            self.maximize_btn.setText("❐")  # Restore icon
            self.maximize_btn.setToolTip("Restaurar")
        else:
            self.maximize_btn.setText("□")  # Maximize icon
            self.maximize_btn.setToolTip("Maximizar")
    
    def _on_maximize_clicked(self):
        """Handle maximize/restore toggle."""
        self.maximize_clicked.emit()
        if self.parent_window:
            is_maximized = self.parent_window.isMaximized()
            self.update_maximize_icon(is_maximized)
    
    def mousePressEvent(self, event):
        """Handle mouse press for window dragging."""
        if event.button() == Qt.LeftButton:
            if self.parent_window:
                # 1. Standard Drag: Only if strictly Normal state (not Maximized)
                # Attempt native drag immediately for best performance/fluidity
                if not self.parent_window.isMaximized():
                    window_handle = self.parent_window.windowHandle()
                    if window_handle and window_handle.startSystemMove():
                        event.accept()
                        return

                # 2. Prepare for Potential Maximize->Restore Drag
                # We save the local Y position to ensure the window "sticks" vertically 
                # to the mouse at the exact same point when it snaps to normal size.
                self._click_pos_local = event.position().toPoint()
                
                # Also track standard manual drag position as fallback
                self._drag_position = event.globalPosition().toPoint() - self.parent_window.frameGeometry().topLeft()
                self._dragging = True
                event.accept()
    
    def mouseMoveEvent(self, event):
        """Handle mouse move for window dragging."""
        if self._dragging and self.parent_window:
            # Smart Snap-Restore Logic
            if self.parent_window.isMaximized():
                 # 1. Calculate relative Horizontal ratio (cursor X / screen width)
                 # This keeps the window horizontally centered under the cursor proportionally
                 screen_width = self.parent_window.width()
                 rel_x_ratio = event.position().x() / screen_width
                 
                 # 2. Restore window to Normal size
                 self.parent_window.toggle_maximize_restore()
                 
                 # 3. Calculate new Window Position to maintain fluidity
                 # New Top-Left X = Global Mouse X - (Window Width * Ratio)
                 new_width = self.parent_window.width()
                 target_x_offset = int(new_width * rel_x_ratio)
                 
                 # New Top-Left Y = Global Mouse Y - Original Local Y Click
                 target_y_offset = self._click_pos_local.y()
                 
                 new_pos = event.globalPosition().toPoint()
                 new_pos.setX(new_pos.x() - target_x_offset)
                 new_pos.setY(new_pos.y() - target_y_offset)
                 
                 # 4. Move window instantly
                 self.parent_window.move(new_pos)
                 
                 # 5. Native Handoff (The "Elegant" part)
                 # Immediately hand control to the OS window manager for silky smooth native dragging
                 window_handle = self.parent_window.windowHandle()
                 if window_handle and window_handle.startSystemMove():
                     self._dragging = False 
                     return
                 
                 # Fallback: Update manual drag offset if native move failed
                 self._drag_position = QPoint(target_x_offset, target_y_offset)

            # Manual Fallback Drag (if Native failed)
            self.parent_window.move(event.globalPosition().toPoint() - self._drag_position)
            event.accept()
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release to stop dragging."""
        self._dragging = False
        event.accept()
    
    def mouseDoubleClickEvent(self, event):
        """Handle double-click to maximize/restore."""
        if event.button() == Qt.LeftButton:
            self.maximize_clicked.emit()
            if self.parent_window:
                is_maximized = self.parent_window.isMaximized()
                self.update_maximize_icon(is_maximized)
