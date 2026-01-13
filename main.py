import sys
from PySide6.QtWidgets import QApplication, QStyleFactory
from app.ui.main_window import MainWindow
from app.ui.themes import ThemeManager

def main():
    app = QApplication(sys.argv)
    
    # Apply Fusion Style
    app.setOrganizationName("CognyApp")
    app.setApplicationName("Cogni")
    
    # Linux Desktop Integration
    # Crucial for wayland/gnome to associate window with .desktop file
    app.setDesktopFileName("cogny") 
    
    # Set Global Icon
    import os
    from PySide6.QtGui import QIcon
    base_dir = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(base_dir, "assets", "logo.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
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

if __name__ == "__main__":
    main()
