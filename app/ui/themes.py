from PySide6.QtGui import QPalette, QColor

class ThemeManager:
    @staticmethod
    def get_palette(theme: str, sidebar_bg: str = None) -> QPalette:
        palette = QPalette()
        if theme == "Dark":
            # Zinc-based Dark Theme
            # Background: #18181b (Zinc-900)
            # Surface: #27272a (Zinc-800)
            # Text: #e4e4e7 (Zinc-200)
            # Accent: #3b82f6 (Blue-500)
            
            base_bg = QColor(sidebar_bg) if sidebar_bg else QColor("#18181b") 
            palette.setColor(QPalette.Window, base_bg)
            palette.setColor(QPalette.WindowText, QColor("#e4e4e7"))
            palette.setColor(QPalette.Base, QColor("#27272a")) # Slightly lighter than Window
            palette.setColor(QPalette.AlternateBase, QColor("#3f3f46"))
            palette.setColor(QPalette.ToolTipBase, QColor("#18181b"))
            palette.setColor(QPalette.ToolTipText, QColor("#e4e4e7"))
            palette.setColor(QPalette.Text, QColor("#e4e4e7"))
            palette.setColor(QPalette.Button, QColor("#27272a"))
            palette.setColor(QPalette.ButtonText, QColor("#e4e4e7"))
            palette.setColor(QPalette.BrightText, QColor("#ef4444")) # Red-500
            palette.setColor(QPalette.Link, QColor("#3b82f6"))      # Blue-500
            palette.setColor(QPalette.Highlight, QColor("#3b82f6")) # Blue-500
            palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
        else:
            # Modern Light Theme
            # Background: #ffffff (White)
            # Surface: #f4f4f5 (Zinc-100)
            # Text: #18181b (Zinc-900)
            # Accent: #2563eb (Blue-600)

            base_bg = QColor(sidebar_bg) if sidebar_bg else QColor("#f4f4f5")
            palette.setColor(QPalette.Window, base_bg)
            palette.setColor(QPalette.WindowText, QColor("#18181b"))
            palette.setColor(QPalette.Base, QColor("#ffffff"))
            palette.setColor(QPalette.AlternateBase, QColor("#f4f4f5"))
            palette.setColor(QPalette.ToolTipBase, QColor("#ffffff"))
            palette.setColor(QPalette.ToolTipText, QColor("#18181b"))
            palette.setColor(QPalette.Text, QColor("#18181b"))
            palette.setColor(QPalette.Button, QColor("#e4e4e7"))
            palette.setColor(QPalette.ButtonText, QColor("#18181b"))
            palette.setColor(QPalette.BrightText, QColor("#dc2626")) # Red-600
            palette.setColor(QPalette.Link, QColor("#2563eb"))      # Blue-600
            palette.setColor(QPalette.Highlight, QColor("#2563eb")) # Blue-600
            palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
        return palette

    @staticmethod
    def get_editor_style(theme: str, editor_bg: str = None) -> str:
        if theme == "Dark":
            bg_color = editor_bg if editor_bg else "#18181b"
            text_color = "#e4e4e7"
            accent_color = "#60a5fa" # Blue-400 for text accents
            code_bg = "#27272a"
            border_color = "#3f3f46"
            
            return f"""
            NoteEditor {{
                padding-left: 80px;
                padding-right: 80px;
                padding-top: 40px;
                padding-bottom: 40px;
                background-color: {bg_color};
                color: {text_color};
                selection-background-color: #3b82f6;
                selection-color: white;
            }}
            /* Markdown Headers */
            h1 {{ font-size: 28px; color: {text_color}; font-weight: 600; margin-top: 30px; margin-bottom: 15px; letter-spacing: -0.5px; }}
            h2 {{ font-size: 24px; color: {text_color}; font-weight: 600; margin-top: 25px; margin-bottom: 12px; letter-spacing: -0.3px; }}
            h3 {{ font-size: 20px; color: {text_color}; font-weight: 600; margin-top: 20px; margin-bottom: 10px; }}
            h4 {{ font-size: 18px; color: {text_color}; font-weight: 600; margin-top: 18px; }}
            h5 {{ font-size: 16px; font-weight: 600; font-style: italic; color: #a1a1aa; }}
            h6 {{ font-size: 14px; font-weight: 600; font-style: italic; color: #71717a; }}
            
            /* Blockquotes */
            blockquote {{
                border-left: 3px solid {accent_color};
                padding-left: 15px;
                color: #a1a1aa;
                margin-left: 5px;
                font-style: italic;
            }}
            
            /* Lists */
            ul, ol {{ margin-left: 20px; color: {text_color}; }}
            li {{ margin-bottom: 8px; line-height: 1.6; }}
            
            /* Code Blocks (pre) & Inline Code (code) */
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
            
            /* Clean Image Layout */
            img {{
                max-width: 700px;
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
            /* Table Styling */
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
            }}
            
            /* Editor Widgets */
            QPlainTextEdit#TitleEdit {{
                font-size: 36px;
                font-weight: 700;
                border: none;
                background-color: {bg_color};
                color: {text_color};
                padding-left: 80px;
                padding-right: 80px;
                padding-top: 30px;
                padding-bottom: 10px;
                margin-bottom: 10px;
            }}
            QToolButton {{
                background-color: transparent;
                color: #a1a1aa;
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
            
            /* Minimal Scrollbar */
            QScrollBar:vertical {{
                border: none;
                background-color: transparent;
                width: 10px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background-color: #3f3f46;
                min-height: 30px;
                border-radius: 5px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: #52525b;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
            """

        else: # Light
            bg_color = editor_bg if editor_bg else "#ffffff"
            text_color = "#18181b"
            accent_color = "#2563eb" # Blue-600
            code_bg = "#f4f4f5"
            border_color = "#e4e4e7"

            return f"""
            NoteEditor {{
                padding-left: 80px;
                padding-right: 80px;
                padding-top: 40px;
                padding-bottom: 40px;
                background-color: {bg_color};
                color: {text_color};
                selection-background-color: #93c5fd; /* Blue-300 */
                selection-color: black;
            }}
            /* Markdown Headers */
            h1 {{ font-size: 28px; color: {text_color}; font-weight: 600; margin-top: 30px; margin-bottom: 15px; letter-spacing: -0.5px; }}
            h2 {{ font-size: 24px; color: {text_color}; font-weight: 600; margin-top: 25px; margin-bottom: 12px; letter-spacing: -0.3px; }}
            h3 {{ font-size: 20px; color: {text_color}; font-weight: 600; margin-top: 20px; margin-bottom: 10px; }}
            h4 {{ font-size: 18px; color: {text_color}; font-weight: 600; margin-top: 18px; }}
            h5 {{ font-size: 16px; font-weight: 600; font-style: italic; color: #52525b; }}
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
                color: #18181b;
                font-family: Consolas, "JetBrains Mono", monospace;
                line-height: 1.5;
            }}
            code {{
                background-color: #e4e4e7;
                padding: 2px 6px;
                border-radius: 4px;
                font-family: Consolas, "JetBrains Mono", monospace;
                color: #ea580c; /* Orange-600 */
            }}
            a {{ color: {accent_color}; text-decoration: none; }}
            
            img {{
                max-width: 700px;
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
                font-size: 36px;
                font-weight: 700;
                border: none;
                background-color: {bg_color};
                color: {text_color};
                padding-left: 80px;
                padding-right: 80px;
                padding-top: 30px;
                padding-bottom: 10px;
                margin-bottom: 10px;
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
            
            /* Minimal Scrollbar */
            QScrollBar:vertical {{
                border: none;
                background-color: transparent;
                width: 10px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background-color: #d4d4d8;
                min-height: 30px;
                border-radius: 5px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: #a1a1aa;
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
            return QColor("#27272a") # Zinc-800
        else:
            return QColor("#f4f4f5") # Zinc-100

    @staticmethod
    def get_syntax_colors(theme: str) -> dict:
        if theme == "Dark":
            return {
                "keyword": "#60a5fa",       # Blue-400
                "keyword_pseudo": "#c084fc",# Purple-400
                "string": "#fb923c",        # Orange-400
                "comment": "#71717a",       # Zinc-500
                "function": "#facc15",      # Yellow-400
                "class": "#34d399",         # Emerald-400
                "number": "#f87171",        # Red-400
                "operator": "#e4e4e7",      # Zinc-200
                "decorator": "#c084fc",     # Purple-400
                "default": "#e4e4e7",       # Zinc-200
                "inline_code": "#fb923c"    # Orange-400
            }
        else: # Light
            return {
                "keyword": "#2563eb",       # Blue-600
                "keyword_pseudo": "#9333ea",# Purple-600
                "string": "#ea580c",        # Orange-600
                "comment": "#a1a1aa",       # Zinc-400
                "function": "#ca8a04",      # Yellow-600
                "class": "#059669",         # Emerald-600
                "number": "#dc2626",        # Red-600
                "operator": "#18181b",      # Zinc-900
                "decorator": "#9333ea",     # Purple-600
                "default": "#18181b",       # Zinc-900
                "inline_code": "#ea580c"    # Orange-600
            }

    @staticmethod
    def get_sidebar_style(theme: str) -> str:
        """Provides CSS for the Sidebar QTreeView."""
        if theme == "Dark":
            # Zinc-based Sidebar
            hover_bg = "#27272a"
            selected_bg = "#27272a" 
            text_color = "#e4e4e7"
            accent_border = "#3b82f6"
            
            return f"""
            QTreeView {{
                background-color: transparent;
                border: none;
                color: {text_color};
                outline: 0;
            }}
            QTreeView::item {{
                padding: 6px;
                border-radius: 6px;
                margin-left: 4px;
                margin-right: 4px;
                margin-bottom: 2px;
            }}
            QTreeView::item:hover {{
                background-color: {hover_bg};
            }}
            QTreeView::item:selected {{
                background-color: {selected_bg};
                color: #ffffff;
                border-left: 3px solid {accent_border}; 
            }}
            QTreeView::item:selected:active {{
                background-color: {selected_bg};
            }}
            QTreeView::item:selected:!active {{
                background-color: {selected_bg};
            }}
            QTreeView::branch:has-children:!has-siblings:closed,
            QTreeView::branch:closed:has-children:has-siblings {{
                border-image: none;
                image: none;
            }}
            """
        else: # Light
            hover_bg = "#f4f4f5"
            selected_bg = "#f4f4f5"
            text_color = "#18181b"
            accent_border = "#2563eb"
             
            return f"""
            QTreeView {{
                background-color: transparent;
                border: none;
                color: {text_color};
                outline: 0;
            }}
            QTreeView::item {{
                padding: 6px;
                border-radius: 6px;
                margin-left: 4px;
                margin-right: 4px;
                margin-bottom: 2px;
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
            """
