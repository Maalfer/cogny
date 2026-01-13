from PySide6.QtGui import QPalette, QColor

class ThemeManager:
    @staticmethod
    def get_palette(theme: str, sidebar_bg: str = None) -> QPalette:
        palette = QPalette()
        if theme == "Dark":
            base_bg = QColor(sidebar_bg) if sidebar_bg else QColor("#1e1e1e")
            palette.setColor(QPalette.Window, base_bg)
            palette.setColor(QPalette.WindowText, QColor("#d4d4d4"))
            palette.setColor(QPalette.Base, QColor("#252526"))
            palette.setColor(QPalette.AlternateBase, QColor("#333333"))
            palette.setColor(QPalette.ToolTipBase, QColor("black"))
            palette.setColor(QPalette.ToolTipText, QColor("white"))
            palette.setColor(QPalette.Text, QColor("#d4d4d4"))
            palette.setColor(QPalette.Button, QColor("#3c3c3c"))
            palette.setColor(QPalette.ButtonText, QColor("#d4d4d4"))
            palette.setColor(QPalette.BrightText, QColor("red"))
            palette.setColor(QPalette.Link, QColor("#4A90E2"))
            palette.setColor(QPalette.Highlight, QColor("#062f4a"))
            palette.setColor(QPalette.HighlightedText, QColor("white"))
        else:
            base_bg = QColor(sidebar_bg) if sidebar_bg else QColor("#E0E0E0")
            palette.setColor(QPalette.Window, base_bg)
            palette.setColor(QPalette.WindowText, QColor("#202020"))
            palette.setColor(QPalette.Base, QColor("#FAFAFA"))
            palette.setColor(QPalette.AlternateBase, QColor("#F0F0F0"))
            palette.setColor(QPalette.ToolTipBase, QColor("#FFFFDC"))
            palette.setColor(QPalette.ToolTipText, QColor("black"))
            palette.setColor(QPalette.Text, QColor("#202020"))
            palette.setColor(QPalette.Button, QColor("#D0D0D0"))
            palette.setColor(QPalette.ButtonText, QColor("#202020"))
            palette.setColor(QPalette.BrightText, QColor("red"))
            palette.setColor(QPalette.Link, QColor("#4A90E2"))
            palette.setColor(QPalette.Highlight, QColor("#4A90E2"))
            palette.setColor(QPalette.HighlightedText, QColor("white"))
        return palette

    @staticmethod
    def get_editor_style(theme: str, editor_bg: str = None) -> str:
        if theme == "Dark":
            bg_color = editor_bg if editor_bg else "#1e1e1e"
            return f"""
            NoteEditor {{
                padding-left: 60px;
                padding-right: 60px;
                padding-top: 30px;
                padding-bottom: 30px;
                background-color: {bg_color};
                color: #d4d4d4;
                selection-background-color: #264f78;
                selection-color: white;
            }}
            /* Limit Image Width for cleaner layout */
            img {{
                max-width: 600px;
                border-radius: 12px;
                margin-top: 15px;
                margin-bottom: 15px;
            }}
            hr {{
                border: none;
                background-color: #505050;
                height: 2px;
                margin-top: 20px;
                margin-bottom: 20px;
            }}
            /* Inline Title Style */
            QPlainTextEdit#TitleEdit {{
                font-size: 28px;
                font-weight: bold;
                border: none;
                background-color: {bg_color};
                color: #d4d4d4;
                padding-left: 60px;
                padding-right: 60px;
                padding-top: 20px;
                padding-bottom: 10px;
                margin-bottom: 0px;
            }}
            QToolButton {{
                background-color: #3c3c3c;
                color: #d4d4d4;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 2px;
                font-size: 10px;
            }}
            QToolButton:hover {{
                background-color: #505050;
                color: white;
            }}
            QToolButton:pressed {{
                background-color: #252526;
            }}
            
            /* Modern Scrollbar (Dark) */
            QScrollBar:vertical {{
                border: none;
                background-color: transparent;
                width: 14px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background-color: #424242;
                min-height: 20px;
                border-radius: 7px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: #4F4F4F;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
            """
        else: # Light
            bg_color = editor_bg if editor_bg else "#FAFAFA"
            return f"""
            NoteEditor {{
                padding-left: 60px;
                padding-right: 60px;
                padding-top: 30px;
                padding-bottom: 30px;
                background-color: {bg_color};
                color: #202020;
            }}
            img {{
                max-width: 600px;
                border-radius: 12px;
                margin-top: 15px;
                margin-bottom: 15px;
            }}
            hr {{
                border: none;
                background-color: #B0B0B0;
                height: 2px;
                margin-top: 20px;
                margin-bottom: 20px;
            }}
            /* Inline Title Style */
            QPlainTextEdit#TitleEdit {{
                font-size: 28px;
                font-weight: bold;
                border: none;
                background-color: {bg_color};
                color: #202020;
                padding-left: 60px;
                padding-right: 60px;
                padding-top: 20px;
                padding-bottom: 10px;
                margin-bottom: 0px;
            }}
            QToolButton {{
                background-color: #D5D8DC;
                color: #202020;
                border: 1px solid #B0B0B0;
                border-radius: 4px;
                padding: 2px;
                font-size: 10px;
            }}
            QToolButton:hover {{
                background-color: #AAB7B8;
                color: black;
            }}
            QToolButton:pressed {{
                background-color: #99A3A4;
            }}
            
            /* Modern Scrollbar (Light) */
            QScrollBar:vertical {{
                border: none;
                background-color: transparent;
                width: 14px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background-color: #C1C1C1;
                min-height: 20px;
                border-radius: 7px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: #A8A8A8;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
            """

    @staticmethod
    def get_code_bg_color(theme: str) -> QColor:
        if theme == "Dark":
            return QColor("#2d2d2d") # Dark Gray for code blocks
        else:
            return QColor("#EEF1F4") # Light Gray-Blue

    @staticmethod
    def get_syntax_colors(theme: str) -> dict:
        if theme == "Dark":
            return {
                "keyword": "#569CD6",       # Blue
                "keyword_pseudo": "#C586C0",# Purple (this, super)
                "string": "#CE9178",        # Orange/Redish
                "comment": "#6A9955",       # Green
                "function": "#DCDCAA",      # Yellow
                "class": "#4EC9B0",         # Cyan
                "number": "#B5CEA8",        # Light Green
                "operator": "#D4D4D4",      # White
                "decorator": "#DCDCAA",     # Yellow
                "default": "#D4D4D4",       # White
                "inline_code": "#CE9178"    # Orange/Redish (Same as String for now, or distinct?)
                                            # User wants emphasis. Let's use a specialized bright color?
                                            # #E67E22 (Carrot/Orange)
            }
        else: # Light
            return {
                "keyword": "#0000FF",       # Blue
                "keyword_pseudo": "#AF00DB",# Purple
                "string": "#A31515",        # Red
                "comment": "#008000",       # Green
                "function": "#795E26",      # Brown/Gold
                "class": "#267F99",         # Teal
                "number": "#098658",        # Dark Green
                "operator": "#000000",      # Black
                "decorator": "#AF00DB",     # Purple
                "default": "#000000",       # Black
                "inline_code": "#E67E22"    # Bright Orange for emphasis
            }
