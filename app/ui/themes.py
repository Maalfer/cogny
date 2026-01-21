from PySide6.QtGui import QPalette, QColor

class ThemeManager:
    @staticmethod
    @staticmethod
    def get_palette(theme: str, global_bg: str = None, text_color: str = None) -> QPalette:
        palette = QPalette()

        if theme == "Dracula":
            # Dracula Theme
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
            
        elif theme == "AnuPpuccin":
            # Catppuccin Mocha Theme
            # Background: #1e1e2e
            # Base/Sidebar: #11111b (Crust)
            # Text: #cdd6f4
            # Accent: #cba6f7 (Mauve)
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

        elif theme == "Dark":
            # Modern Dark Theme (Zinc-950/900)
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

        else:
            # Modern Light Theme
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
        return palette

    @staticmethod
    def get_editor_style(theme: str, editor_bg: str = None, text_color: str = None, global_bg: str = None) -> str:
        if theme == "Dracula":
            # Default to global_bg if provided, else theme default
            default_bg = global_bg if global_bg else "#282a36"
            bg_color = editor_bg if editor_bg else default_bg
            text_color = text_color if text_color else "#f8f8f2"
            accent_color = "#8be9fd" # Cyan
            code_bg = "#44475a" # Dracula Surface
            border_color = "#6272a4" # Dracula Comment
            sel_bg = "#bd93f9"
            sel_text = "#282a36"

        elif theme == "AnuPpuccin":
            default_bg = global_bg if global_bg else "#1e1e2e"
            bg_color = editor_bg if editor_bg else default_bg
            text_color = text_color if text_color else "#cdd6f4"
            accent_color = "#cba6f7" # Mauve
            code_bg = "#181825" # Mantle
            border_color = "#313244" # Surface0
            sel_bg = "#45475a" # Surface1
            sel_text = "#cdd6f4"

        elif theme == "Dark":
            default_bg = global_bg if global_bg else "#18181b"
            bg_color = editor_bg if editor_bg else default_bg
            text_color = text_color if text_color else "#e4e4e7"
            accent_color = "#60a5fa" # Blue-400
            code_bg = "#52525b" # Zinc-600
            border_color = "#a1a1aa" # Zinc-400
            sel_bg = "#3b82f6"
            sel_text = "#ffffff"

        else: # Light
            default_bg = global_bg if global_bg else "#ffffff"
            bg_color = editor_bg if editor_bg else default_bg
            text_color = text_color if text_color else "#18181b"
            accent_color = "#2563eb" # Blue-600
            code_bg = "#f4f4f5"
            border_color = "#e4e4e7"
            sel_bg = "#93c5fd"
            sel_text = "#000000"
        return f"""
            NoteEditor {{
                padding-left: 80px;
                padding-right: 80px;
                padding-top: 40px;
                padding-bottom: 40px;
                background-color: {bg_color};
                color: {text_color};
                selection-background-color: {sel_bg};
                selection-color: {sel_text};
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
                font-size: 32px;
                font-weight: 700;
                border: none;
                border-bottom: 2px solid {border_color};
                background-color: {bg_color};
                color: {text_color};
                padding-left: 80px;
                padding-right: 80px;
                padding-top: 30px;
                padding-bottom: 10px;
                margin-left: 20px;
                margin-right: 20px;
                margin-bottom: 20px;
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


    @staticmethod
    def get_title_style(theme: str, global_bg: str = None, text_color: str = None) -> str:
        """Returns stylesheet for the TitleEditor."""
        if theme == "Dracula":
            bg_color = global_bg if global_bg else "#282a36"
            text_color = text_color if text_color else "#f8f8f2"
            border_color = "#6272a4"
        elif theme == "AnuPpuccin":
            bg_color = global_bg if global_bg else "#1e1e2e"
            text_color = text_color if text_color else "#cdd6f4"
            border_color = "#313244"
        elif theme == "Dark":
            bg_color = global_bg if global_bg else "#18181b"
            text_color = text_color if text_color else "#e4e4e7"
            border_color = "#a1a1aa"
        else: # Light
            bg_color = global_bg if global_bg else "#ffffff"
            text_color = text_color if text_color else "#18181b"
            border_color = "#e4e4e7"

        return f"""
            QPlainTextEdit#TitleEdit {{
                font-size: 32px;
                font-weight: 700;
                border: none;
                border-bottom: 2px solid {border_color};
                background-color: {bg_color};
                color: {text_color};
                padding-left: 80px;
                padding-right: 80px;
                padding-top: 10px;
                padding-bottom: 0px;
                margin-left: 20px;
                margin-right: 20px;
                margin-bottom: 10px;
            }}
        """

    @staticmethod
    def get_code_bg_color(theme: str) -> QColor:
        if theme == "Dracula":
            return QColor("#44475a")
        elif theme == "Dark":
            return QColor("#52525b") # Zinc-600
        else:
            return QColor("#f4f4f5") # Zinc-100

    @staticmethod
    def get_syntax_colors(theme: str) -> dict:
        if theme == "Dracula":
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
                "inline_code": "#f1fa8c"    # Yellow
            }
        elif theme == "Dark":
             # Standard Dark
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
    def get_sidebar_style(theme: str, sidebar_bg: str = None, text_color: str = None) -> str:
        """Provides CSS for the Sidebar QTreeView."""
        # Use custom bg if provided, else keep transparent to use Palette (Window) color
        tree_bg = sidebar_bg if sidebar_bg else "transparent"

        if theme == "Dracula":
            # Dracula Sidebar
            hover_bg = "rgba(255, 255, 255, 0.05)"
            selected_bg = "rgba(0, 0, 0, 0.2)" 
            text_color = text_color if text_color else "#f8f8f2"
            accent_border = "#bd93f9" # Purple
            
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
                margin-bottom: 0px; /* Removed gap to match branch height */
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
            
            /* Uniform Hover/Selection for Branch */
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
        elif theme == "AnuPpuccin":
             # Catppuccin Sidebar
            hover_bg = "rgba(255, 255, 255, 0.05)"
            selected_bg = "rgba(0, 0, 0, 0.2)"
            text_color = text_color if text_color else "#cdd6f4"
            accent_border = "#cba6f7" # Mauve
            
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
        elif theme == "Dark":
            # Zinc-based Sidebar
            hover_bg = "rgba(255, 255, 255, 0.05)"
            selected_bg = "rgba(0, 0, 0, 0.2)"
            text_color = text_color if text_color else "#e4e4e7"
            accent_border = "#3b82f6"
            
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
                color: #ffffff;
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
        else: # Light
            hover_bg = "rgba(0, 0, 0, 0.05)"
            selected_bg = "rgba(0, 0, 0, 0.1)"
            text_color = text_color if text_color else "#18181b"
            accent_border = "#2563eb"
             
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

    @staticmethod
    def get_toolbar_style(theme: str, global_bg: str = None) -> str:
        """Returns a global QToolBar stylesheet."""
        if theme == "Dracula":
            bg = global_bg if global_bg else "#282a36"
            border = "#6272a4"
        elif theme == "AnuPpuccin":
            bg = global_bg if global_bg else "#1e1e2e"
            border = "#313244"
        elif theme == "Dark":
            bg = global_bg if global_bg else "#18181b"
            border = "#3f3f46"
        else: # Light
            bg = global_bg if global_bg else "#f4f4f5"
            border = "#e4e4e7"
            
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

    @staticmethod
    def get_scrollbar_style(theme: str) -> str:
        """Returns a global QScrollBar stylesheet."""
        if theme == "Dracula":
            handle = "#6272a4"
            handle_hover = "#bd93f9"
            bg = "#282a36" 
        elif theme == "AnuPpuccin":
            handle = "#585b70" # Surface2
            handle_hover = "#89b4fa" # Blue
            bg = "#1e1e2e"
        elif theme == "Dark":
            handle = "#3f3f46" # Zinc-700
            handle_hover = "#71717a" # Zinc-500
            bg = "#18181b"
        else: # Light
            handle = "#cbd5e1" # Slate-300
            handle_hover = "#94a3b8" # Slate-400
            bg = "#f4f4f5"

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

    @staticmethod
    def get_code_bg_color(theme: str) -> QColor:
        if theme == "Dracula":
            return QColor("#373A47")
        elif theme == "AnuPpuccin":
             return QColor("#181825") # Mantle
        elif theme == "Dark":
            return QColor("#373E47") # Zinc-600
        else:
            return QColor("#f4f4f5") # Zinc-100

    @staticmethod
    def get_syntax_colors(theme: str) -> dict:
        if theme == "Dracula":
            return {
                "keyword": "#ff79c6",       # Pink
                "keyword_pseudo": "#bd93f9",# Purple
                "string": "#f1fa8c",        # Yellow
                "comment": "#6272a4",       # Comment
                "function": "#50fa7b",      # Green
                "class": "#8be9fd",         # Cyan
                "number": "#bd93f9",        # Purple
                "decorator": "#50fa7b",     # Green
                "default": "#f8f8f2",       # White
                "inline_code": "#ffb86c",    # Orange
                "highlight_bg": "#f1fa8c",  # Yellow (Dracula)
                "highlight_text": "#282a36" # Background color for text
            }
        elif theme == "AnuPpuccin":
             # Catppuccin Mocha Syntax
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
        elif theme == "Dark":
             # Zinc High Contrast
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
        else:
            # Modern Light
            return {
                "keyword": "#db2777",       # Pink-600
                "keyword_pseudo": "#7c3aed",# Violet-600
                "string": "#ca8a04",        # Yellow-600
                "comment": "#a1a1aa",       # Zinc-400
                "function": "#16a34a",      # Green-600
                "class": "#2563eb",         # Blue-600
                "number": "#a21caf",        # Fuchsia-700
                "decorator": "#9333ea",     # Purple-600
                "default": "#18181b",       # Zinc-900
                "inline_code": "#ea580c",   # Orange-600
                "highlight_bg": "#fef08a",  # Yellow-200
                "highlight_text": "#000000"
            }

    @staticmethod
    def get_search_bar_style(theme: str, global_bg: str = None, text_color: str = None) -> str:
        """Returns stylesheet for the main search bar."""
        
        # Use semi-transparent backgrounds to blend with global color
        if theme == "Dracula":
            bg_color = "rgba(0, 0, 0, 0.2)" 
            text_color = text_color if text_color else "#f8f8f2"
            border_color = "rgba(255, 255, 255, 0.1)"
            focus_border = "#bd93f9" # Purple
        elif theme == "AnuPpuccin":
            bg_color = "rgba(0, 0, 0, 0.2)"
            text_color = text_color if text_color else "#cdd6f4"
            border_color = "rgba(255, 255, 255, 0.1)"
            focus_border = "#cba6f7"
        elif theme == "Dark":
            bg_color = "rgba(0, 0, 0, 0.2)"
            text_color = text_color if text_color else "#e4e4e7"
            border_color = "rgba(255, 255, 255, 0.1)"
            focus_border = "#3b82f6"
        else: # Light
            bg_color = "rgba(255, 255, 255, 0.5)"
            text_color = text_color if text_color else "#18181b"
            border_color = "rgba(0, 0, 0, 0.1)"
            focus_border = "#2563eb"

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

    @staticmethod
    def get_title_bar_style(theme: str, global_bg: str = None, text_color: str = None) -> str:
        """Returns stylesheet for CustomTitleBar."""
        
        if theme == "Dracula":
            bg_color = global_bg if global_bg else "#282a36"
            text_color = text_color if text_color else "#f8f8f2"
            border_color = "#6272a4"
            btn_hover = "rgba(255, 255, 255, 0.1)"
            btn_pressed = "rgba(255, 255, 255, 0.15)"
        elif theme == "AnuPpuccin":
            bg_color = global_bg if global_bg else "#1e1e2e"
            text_color = text_color if text_color else "#cdd6f4"
            border_color = "#313244"
            btn_hover = "rgba(255, 255, 255, 0.1)"
            btn_pressed = "rgba(255, 255, 255, 0.15)"
        elif theme == "Dark":
            bg_color = global_bg if global_bg else "#18181b"
            text_color = text_color if text_color else "#e4e4e7"
            border_color = "#3f3f46"
            btn_hover = "rgba(255, 255, 255, 0.1)"
            btn_pressed = "rgba(255, 255, 255, 0.15)"
        else:  # Light
            bg_color = global_bg if global_bg else "#f4f4f5"
            text_color = text_color if text_color else "#18181b"
            border_color = "#e4e4e7"
            btn_hover = "rgba(0, 0, 0, 0.05)"
            btn_pressed = "rgba(0, 0, 0, 0.1)"
        
        return f"""
            CustomTitleBar {{
                background-color: {bg_color};
                border-bottom: 1px solid {border_color};
            }}
            
            #TitleLabel {{
                color: {text_color};
            }}
            
            /* Minimize/Maximize buttons for dark themes */
            #minimizeButton, #maximizeButton {{
                color: {text_color};
            }}
            #minimizeButton:hover, #maximizeButton:hover {{
                background: {btn_hover};
            }}
            #minimizeButton:pressed, #maximizeButton:pressed {{
                background: {btn_pressed};
            }}
            
            /* Close button - red hover for all themes */
            #closeButton {{
                color: {text_color};
            }}
            #closeButton:hover {{
                background: #c42b1c;
                color: white;
            }}
            #closeButton:pressed {{
                background: #a52313;
                color: white;
            }}
        """
