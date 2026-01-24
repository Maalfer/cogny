from app.ui.temas import ThemeManager as NewThemeManager

class ThemeManager:
    """Legacy wrapper for backward compatibility or direct delegation."""
    
    @staticmethod
    def get_palette(theme: str, global_bg: str = None, text_color: str = None):
        return NewThemeManager.get_palette(theme, global_bg, text_color)

    @staticmethod
    def get_editor_style(theme: str, editor_bg: str = None, text_color: str = None, global_bg: str = None) -> str:
        return NewThemeManager.get_editor_style(theme, editor_bg, text_color, global_bg)

    @staticmethod
    def get_title_style(theme: str, global_bg: str = None, text_color: str = None) -> str:
        return NewThemeManager.get_title_style(theme, global_bg, text_color)

    @staticmethod
    def get_code_bg_color(theme: str):
        return NewThemeManager.get_code_bg_color(theme)

    @staticmethod
    def get_syntax_colors(theme: str) -> dict:
        return NewThemeManager.get_syntax_colors(theme)

    @staticmethod
    def get_sidebar_style(theme: str, sidebar_bg: str = None, text_color: str = None) -> str:
        return NewThemeManager.get_sidebar_style(theme, sidebar_bg, text_color)

    @staticmethod
    def get_splitter_style(theme: str) -> str:
        return NewThemeManager.get_splitter_style(theme)

    @staticmethod
    def get_toolbar_style(theme: str, global_bg: str = None) -> str:
        return NewThemeManager.get_toolbar_style(theme, global_bg)

    @staticmethod
    def get_scrollbar_style(theme: str) -> str:
        return NewThemeManager.get_scrollbar_style(theme)

    @staticmethod
    def get_search_bar_style(theme: str, global_bg: str = None, text_color: str = None) -> str:
        return NewThemeManager.get_search_bar_style(theme, global_bg, text_color)

    @staticmethod
    def get_title_bar_style(theme: str, global_bg: str = None, text_color: str = None) -> str:
        return NewThemeManager.get_title_bar_style(theme, global_bg, text_color)

    @staticmethod
    def get_tab_style(theme: str, global_bg: str = None) -> str:
        return NewThemeManager.get_tab_style(theme, global_bg)
