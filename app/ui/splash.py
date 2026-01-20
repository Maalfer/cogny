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
        central_widget = QWidget()
        central_widget.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #252525, stop:1 #2f2f3a);
                border-radius: 14px;
                border: 1px solid rgba(255,255,255,0.04);
            }
            QLabel {
                color: #FFFFFF;
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
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
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
        
        # Visual effects: shadow and subtle animations
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, 180))
        central_widget.setGraphicsEffect(shadow)

        # Logo fade-in
        logo_opacity = QGraphicsOpacityEffect(self.logo_label)
        self.logo_label.setGraphicsEffect(logo_opacity)
        self.logo_anim = QPropertyAnimation(logo_opacity, b"opacity")
        self.logo_anim.setDuration(700)
        self.logo_anim.setStartValue(0.0)
        self.logo_anim.setEndValue(1.0)
        self.logo_anim.setEasingCurve(QEasingCurve.OutCubic)

        # Fade-in for central widget (avoid setting window opacity which
        # some platform plugins do not support)
        central_opacity = QGraphicsOpacityEffect(central_widget)
        central_widget.setGraphicsEffect(central_opacity)
        central_opacity.setOpacity(0.0)

        self.central_fade_anim = QPropertyAnimation(central_opacity, b"opacity")
        self.central_fade_anim.setDuration(600)
        self.central_fade_anim.setStartValue(0.0)
        self.central_fade_anim.setEndValue(1.0)
        self.central_fade_anim.setEasingCurve(QEasingCurve.OutCubic)

        # Do not start the worker here to avoid races with external connections.
        # Caller should call `start_warmup()` after connecting signals.

    def start_warmup(self):
        """Start the warmup worker. Call after connecting any external slots to signals."""
        if not getattr(self, 'worker', None):
            self.worker = WarmupWorker()
            self.worker.progress.connect(self.progress.setValue)
            self.worker.status.connect(self.status_label.setText)
        self.worker.start()

    def showEvent(self, event):
        super().showEvent(event)
        # Play animations when splash is shown
        # Start central widget fade and logo fade. Avoid animating window opacity.
        try:
            self.central_fade_anim.start()
            self.logo_anim.start()
        except Exception:
            pass
