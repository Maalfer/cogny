from .base_theme import BaseTheme
from PySide6.QtGui import QPalette, QColor

class LightTheme(BaseTheme):
    @property
    def name(self) -> str:
        return "Light"

    def apply_palette(self, palette: QPalette, global_bg: str = None, text_color: str = None):
        base_bg = QColor(global_bg) if global_bg else QColor("#f4f4f5")
        base_text = QColor(text_color) if text_color else QColor("#18181b")
        palette.setColor(QPalette.Window, base_bg)
        palette.setColor(QPalette.WindowText, base_text)
        palette.setColor(QPalette.Base, QColor("#ffffff"))
        palette.setColor(QPalette.AlternateBase, QColor("#f4f4f5"))
        palette.setColor(QPalette.ToolTipBase, QColor("#ffffff"))
        palette.setColor(QPalette.ToolTipText, base_text)
        palette.setColor(QPalette.Text, base_text)
        palette.setColor(QPalette.Button, QColor("#e4e4e7"))
        palette.setColor(QPalette.ButtonText, base_text)
        palette.setColor(QPalette.BrightText, QColor("#dc2626")) # Red-600
        palette.setColor(QPalette.Link, QColor("#2563eb"))      # Blue-600
        palette.setColor(QPalette.Highlight, QColor("#2563eb")) # Blue-600
        palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))

    def get_editor_style(self, editor_bg: str = None, text_color: str = None, global_bg: str = None) -> str:
        default_bg = global_bg if global_bg else "#ffffff"
        bg_color = editor_bg if editor_bg else default_bg
        text_color = text_color if text_color else "#18181b"
        accent_color = "#2563eb" # Blue-600
        code_bg = "#f4f4f5"
        border_color = "#e4e4e7"
        sel_bg = "#93c5fd"
        sel_text = "#000000"
        
        return self._generate_editor_css(bg_color, text_color, sel_bg, sel_text, accent_color, code_bg, border_color)

    def get_title_style(self, global_bg: str = None, text_color: str = None) -> str:
        bg_color = global_bg if global_bg else "#ffffff"
        text_color = text_color if text_color else "#18181b"
        return self._generate_title_css(bg_color, text_color)

    def get_code_bg_color(self) -> QColor:
        return QColor("#f4f4f5") # Zinc-100

    def get_syntax_colors(self) -> dict:
        return {
            "keyword": "#db2777",       # Pink-600
            "keyword_pseudo": "#7c3aed",# Violet-600
            "string": "#ca8a04",        # Yellow-600
            "comment": "#a1a1aa",       # Zinc-400
            "function": "#16a34a",      # Green-600
            "class": "#2563eb",         # Blue-600
            "number": "#a21caf",        # Fuchsia-700
            "operator": "#18181b",      # Zinc-900
            "decorator": "#9333ea",     # Purple-600
            "default": "#18181b",       # Zinc-900
            "inline_code": "#ea580c",   # Orange-600
            "highlight_bg": "#fef08a",  # Yellow-200
            "highlight_text": "#000000"
        }

    def get_sidebar_style(self, sidebar_bg: str = None, text_color: str = None) -> str:
        tree_bg = sidebar_bg if sidebar_bg else "transparent"
        text_color = text_color if text_color else "#18181b"
        hover_bg = "rgba(0, 0, 0, 0.05)"
        selected_bg = "rgba(0, 0, 0, 0.1)"
        accent_border = "#2563eb"
        return self._generate_sidebar_css(tree_bg, text_color, hover_bg, selected_bg, accent_border)

    def get_splitter_style(self) -> str:
        return self._generate_splitter_css()

    def get_toolbar_style(self, global_bg: str = None) -> str:
        bg = global_bg if global_bg else "#f4f4f5"
        border = "#e4e4e7"
        return self._generate_toolbar_css(bg, border)

    def get_scrollbar_style(self) -> str:
        handle = "#cbd5e1" # Slate-300
        handle_hover = "#94a3b8" # Slate-400
        return self._generate_scrollbar_css(handle, handle_hover)

    def get_search_bar_style(self, global_bg: str = None, text_color: str = None) -> str:
        bg_color = "rgba(255, 255, 255, 0.5)"
        text_color = text_color if text_color else "#18181b"
        border_color = "rgba(0, 0, 0, 0.1)"
        focus_border = "#2563eb"
        return self._generate_search_bar_css(bg_color, text_color, border_color, focus_border)

    def get_title_bar_style(self, global_bg: str = None, text_color: str = None) -> str:
        bg_color = global_bg if global_bg else "#f4f4f5"
        text_color = text_color if text_color else "#18181b"
        border_color = "#e4e4e7"
        btn_hover = "rgba(0, 0, 0, 0.05)"
        btn_pressed = "rgba(0, 0, 0, 0.1)"
        return self._generate_title_bar_css(bg_color, text_color, border_color, btn_hover, btn_pressed)

    def get_tab_style(self, global_bg: str = None) -> str:
        bg = global_bg if global_bg else "#f4f4f5"
        border = "#e4e4e7"
        selected_bg = "#ffffff"
        hover_bg = "#e4e4e7" # Zinc-200
        text = "#18181b"
        return self._generate_tab_css(bg, border, selected_bg, hover_bg, text)

    # --- Helpers to DRY css (Assuming same structure for all, copied from themes.py) ---
    def _generate_editor_css(self, bg_color, text_color, sel_bg, sel_text, accent_color, code_bg, border_color):
        return f"""
            NoteEditor {{
                padding-left: 0px;
                padding-right: 0px;
                padding-top: 0px;
                padding-bottom: 10px;
                background-color: {bg_color};
                color: {text_color};
                selection-background-color: {sel_bg};
                selection-color: {sel_text};
                border: none;
            }}
            /* Markdown Headers */
            h1 {{ font-size: 28px; color: {text_color}; font-weight: 600; margin-top: 30px; margin-bottom: 15px; letter-spacing: -0.5px; }}
            h2 {{ font-size: 24px; color: {text_color}; font-weight: 600; margin-top: 25px; margin-bottom: 12px; letter-spacing: -0.3px; }}
            h3 {{ font-size: 20px; color: {text_color}; font-weight: 600; margin-top: 20px; margin-bottom: 10px; }}
            h4 {{ font-size: 18px; color: {text_color}; font-weight: 600; margin-top: 18px; }}
            h5 {{ font-size: 16px; font-weight: 600; font-style: italic; color: #a1a1aa; }}
            h6 {{ font-size: 14px; font-weight: 600; font-style: italic; color: #71717a; }}
            
            blockquote {{
                border-left: 3px solid {accent_color};
                padding-left: 15px;
                color: #52525b;
                margin-left: 5px;
                font-style: italic;
            }}
            
            ul, ol {{ margin-left: 20px; color: {text_color}; }}
            li {{ margin-bottom: 8px; line-height: 1.6; }}
            
            pre {{
                background-color: {code_bg};
                border: 1px solid {border_color};
                padding: 15px;
                border-radius: 8px;
                color: #e4e4e7;
                font-family: Consolas, "JetBrains Mono", monospace;
                line-height: 1.5;
            }}
            code {{
                background-color: #2e2e31;
                padding: 2px 6px;
                border-radius: 4px;
                font-family: Consolas, "JetBrains Mono", monospace;
                color: #fb923c; /* Orange-400 */
            }}
            a {{ color: {accent_color}; text-decoration: none; }}
            
            img {{
                max-width: 100%;
                border-radius: 8px;
                margin-top: 20px;
                margin-bottom: 20px;
            }}
            hr {{
                border: none;
                background-color: {border_color};
                height: 1px;
                margin-top: 40px;
                margin-bottom: 40px;
            }}
            
            table {{
                border-collapse: separate;
                border-spacing: 0;
                width: 100%;
                margin-top: 20px;
                margin-bottom: 20px;
            }}
            th, td {{
                border-bottom: 1px solid {border_color};
                padding: 12px;
                text-align: left;
            }}
            th {{
                color: {text_color};
                font-weight: 600;
                border-bottom: 2px solid {border_color};
                background-color: transparent;
            }}
            
            QPlainTextEdit#TitleEdit {{
                font-size: 32px;
                font-weight: 700;
                border: none;
                background-color: {bg_color};
                color: {text_color};
                padding-left: 0px;
                padding-right: 0px;
                padding-top: 10px;
                padding-bottom: 0px;
                margin-bottom: 0px;
            }}
            QToolButton {{
                background-color: transparent;
                color: #52525b;
                border: none;
                border-radius: 4px;
                padding: 4px;
                font-size: 12px;
            }}
            QToolButton:hover {{
                background-color: {code_bg};
                color: {text_color};
            }}
            QToolButton:pressed {{
                background-color: {border_color};
            }}
            """

    def _generate_title_css(self, bg_color, text_color):
        return f"""
            QPlainTextEdit#TitleEdit {{
                font-size: 32px;
                font-weight: 700;
                border: none;
                background-color: {bg_color};
                color: {text_color};
                padding-left: 0px;
                padding-right: 0px;
                padding-top: 10px;
                padding-bottom: 0px;
                margin-bottom: 0px;
            }}
        """

    def _generate_sidebar_css(self, tree_bg, text_color, hover_bg, selected_bg, accent_border):
        return f"""
            QTreeView {{
                background-color: {tree_bg};
                border: none;
                color: {text_color};
                outline: 0;
                selection-background-color: transparent;
                show-decoration-selected: 0;
            }}
            QTreeView::item {{
                padding: 6px;
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
                border-top-left-radius: 0px;
                border-bottom-left-radius: 0px;
                margin-left: 0px; 
                margin-right: 4px;
                margin-bottom: 0px;
            }}
            QTreeView::item:hover {{
                background-color: {hover_bg};
            }}
            QTreeView::item:selected {{
                background-color: {selected_bg};
                color: {text_color};
                border-left: 3px solid {accent_border}; 
            }}
            QTreeView::item:selected:active {{
                background-color: {selected_bg};
            }}
            QTreeView::item:selected:!active {{
                background-color: {selected_bg};
            }}
            
            QTreeView::branch:hover {{
                background-color: {hover_bg};
            }}
            QTreeView::branch:selected {{
                background-color: {selected_bg};
            }}

            QTreeView::branch:has-children:!has-siblings:closed,
            QTreeView::branch:closed:has-children:has-siblings {{
                border-image: none;
                image: none;
            }}
            """

    def _generate_splitter_css(self):
        return f"""
        QSplitter::handle {{
            background-color: transparent;
            height: 0px; /* For vertical splitters if any */
            width: 0px;  /* For horizontal splitters */
        }}
        """

    def _generate_toolbar_css(self, bg, border):
        return f"""
        QToolBar {{
            background: {bg};
            border-bottom: 1px solid {border};
            spacing: 5px;
            padding: 5px;
            border: none;
        }}
        QToolBar::handle {{
            image: none;
            width: 0px;
        }}
        QToolBar::separator {{
            background-color: {border};
            width: 1px;
            margin: 5px;
        }}
        """

    def _generate_scrollbar_css(self, handle, handle_hover):
        return f"""
        QScrollBar:vertical {{
            border: none;
            background-color: transparent;
            width: 12px;
            margin: 0px 0px 0px 0px;
        }}
        QScrollBar::handle:vertical {{
            background-color: {handle};
            min-height: 30px;
            border-radius: 6px;
            margin: 2px 2px 2px 2px;
        }}
        QScrollBar::handle:vertical:hover {{
            background-color: {handle_hover};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
            background: none;
        }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: none;
        }}

        QScrollBar:horizontal {{
            border: none;
            background-color: transparent;
            height: 12px;
            margin: 0px 0px 0px 0px;
        }}
        QScrollBar::handle:horizontal {{
            background-color: {handle};
            min-width: 30px;
            border-radius: 6px;
            margin: 2px 2px 2px 2px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background-color: {handle_hover};
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
            background: none;
        }}
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
            background: none;
        }}
        """

    def _generate_search_bar_css(self, bg_color, text_color, border_color, focus_border):
        return f"""
            QLineEdit {{
                border: 1px solid {border_color};
                border-radius: 15px;
                padding: 5px 10px;
                background-color: {bg_color};
                color: {text_color};
                min-width: 200px;
                selection-background-color: {focus_border};
                selection-color: {bg_color};
            }}
            QLineEdit:focus {{
                border: 1px solid {focus_border};
            }}
        """

    def _generate_title_bar_css(self, bg_color, text_color, border_color, btn_hover, btn_pressed):
        return f"""
            QWidget#CustomTitleBar {{
                background-color: {bg_color};
                border-bottom: 1px solid {border_color};
            }}
            QLabel#TitleLabel {{
                color: {text_color};
                font-weight: bold;
            }}
            QToolButton {{
                background: transparent;
                border: none;
                border-radius: 4px;
                padding: 4px;
            }}
            QToolButton:hover {{
                background-color: {btn_hover};
            }}
            QToolButton:pressed {{
                background-color: {btn_pressed};
            }}
        """

    def _generate_tab_css(self, bg, border, selected_bg, hover_bg, text):
        return f"""
        QTabWidget::pane {{
            border: 1px solid {border};
            background: {selected_bg};
            border-radius: 4px;
        }}
        QTabBar::tab {{
            background: {bg};
            color: {text};
            border: 1px solid transparent;
            padding: 8px 12px;
            margin-right: 2px;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        }}
        QTabBar::tab:hover {{
            background: {hover_bg};
        }}
        QTabBar::tab:selected {{
            background: {selected_bg};
            border: 1px solid {border};
            border-bottom: 1px solid {selected_bg}; /* Blend with pane */
        }}
        QTabBar::close-button {{
            image: url(close.svg); /* Placeholder or leave default */
            subcontrol-position: right;
        }}
        """
