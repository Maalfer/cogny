from .light import LightTheme
from PySide6.QtGui import QPalette, QColor

class AnuPpuccinTheme(LightTheme):
    @property
    def name(self) -> str:
        return "AnuPpuccin"

    def apply_palette(self, palette: QPalette, global_bg: str = None, text_color: str = None):
        base_bg = QColor(global_bg) if global_bg else QColor("#11111b") 
        base_text = QColor(text_color) if text_color else QColor("#cdd6f4")
        palette.setColor(QPalette.Window, base_bg)
        palette.setColor(QPalette.WindowText, base_text)
        palette.setColor(QPalette.Base, QColor("#1e1e2e")) 
        palette.setColor(QPalette.AlternateBase, QColor("#313244")) # Surface0
        palette.setColor(QPalette.ToolTipBase, QColor("#181825"))   # Mantle
        palette.setColor(QPalette.ToolTipText, base_text)
        palette.setColor(QPalette.Text, base_text)
        palette.setColor(QPalette.Button, QColor("#1e1e2e"))
        palette.setColor(QPalette.ButtonText, base_text)
        palette.setColor(QPalette.BrightText, QColor("#f38ba8")) # Red
        palette.setColor(QPalette.Link, QColor("#89b4fa"))      # Blue
        palette.setColor(QPalette.Highlight, QColor("#cba6f7")) # Mauve
        palette.setColor(QPalette.HighlightedText, QColor("#1e1e2e"))

    def get_editor_style(self, editor_bg: str = None, text_color: str = None, global_bg: str = None) -> str:
        default_bg = "#11111b" 
        bg_color = editor_bg if editor_bg else default_bg
        text_color = text_color if text_color else "#cdd6f4"
        accent_color = "#cba6f7" # Mauve
        code_bg = "#181825" # Mantle
        border_color = "#313244" # Surface0
        sel_bg = "#45475a" # Surface1
        sel_text = "#cdd6f4"
        
        return self._generate_editor_css(bg_color, text_color, sel_bg, sel_text, accent_color, code_bg, border_color)

    def get_title_style(self, global_bg: str = None, text_color: str = None) -> str:
        bg_color = "#11111b"
        text_color = text_color if text_color else "#cdd6f4"
        return self._generate_title_css(bg_color, text_color)

    def get_code_bg_color(self) -> QColor:
        return QColor("#181825") # Mantle

    def get_syntax_colors(self) -> dict:
        return {
            "keyword": "#cba6f7",       # Mauve
            "keyword_pseudo": "#f5c2e7",# Pink
            "string": "#a6e3a1",        # Green
            "comment": "#6c7086",       # Overlay0
            "function": "#89b4fa",      # Blue
            "class": "#f9e2af",         # Yellow
            "number": "#fab387",        # Peach
            "decorator": "#f5e0dc",     # Rosewater
            "default": "#cdd6f4",       # Text
            "inline_code": "#f38ba8",    # Red
            "highlight_bg": "#fab387",  # Peach
            "highlight_text": "#1e1e2e"
        }

    def get_sidebar_style(self, sidebar_bg: str = None, text_color: str = None) -> str:
        tree_bg = sidebar_bg if sidebar_bg else "transparent"
        text_color = text_color if text_color else "#cdd6f4"
        hover_bg = "rgba(255, 255, 255, 0.05)"
        selected_bg = "rgba(0, 0, 0, 0.2)"
        accent_border = "#cba6f7" # Mauve
        return self._generate_sidebar_css(tree_bg, text_color, hover_bg, selected_bg, accent_border)

    def get_toolbar_style(self, global_bg: str = None) -> str:
        bg = global_bg if global_bg else "#1e1e2e"
        border = "#313244"
        return self._generate_toolbar_css(bg, border)

    def get_scrollbar_style(self) -> str:
        handle = "#585b70" # Surface2
        handle_hover = "#89b4fa" # Blue
        return self._generate_scrollbar_css(handle, handle_hover)

    def get_search_bar_style(self, global_bg: str = None, text_color: str = None) -> str:
        bg_color = "rgba(0, 0, 0, 0.2)"
        text_color = text_color if text_color else "#cdd6f4"
        border_color = "rgba(255, 255, 255, 0.1)"
        focus_border = "#cba6f7"
        return self._generate_search_bar_css(bg_color, text_color, border_color, focus_border)

    def get_title_bar_style(self, global_bg: str = None, text_color: str = None) -> str:
        bg_color = global_bg if global_bg else "#1e1e2e"
        text_color = text_color if text_color else "#cdd6f4"
        border_color = "#313244"
        btn_hover = "rgba(255, 255, 255, 0.1)"
        btn_pressed = "rgba(255, 255, 255, 0.15)"
        return self._generate_title_bar_css(bg_color, text_color, border_color, btn_hover, btn_pressed)

    def get_splitter_style(self) -> str:
        return f"""
        QSplitter::handle {{
            background-color: transparent;
            height: 0px; 
            width: 0px;  
        }}
        """
