from .light import LightTheme
from PySide6.QtGui import QPalette, QColor

class DraculaTheme(LightTheme):
    @property
    def name(self) -> str:
        return "Dracula"

    def apply_palette(self, palette: QPalette, global_bg: str = None, text_color: str = None):
        base_bg = QColor(global_bg) if global_bg else QColor("#282a36") 
        base_text = QColor(text_color) if text_color else QColor("#f8f8f2")
        palette.setColor(QPalette.Window, base_bg)
        palette.setColor(QPalette.WindowText, base_text)
        palette.setColor(QPalette.Base, QColor("#44475a")) # Surface
        palette.setColor(QPalette.AlternateBase, QColor("#6272a4"))
        palette.setColor(QPalette.ToolTipBase, QColor("#282a36"))
        palette.setColor(QPalette.ToolTipText, base_text)
        palette.setColor(QPalette.Text, base_text)
        palette.setColor(QPalette.Button, QColor("#44475a"))
        palette.setColor(QPalette.ButtonText, base_text)
        palette.setColor(QPalette.BrightText, QColor("#ff5555")) 
        palette.setColor(QPalette.Link, QColor("#8be9fd"))      # Cyan
        palette.setColor(QPalette.Highlight, QColor("#bd93f9")) # Purple
        palette.setColor(QPalette.HighlightedText, QColor("#282a36"))

    def get_editor_style(self, editor_bg: str = None, text_color: str = None, global_bg: str = None) -> str:
        default_bg = "#21222c" 
        bg_color = editor_bg if editor_bg else default_bg
        text_color = text_color if text_color else "#f8f8f2"
        accent_color = "#8be9fd" # Cyan
        code_bg = "#44475a" # Dracula Surface
        border_color = "#6272a4" # Dracula Comment
        sel_bg = "#bd93f9"
        sel_text = "#282a36"
        
        return self._generate_editor_css(bg_color, text_color, sel_bg, sel_text, accent_color, code_bg, border_color)

    def get_title_style(self, global_bg: str = None, text_color: str = None) -> str:
        bg_color = "#21222c"
        text_color = text_color if text_color else "#f8f8f2"
        return self._generate_title_css(bg_color, text_color)

    def get_code_bg_color(self) -> QColor:
        return QColor("#44475a")

    def get_syntax_colors(self) -> dict:
        return {
            "keyword": "#ff79c6",       # Pink
            "keyword_pseudo": "#bd93f9",# Purple
            "string": "#f1fa8c",        # Yellow
            "comment": "#6272a4",       # Comment
            "function": "#50fa7b",      # Green
            "class": "#8be9fd",         # Cyan
            "number": "#bd93f9",        # Purple
            "operator": "#ff79c6",      # Pink
            "decorator": "#bd93f9",     # Purple
            "default": "#f8f8f2",       # Foreground
            "inline_code": "#f1fa8c",    # Yellow
            "highlight_bg": "#f1fa8c",  # Yellow (Dracula)
            "highlight_text": "#282a36" # Background color for text
        }

    def get_sidebar_style(self, sidebar_bg: str = None, text_color: str = None) -> str:
        tree_bg = sidebar_bg if sidebar_bg else "transparent"
        text_color = text_color if text_color else "#f8f8f2"
        hover_bg = "rgba(255, 255, 255, 0.05)"
        selected_bg = "rgba(0, 0, 0, 0.2)" 
        accent_border = "#bd93f9" # Purple
        return self._generate_sidebar_css(tree_bg, text_color, hover_bg, selected_bg, accent_border)

    def get_toolbar_style(self, global_bg: str = None) -> str:
        bg = global_bg if global_bg else "#282a36"
        border = "#6272a4"
        return self._generate_toolbar_css(bg, border)

    def get_scrollbar_style(self) -> str:
        handle = "#6272a4"
        handle_hover = "#bd93f9"
        return self._generate_scrollbar_css(handle, handle_hover)

    def get_search_bar_style(self, global_bg: str = None, text_color: str = None) -> str:
        bg_color = "rgba(0, 0, 0, 0.2)" 
        text_color = text_color if text_color else "#f8f8f2"
        border_color = "rgba(255, 255, 255, 0.1)"
        focus_border = "#bd93f9" # Purple
        return self._generate_search_bar_css(bg_color, text_color, border_color, focus_border)

    def get_title_bar_style(self, global_bg: str = None, text_color: str = None) -> str:
        bg_color = global_bg if global_bg else "#282a36"
        text_color = text_color if text_color else "#f8f8f2"
        border_color = "#6272a4"
        btn_hover = "rgba(255, 255, 255, 0.1)"
        btn_pressed = "rgba(255, 255, 255, 0.15)"
        return self._generate_title_bar_css(bg_color, text_color, border_color, btn_hover, btn_pressed)
