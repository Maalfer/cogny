import sys
from PySide6.QtWidgets import QApplication, QStyleFactory
from app.ui.main_window import MainWindow
from app.ui.themes import ThemeManager

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Apply Fusion Style
    app.setOrganizationName("CognyApp")
    app.setApplicationName("Cogni")
    
    # Apply Fusion Style
    app.setStyle(QStyleFactory.create("Fusion"))
    
    # Load Theme from Settings (Default: Dark)
    from PySide6.QtCore import QSettings
    settings = QSettings()
    theme_name = settings.value("theme", "Dark")
    
    # Apply Theme
    app.setPalette(ThemeManager.get_palette(theme_name))
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
