from PySide6.QtWidgets import QMainWindow, QLabel, QVBoxLayout, QWidget, QProgressBar
from PySide6.QtCore import Qt, QThread, Signal, QTimer
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
            
            # Step 2: Theme Manager Cache (40%)
            from app.ui.themes import ThemeManager
            # Force cache load
            _ = ThemeManager.get_palette("Dark")
            _ = ThemeManager.get_palette("Light")
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
        self.resize(400, 300)
        
        # UI Setup
        central_widget = QWidget()
        central_widget.setStyleSheet("""
            QWidget {
                background-color: #2D2D2D;
                border-radius: 12px;
                border: 1px solid #444;
            }
            QLabel {
                color: #FFFFFF;
            }
            QProgressBar {
                border: none;
                background-color: #444;
                border-radius: 2px;
                height: 4px;
            }
            QProgressBar::chunk {
                background-color: #3498db;
                border-radius: 2px;
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
            self.logo_label.setPixmap(pixmap.scaled(128, 128, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.logo_label.setText("COGNY")
            self.logo_label.setFont(QFont("Arial", 24, QFont.Bold))
        
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
        
        # We don't start worker immediately here, caller handles it? 
        # Or we start it automatically? Let's start it automatically for simplicity.
        self.worker.start()
