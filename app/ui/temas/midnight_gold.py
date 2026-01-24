from .dark import DarkTheme
from PySide6.QtGui import QPalette, QColor

class MidnightGoldTheme(DarkTheme):
    @property
    def name(self) -> str:
        return "Midnight Gold"

    def apply_palette(self, palette: QPalette, global_bg: str = None, text_color: str = None):
        # Deep Black Backgrounds
        base_bg = QColor("#000000") 
        # Pale Gold / Off-White Text
        base_text = QColor("#FFF8E1") 
        
        palette.setColor(QPalette.Window, base_bg)
        palette.setColor(QPalette.WindowText, base_text)
        palette.setColor(QPalette.Base, QColor("#0a0a0a"))   # Slightly lighter black for inputs
        palette.setColor(QPalette.AlternateBase, QColor("#1a1a1a"))
        palette.setColor(QPalette.ToolTipBase, QColor("#1a1a1a"))
        palette.setColor(QPalette.ToolTipText, base_text)
        palette.setColor(QPalette.Text, base_text)
        palette.setColor(QPalette.Button, QColor("#1a1a1a"))
        palette.setColor(QPalette.ButtonText, base_text)
        palette.setColor(QPalette.BrightText, QColor("#FFD700")) # Gold
        palette.setColor(QPalette.Link, QColor("#FFD700"))       # Gold
        palette.setColor(QPalette.Highlight, QColor("#FFD700"))  # Gold
        palette.setColor(QPalette.HighlightedText, QColor("#000000")) # Black text on Gold

    def get_editor_style(self, editor_bg: str = None, text_color: str = None, global_bg: str = None) -> str:
        bg_color = "#000000"
        text_color = "#FFF8E1"
        accent_color = "#FFD700" # Gold
        code_bg = "#111111"
        border_color = "#333333"
        sel_bg = "#FFD700"
        sel_text = "#000000"
        
        return self._generate_editor_css(bg_color, text_color, sel_bg, sel_text, accent_color, code_bg, border_color)

    def get_title_style(self, global_bg: str = None, text_color: str = None) -> str:
        bg_color = "#000000"
        text_color = "#FFD700" # Gold Title
        return self._generate_title_css(bg_color, text_color)

    def get_code_bg_color(self) -> QColor:
        return QColor("#1a1a1a")

    def get_syntax_colors(self) -> dict:
        return {
            "keyword": "#FFD700",       # Gold
            "keyword_pseudo": "#FFB300",# Amber
            "string": "#F0E68C",        # Khaki
            "comment": "#666666",       # Grey
            "function": "#FFF8E1",      # Off-White (or maybe a soft yellow? #FAFAD2)
            "class": "#FFD700",         # Gold
            "number": "#DAA520",        # GoldenRod
            "decorator": "#B8860B",     # DarkGoldenRod
            "default": "#FFF8E1",       # Off-White
            "inline_code": "#FFD700",   # Gold
            "highlight_bg": "#333333",  
            "highlight_text": "#FFD700"
        }

    def get_sidebar_style(self, sidebar_bg: str = None, text_color: str = None) -> str:
        tree_bg = "#000000"
        text_color = "#FFF8E1"
        hover_bg = "rgba(255, 215, 0, 0.1)" # Gold tint
        selected_bg = "rgba(255, 215, 0, 0.2)" # Stronger Gold tint
        accent_border = "#FFD700"
        return self._generate_sidebar_css(tree_bg, text_color, hover_bg, selected_bg, accent_border)

    def get_toolbar_style(self, global_bg: str = None) -> str:
        bg = "#000000"
        border = "#333333"
        return self._generate_toolbar_css(bg, border)

    def get_scrollbar_style(self) -> str:
        handle = "#333333"
        handle_hover = "#FFD700" # Gold on hover
        return self._generate_scrollbar_css(handle, handle_hover)

    def get_search_bar_style(self, global_bg: str = None, text_color: str = None) -> str:
        bg_color = "rgba(255, 255, 255, 0.05)"
        text_color = "#FFF8E1"
        border_color = "#333333"
        focus_border = "#FFD700"
        return self._generate_search_bar_css(bg_color, text_color, border_color, focus_border)

    def get_title_bar_style(self, global_bg: str = None, text_color: str = None) -> str:
        bg_color = "#000000"
        text_color = "#FFD700"
        border_color = "#333333"
        btn_hover = "rgba(255, 215, 0, 0.1)"
        btn_pressed = "rgba(255, 215, 0, 0.2)"
        return self._generate_title_bar_css(bg_color, text_color, border_color, btn_hover, btn_pressed)
