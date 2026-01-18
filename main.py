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
    app.setDesktopFileName("cogny") 
    
    # Set Global Icon
    from PySide6.QtGui import QIcon
    base_dir = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(base_dir, "assets", "logo.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    app.setStyle(QStyleFactory.create("Fusion"))
    
    # Splash Screen Integration
    from app.ui.splash import SplashWindow
    
    # Prevent app from closing when splash closes before main window opens
    app.setQuitOnLastWindowClosed(False)
    
    splash = SplashWindow()
    splash.show()
    
    def launch_main_app():
        # This function runs after warm-up
        
        # Load Theme (now fast due to warm-up)
        # from PySide6.QtCore import QSettings # redundant import, but safe
        # settings = QSettings()
        # theme_name = settings.value("theme", "Dark")
        # app.setPalette(ThemeManager.get_palette(theme_name))
        # Note: ThemeManager usage in Splash does not set app palette, 
        # but it caches the palette generation. We must set it here.
        from PySide6.QtCore import QSettings
        settings = QSettings()
        theme_name = settings.value("theme", "Dark")
        app.setPalette(ThemeManager.get_palette(theme_name))

        # Vault Selection Logic
        vault_path = settings.value("last_vault_path", "")
        show_setup = False
        
        if not vault_path or not os.path.exists(vault_path) or not os.path.isdir(vault_path):
            show_setup = True
            
        is_draft = False
        if show_setup:
            from app.ui.dialogs_setup import SetupDialog
            setup_dialog = SetupDialog()
            if setup_dialog.exec():
                vault_path = setup_dialog.selected_vault_path
                if vault_path == "__TEMP__":
                    import tempfile
                    import uuid
                    temp_name = f"cogny_draft_{uuid.uuid4().hex[:8]}"
                    vault_path = os.path.join(tempfile.gettempdir(), temp_name)
                    os.makedirs(vault_path, exist_ok=True)
                    is_draft = True
                else:
                    settings.setValue("last_vault_path", vault_path)
                    is_draft = False
            else:
                sys.exit(0)
        
        # Launch Main Window
        global window # Keep reference
        window = MainWindow(vault_path, is_draft=is_draft)
        window.show()
        
        # Re-enable quit on close
        app.setQuitOnLastWindowClosed(True)
        
    # Connect Splash Signal
    splash.worker.finished_warmup.connect(launch_main_app)
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
