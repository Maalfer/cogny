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
        layout.setContentsMargins(10, 0, 0, 0)
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
        
        # Title
        self.title_label = QLabel("Cogny")
        self.title_label.setObjectName("TitleLabel")
        self.title_label.setStyleSheet("font-weight: 600; font-size: 13px;")
        self.title_label.setAttribute(Qt.WA_TransparentForMouseEvents)  # Allow clicks to pass through
        layout.addWidget(self.title_label)
        
        # Spacer
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
                # Try system move first (Native Wayland/X11 support)
                window_handle = self.parent_window.windowHandle()
                if window_handle and window_handle.startSystemMove():
                    event.accept()
                    return

                # Fallback to manual move
                self._dragging = True
                self._drag_position = event.globalPosition().toPoint() - self.parent_window.frameGeometry().topLeft()
                event.accept()
    
    def mouseMoveEvent(self, event):
        """Handle mouse move for window dragging."""
        if self._dragging and self.parent_window and not self.parent_window.isMaximized():
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
