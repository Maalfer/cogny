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
    
    # Vault Selection Logic
    vault_path = settings.value("last_vault_path", "")
    
    # Verify if directory exists
    show_setup = False
    
    # Check if vault_path is valid
    if not vault_path or not os.path.exists(vault_path) or not os.path.isdir(vault_path):
        show_setup = True
    
    if show_setup:
        from app.ui.dialogs_setup import SetupDialog
        setup_dialog = SetupDialog()
        if setup_dialog.exec():
            vault_path = setup_dialog.selected_vault_path
            
            # Handle Draft Mode
            if vault_path == "__TEMP__":
                import tempfile
                import uuid
                # Create a unique temp name
                temp_name = f"cogny_draft_{uuid.uuid4().hex[:8]}"
                vault_path = os.path.join(tempfile.gettempdir(), temp_name)
                # Ensure it exists
                os.makedirs(vault_path, exist_ok=True)
                
                # Do NOT save to settings.value("last_vault_path")
                # So next time app opens, it asks again.
                is_draft = True
            else:
                settings.setValue("last_vault_path", vault_path)
                is_draft = False
        else:
            # User closed dialog
            sys.exit(0)
    else:
        is_draft = False
    
    window = MainWindow(vault_path, is_draft=is_draft)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
