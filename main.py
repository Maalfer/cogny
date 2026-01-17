import sys
from PySide6.QtWidgets import QApplication, QStyleFactory
from app.ui.main_window import MainWindow
from app.ui.themes import ThemeManager

def main():
    # Suppress benign Qt/Wayland warning
    import os
    os.environ["QT_LOGGING_RULES"] = "qt.qpa.services=false"
    
    app = QApplication(sys.argv)
    
    # Apply Fusion Style
    app.setOrganizationName("CognyApp")
    app.setApplicationName("Cogny")
    
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
    
    # Database Selection Logic
    db_path = settings.value("last_db_path", "")
    
    # Verify if file exists (if it was supposed to) or if it's empty
    # If path is invalid or empty, show setup
    show_setup = False
    # If path is invalid or empty, show setup
    show_setup = False
    
    # Check if db_path is valid (File or Directory)
    if not db_path or not os.path.exists(db_path):
        show_setup = True
    
    # If it is a directory (Vault), check if internal DB exists inside
    if not show_setup and os.path.isdir(db_path):
        internal_db = os.path.join(db_path, ".cogny.cdb")
        # We don't force setup here if internal db is missing, 
        # because MainWindow might create it? 
        # Actually better to rely on MainWindow handling the init if the path is a dir.
        pass
        
    if show_setup:
        from app.ui.dialogs_setup import SetupDialog
        setup_dialog = SetupDialog()
        if setup_dialog.exec():
            db_path = setup_dialog.selected_db_path
            
            # Handle Draft Mode
            if db_path == "__TEMP__":
                import tempfile
                import uuid
                # Create a unique temp name so we don't conflict
                temp_name = f"cogny_draft_{uuid.uuid4().hex[:8]}.cdb"
                db_path = os.path.join(tempfile.gettempdir(), temp_name)
                # Do NOT save to settings.value("last_db_path")
                # So next time app opens, it asks again.
                is_draft = True
            else:
                settings.setValue("last_db_path", db_path)
                is_draft = False
        else:
            # User closed dialog
            sys.exit(0)
    else:
        is_draft = False
    
    window = MainWindow(db_path, is_draft=is_draft)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
