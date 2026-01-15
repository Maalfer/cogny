from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSettings
from app.ui.themes import ThemeManager
from app.ui.widgets import ThemeSettingsDialog

class UiThemeMixin:
    def show_theme_dialog(self):
        if ThemeSettingsDialog.show_dialog(self):
            settings = QSettings()
            new_theme = settings.value("theme", "Dark")
            self.switch_theme(new_theme)

    def switch_theme(self, theme_name):
        settings = QSettings()
        sidebar_bg = settings.value("theme_custom_sidebar_bg", "")
        
        # App Palette
        QApplication.instance().setPalette(ThemeManager.get_palette(theme_name, sidebar_bg))
        
        # Update components
        self.editor_area.switch_theme(theme_name)
        
        # Apply Sidebar Styles explicitly
        sidebar_style = ThemeManager.get_sidebar_style(theme_name)
        self.sidebar.tree_view.setStyleSheet(sidebar_style)
        
        self.statusBar().showMessage(f"Tema cambiado a {theme_name}", 2000)
