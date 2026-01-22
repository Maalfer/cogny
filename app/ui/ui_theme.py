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
        global_bg = settings.value("theme_custom_global_bg", "")
        text_color = settings.value("theme_custom_text_color", "")
        
        # App Palette
        QApplication.instance().setPalette(ThemeManager.get_palette(theme_name, global_bg, text_color))
        
        # Update components
        self.editor_area.switch_theme(theme_name, text_color, global_bg)
        
        # Update Title Edit Style explicitly
        if hasattr(self.editor_area, "title_edit"):
             title_style = ThemeManager.get_title_style(theme_name, global_bg, text_color)
             self.editor_area.title_edit.setStyleSheet(title_style)
        
        # Apply Global Scrollbar & Splitter Style
        scrollbar_style = ThemeManager.get_scrollbar_style(theme_name)
        toolbar_style = ThemeManager.get_toolbar_style(theme_name, global_bg)
        splitter_style = ThemeManager.get_splitter_style(theme_name)
        QApplication.instance().setStyleSheet(scrollbar_style + toolbar_style + splitter_style)
        
        # Apply Sidebar Styles explicitly
        sidebar_style = ThemeManager.get_sidebar_style(theme_name, sidebar_bg, text_color)
        self.sidebar.tree_view.setStyleSheet(sidebar_style)
        
        # Update Search Bar Style
        if hasattr(self, 'search_manager'):
            self.search_manager.update_theme(theme_name, global_bg, text_color)
        
        # Update Title Bar Style
        if hasattr(self, 'title_bar'):
            title_bar_style = ThemeManager.get_title_bar_style(theme_name, global_bg, text_color)
            self.title_bar.setStyleSheet(title_bar_style)
        
        self.statusBar().showMessage(f"Tema cambiado a {theme_name}", 2000)
