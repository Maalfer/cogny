from .base_theme import BaseTheme
from .light import LightTheme
from .dark import DarkTheme
from .dracula import DraculaTheme
from .anuppuccin import AnuPpuccinTheme

class ThemeManager:
    _themes = {
        "Light": LightTheme(),
        "Dark": DarkTheme(),
        "Dracula": DraculaTheme(),
        "AnuPpuccin": AnuPpuccinTheme()
    }

    @staticmethod
    def get_theme(theme_name: str) -> BaseTheme:
        return ThemeManager._themes.get(theme_name, ThemeManager._themes["Light"])

    @staticmethod
    def get_palette(theme: str, global_bg: str = None, text_color: str = None):
        from PySide6.QtGui import QPalette
        palette = QPalette()
        ThemeManager.get_theme(theme).apply_palette(palette, global_bg, text_color)
        return palette

    @staticmethod
    def get_editor_style(theme: str, editor_bg: str = None, text_color: str = None, global_bg: str = None) -> str:
        return ThemeManager.get_theme(theme).get_editor_style(editor_bg, text_color, global_bg)

    @staticmethod
    def get_title_style(theme: str, global_bg: str = None, text_color: str = None) -> str:
        return ThemeManager.get_theme(theme).get_title_style(global_bg, text_color)

    @staticmethod
    def get_code_bg_color(theme: str):
        return ThemeManager.get_theme(theme).get_code_bg_color()

    @staticmethod
    def get_syntax_colors(theme: str) -> dict:
        return ThemeManager.get_theme(theme).get_syntax_colors()

    @staticmethod
    def get_sidebar_style(theme: str, sidebar_bg: str = None, text_color: str = None) -> str:
        return ThemeManager.get_theme(theme).get_sidebar_style(sidebar_bg, text_color)

    @staticmethod
    def get_splitter_style(theme: str) -> str:
        return ThemeManager.get_theme(theme).get_splitter_style()

    @staticmethod
    def get_toolbar_style(theme: str, global_bg: str = None) -> str:
        return ThemeManager.get_theme(theme).get_toolbar_style(global_bg)

    @staticmethod
    def get_scrollbar_style(theme: str) -> str:
        return ThemeManager.get_theme(theme).get_scrollbar_style()

    @staticmethod
    def get_search_bar_style(theme: str, global_bg: str = None, text_color: str = None) -> str:
        return ThemeManager.get_theme(theme).get_search_bar_style(global_bg, text_color)

    @staticmethod
    def get_title_bar_style(theme: str, global_bg: str = None, text_color: str = None) -> str:
        return ThemeManager.get_theme(theme).get_title_bar_style(global_bg, text_color)

    @staticmethod
    def get_tab_style(theme: str, global_bg: str = None) -> str:
        return ThemeManager.get_theme(theme).get_tab_style(global_bg)
