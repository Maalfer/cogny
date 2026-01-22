from PySide6.QtWidgets import QMainWindow, QLabel, QVBoxLayout, QWidget, QProgressBar, QGraphicsDropShadowEffect, QGraphicsOpacityEffect
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPixmap, QFont, QColor
import os
import sys

# Warmup Worker to pre-load heavy modules
class WarmupWorker(QThread):
    progress = Signal(int)
    status = Signal(str)
    finished_warmup = Signal()

    def run(self):
        try:
            # Step 1: Heavy Imports (20%)
            self.status.emit("Cargando librerías gráficas...")
            self.progress.emit(10)
            
            # Simulate work if imports are instant, but usually they take IO time
            import markdown
            import pygments
            from PIL import Image
            import weasyprint
            
            self.progress.emit(30)
            self.status.emit("Iniciando motor de renderizado...")
            
            # Step 2: Light non-GUI warmups (40%)
            # Avoid creating GUI-related objects (QPalette/QColor) from a worker thread.
            # We'll let the main thread initialize theme/palette when ready.
            self.progress.emit(50)
            
            # Step 3: Regex Compilation (70%)
            self.status.emit("Optimizando editor...")
            import re
            
            # Compile Markdown Patterns
            # (Matches those in Highlighter and Editor)
            re.compile(r"^#{1,6}\s.*") # Headers
            re.compile(r"(\*\*|__)(.*?)\1") # Bold
            re.compile(r"(\*|_)(.*?)\1") # Italic
            re.compile(r"!\[.*?\]\((.*?)\)") # Images
            re.compile(r"!\[\[(.*?)\]\]") # WikiLinks
            
            self.progress.emit(80)
            
            # Step 4: Finalize
            self.status.emit("Listo.")
            self.progress.emit(100)
            
            # Small delay to let user see "100%"
            QThread.msleep(200)
            
        except Exception as e:
            print(f"Warmup Error: {e}")
        finally:
            self.finished_warmup.emit()

class SplashWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Compact & Minimalist Size
        self.resize(380, 260)
        
        # Central Container with Shadow
        # We use a container widget inside the main window to hold the layout and apply effects
        self.container = QWidget()
        self.container.setObjectName("SplashContainer")
        self.setCentralWidget(self.container)
        
        # Shadow Effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setXOffset(0)
        shadow.setYOffset(10)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.container.setGraphicsEffect(shadow)

        # Layout
        main_layout = QVBoxLayout(self.container)
        main_layout.setContentsMargins(30, 40, 30, 40)
        main_layout.setSpacing(15)
        main_layout.setAlignment(Qt.AlignCenter)

        # Stylesheet (Modern Dark Minimalist)
        self.setStyleSheet("""
            QWidget#SplashContainer {
                background-color: #1e1e2e; /* Catppuccin Base / Modern Dark */
                border-radius: 16px;
                border: 1px solid #313244; /* Subtle Border */
            }
            QLabel {
                color: #cdd6f4; /* Text Base */
                background: transparent;
            }
            QProgressBar {
                border: none;
                background-color: #313244; /* Darker track */
                border-radius: 2px;
                height: 4px; /* Ultra thin minimalist bar */
            }
            QProgressBar::chunk {
                background-color: #cba6f7; /* Accent Color (Mauve/Purple) */
                border-radius: 2px;
            }
        """)

        # Logo
        self.logo_label = QLabel()
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        logo_path = os.path.join(base_dir, "assets", "logo.png")
        
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            # Smaller, crisper logo
            self.logo_label.setPixmap(pixmap.scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            # Fallback Text Logo
            self.logo_label.setText("C")
            self.logo_label.setFont(QFont("Segoe UI", 48, QFont.Bold))
            self.logo_label.setStyleSheet("color: #cba6f7;")
            
        self.logo_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.logo_label)

        # App Title (Minimalist)
        title = QLabel("Cogny")
        title.setFont(QFont("Segoe UI", 20, QFont.Bold)) # Clean San-Serif
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("margin-top: 5px;")
        main_layout.addWidget(title)

        # Spacer (Push content slightly)
        main_layout.addStretch()

        # Status Label (Subtle)
        self.status_label = QLabel("Iniciando...")
        self.status_label.setFont(QFont("Segoe UI", 9))
        self.status_label.setStyleSheet("color: #a6adc8;") # Muted text
        self.status_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.status_label)
        
        # Progress Bar (Thin)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedWidth(240) # Compact width
        main_layout.addWidget(self.progress, 0, Qt.AlignCenter)
        
        # Start Worker
        self.worker = WarmupWorker()
        self.worker.progress.connect(self.progress.setValue)
        self.worker.status.connect(self.status_label.setText)

    def start_warmup(self):
        """Start the warmup worker."""
        if not getattr(self, 'worker', None):
            self.worker = WarmupWorker()
            self.worker.progress.connect(self.progress.setValue)
            self.worker.status.connect(self.status_label.setText)
        self.worker.start()

    def showEvent(self, event):
        super().showEvent(event)

    def set_status(self, text):
         self.status_label.setText(text)

    def show_loading_note(self, note_name):
         self.status_label.setText(f"Cargando nota: {note_name}...")


