from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QIcon, QPainter, QColor
from PySide6.QtSvgWidgets import QSvgWidget
import os


class CustomTitleBar(QWidget):
    """Custom title bar with minimize, maximize, and close buttons."""
    
    minimize_clicked = Signal()
    maximize_clicked = Signal()
    close_clicked = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self._dragging = False
        self._drag_position = QPoint()
        
        self.setFixedHeight(40)
        self.setObjectName("CustomTitleBar")
        
        # Main Layout
        layout = QHBoxLayout()
        # Increased left margin to 24 to fix persistent icon clipping on rounded corners
        layout.setContentsMargins(24, 0, 0, 0) 
        layout.setSpacing(0)
        self.setLayout(layout)
        
        # Logo
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        logo_path = os.path.join(base_dir, "assets", "logo.png")
        
        self.logo_label = QLabel()
        if os.path.exists(logo_path):
            from PySide6.QtGui import QPixmap
            pixmap = QPixmap(logo_path).scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.logo_label.setPixmap(pixmap)
        self.logo_label.setFixedSize(24, 24)
        self.logo_label.setStyleSheet("margin-right: 8px;")
        self.logo_label.setAttribute(Qt.WA_TransparentForMouseEvents)  # Allow clicks to pass through
        layout.addWidget(self.logo_label)
        
        # Spacer Left
        layout.addStretch()
        
        # Title
        self.title_label = QLabel("Cogny")
        self.title_label.setObjectName("TitleLabel")
        self.title_label.setStyleSheet("font-weight: 600; font-size: 13px;")
        self.title_label.setAlignment(Qt.AlignCenter) # Center text in label
        self.title_label.setAttribute(Qt.WA_TransparentForMouseEvents)  # Allow clicks to pass through
        layout.addWidget(self.title_label)
        
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
        self.title_label.setText(title)
    
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
