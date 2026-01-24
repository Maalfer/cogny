from .light import LightTheme
from PySide6.QtGui import QPalette, QColor

class DarkTheme(LightTheme):
    @property
    def name(self) -> str:
        return "Dark"

    def apply_palette(self, palette: QPalette, global_bg: str = None, text_color: str = None):
        base_bg = QColor(global_bg) if global_bg else QColor("#18181b") 
        base_text = QColor(text_color) if text_color else QColor("#e4e4e7")
        palette.setColor(QPalette.Window, base_bg)
        palette.setColor(QPalette.WindowText, base_text)
        palette.setColor(QPalette.Base, QColor("#27272a")) # Zinc-800
        palette.setColor(QPalette.AlternateBase, QColor("#3f3f46"))
        palette.setColor(QPalette.ToolTipBase, QColor("#18181b"))
        palette.setColor(QPalette.ToolTipText, base_text)
        palette.setColor(QPalette.Text, base_text)
        palette.setColor(QPalette.Button, QColor("#27272a"))
        palette.setColor(QPalette.ButtonText, base_text)
        palette.setColor(QPalette.BrightText, QColor("#ef4444")) # Red-500
        palette.setColor(QPalette.Link, QColor("#60a5fa"))      # Blue-400
        palette.setColor(QPalette.Highlight, QColor("#3b82f6")) # Blue-500
        palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))

    def get_editor_style(self, editor_bg: str = None, text_color: str = None, global_bg: str = None) -> str:
        default_bg = "#09090b"
        bg_color = editor_bg if editor_bg else default_bg
        text_color = text_color if text_color else "#e4e4e7"
        accent_color = "#60a5fa" # Blue-400
        code_bg = "#27272a" # Zinc-800
        border_color = "#3f3f46" # Zinc-700
        sel_bg = "#3b82f6"
        sel_text = "#ffffff"
        
        return self._generate_editor_css(bg_color, text_color, sel_bg, sel_text, accent_color, code_bg, border_color)

    def get_title_style(self, global_bg: str = None, text_color: str = None) -> str:
        bg_color = "#09090b"
        text_color = text_color if text_color else "#e4e4e7"
        return self._generate_title_css(bg_color, text_color)

    def get_code_bg_color(self) -> QColor:
        return QColor("#52525b") # Zinc-600

    def get_syntax_colors(self) -> dict:
        return {
            "keyword": "#f472b6",       # Pink-400
            "keyword_pseudo": "#c084fc",# Purple-500
            "string": "#facc15",        # Yellow-400
            "comment": "#71717a",       # Zinc-500
            "function": "#4ade80",      # Green-400
            "class": "#60a5fa",         # Blue-400
            "number": "#e879f9",        # Fuchsia-400
            "decorator": "#9333ea",     # Purple-600
            "default": "#e4e4e7",       # Zinc-200
            "inline_code": "#fb923c",   # Orange-400
            "highlight_bg": "#facc15",  # Yellow-400
            "highlight_text": "#000000"
        }

    def get_sidebar_style(self, sidebar_bg: str = None, text_color: str = None) -> str:
        tree_bg = sidebar_bg if sidebar_bg else "transparent"
        text_color = text_color if text_color else "#e4e4e7"
        hover_bg = "rgba(255, 255, 255, 0.05)"
        selected_bg = "rgba(0, 0, 0, 0.2)"
        accent_border = "#3b82f6"
        return self._generate_sidebar_css(tree_bg, text_color, hover_bg, selected_bg, accent_border)

    def get_splitter_style(self) -> str:
        return self._generate_splitter_css() # Base uses transparent, works for dark too

    def get_toolbar_style(self, global_bg: str = None) -> str:
        bg = global_bg if global_bg else "#18181b"
        border = "#3f3f46"
        return self._generate_toolbar_css(bg, border)

    def get_scrollbar_style(self) -> str:
        handle = "#3f3f46" # Zinc-700
        handle_hover = "#71717a" # Zinc-500
        return self._generate_scrollbar_css(handle, handle_hover)

    def get_search_bar_style(self, global_bg: str = None, text_color: str = None) -> str:
        bg_color = "rgba(0, 0, 0, 0.2)"
        text_color = text_color if text_color else "#e4e4e7"
        border_color = "rgba(255, 255, 255, 0.1)"
        focus_border = "#3b82f6"
        return self._generate_search_bar_css(bg_color, text_color, border_color, focus_border)

    def get_title_bar_style(self, global_bg: str = None, text_color: str = None) -> str:
        bg_color = global_bg if global_bg else "#18181b"
        text_color = text_color if text_color else "#e4e4e7"
        border_color = "#3f3f46"
        btn_hover = "rgba(255, 255, 255, 0.1)"
        btn_pressed = "rgba(255, 255, 255, 0.15)"
        return self._generate_title_bar_css(bg_color, text_color, border_color, btn_hover, btn_pressed)
