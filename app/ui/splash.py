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
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Center on screen
        self.resize(440, 320)
        
        # UI Setup
        # We need a wrapper widget to handle the Opacity Effect properly
        # while the inner content widget handles the Shadow Effect.
        # Nested effects on the same widget can cause issues, and replacing them definitely does.
        

        # Wrapper is just the central widget now
        self.wrapper_widget = QWidget()
        self.wrapper_widget.setAttribute(Qt.WA_TranslucentBackground)
        self.setCentralWidget(self.wrapper_widget)
        
        wrapper_layout = QVBoxLayout(self.wrapper_widget)
        wrapper_layout.setContentsMargins(10, 10, 10, 10)
        wrapper_layout.setAlignment(Qt.AlignCenter)
        
        # Content Widget
        self.content_widget = QWidget()
        self.content_widget.setObjectName("ContentContainer")
        self.content_widget.setStyleSheet("""
            QWidget#ContentContainer {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #252525, stop:1 #2f2f3a);
                border-radius: 14px;
                border: 2px solid #444; 
            }
            QLabel {
                color: #FFFFFF;
                background: transparent;
            }
            QProgressBar {
                border: none;
                background-color: rgba(255,255,255,0.06);
                border-radius: 4px;
                height: 8px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6dd5fa, stop:1 #2980b9);
                border-radius: 4px;
            }
        """)
        wrapper_layout.addWidget(self.content_widget)
        
        # Layout inside the styled box
        layout = QVBoxLayout(self.content_widget)
        layout.setAlignment(Qt.AlignCenter)
        
        # Logo
        self.logo_label = QLabel()
        logo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets", "logo.png")
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            self.logo_label.setPixmap(pixmap.scaled(140, 140, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.logo_label.setText("COGNY")
            self.logo_label.setFont(QFont("Segoe UI", 26, QFont.Bold))

        self.logo_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.logo_label)
        
        layout.addSpacing(20)
        
        # App Name
        title = QLabel("Cogny")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Status
        self.status_label = QLabel("Iniciando...")
        self.status_label.setFont(QFont("Segoe UI", 10))
        self.status_label.setStyleSheet("color: #AAA;")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)
        
        layout.addSpacing(20)
        
        # Progress Bar
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedWidth(200)
        layout.addWidget(self.progress)
        
        # Start Worker
        self.worker = WarmupWorker()
        self.worker.progress.connect(self.progress.setValue)
        self.worker.status.connect(self.status_label.setText)
        
        # No complex effects to avoid Painter errors
        # self.setWindowOpacity(0.0) # Optional: Animate window opacity instead of widget opacity?
        # Let's keep it simple first.

    def start_warmup(self):
        """Start the warmup worker. Call after connecting any external slots to signals."""
        if not getattr(self, 'worker', None):
            self.worker = WarmupWorker()
            self.worker.progress.connect(self.progress.setValue)
            self.worker.status.connect(self.status_label.setText)
        self.worker.start()

    def showEvent(self, event):
        super().showEvent(event)

