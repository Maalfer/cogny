from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QFont, QColor
from PySide6.QtCore import QRegularExpression
import pygments
from pygments import lex
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.formatters import HtmlFormatter
from app.ui.themes import ThemeManager

class MarkdownHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlighting_rules = []
        self.active_block = None

        # Headers (# Title)
        header_format = QTextCharFormat()
        header_format.setFontWeight(QFont.Bold)
        header_format.setForeground(QColor("#4A90E2")) 
        self.highlighting_rules.append((QRegularExpression(r"^#+ .+"), header_format))

        # Bold (**text**)
        bold_format = QTextCharFormat()
        bold_format.setFontWeight(QFont.Bold)
        self.highlighting_rules.append((QRegularExpression(r"\*\*.*?\*\*"), bold_format))
        
        # Italic (*text*)
        italic_format = QTextCharFormat()
        italic_format.setFontItalic(True)
        self.highlighting_rules.append((QRegularExpression(r"\*.*?\*"), italic_format))
        
        self.code_format = QTextCharFormat()
        self.code_format.setFontFamilies(["Consolas", "Monospace", "Courier New"])
        self.code_format.setForeground(QColor("#D0D0D0"))
        self.code_format = QTextCharFormat()
        self.code_format.setFontFamilies(["Consolas", "Monospace", "Courier New"])
        self.code_format.setForeground(QColor("#D0D0D0"))
        # Background handled by Editor (Block Format)
        
        # Hidden format for markup characters
        self.hidden_format = QTextCharFormat()
        self.hidden_format.setForeground(QColor("transparent"))
        self.hidden_format.setFontPointSize(0.1) # Collapse width
        self.hidden_format.setFontStretch(0) # Minimal stretch
        
        # Pre-compile regexes for highlightBlock to improve performance
        self.header_pattern_live = QRegularExpression(r"^(#+)\s+(.+)")
        self.bold_pattern_live = QRegularExpression(r"(\*\*)(.*?)(\*\*)")
        self.italic_pattern_live = QRegularExpression(r"(\*)(.*?)(\*)")
        self.link_pattern_live = QRegularExpression(r"(\[)(.*?)(\])(\()(.*?)(\))")
        
        # Dynamic Language Registry
        self.languages = [] 
        # Map: "python" -> index 0 (so state = 2)
        
        self.lexer_cache = {} # Cache for Pygments lexers to avoid repetitive instantiation
        
        self.current_theme = "Light"
        self.syntax_colors = {}
        self.set_theme("Light") # Initial

    def set_theme(self, theme_name):
        self.current_theme = theme_name
        self.syntax_colors = ThemeManager.get_syntax_colors(theme_name)
        self.rehighlight()

    def get_color(self, key):
        return QColor(self.syntax_colors.get(key, self.syntax_colors["default"])) 

    def highlightBlock(self, text):
        # 0. Check if this block is active
        is_active = (self.currentBlock() == self.active_block)

        # Basic Markdown Rules (Headers, Bold, Italic) - Keep Live Preview Hiding
        
        # ... (Header Hiding Logic) ...
        # (I will preserve the header/bold logic but only targeting the code part change to reduce diff size logic if possible, 
        # but replace_file_content replaces range. I'll include the whole method for safety or careful chunks.)
        
        # Re-implementing formatting loop for standard markdown to ensure context is kept
        # Re-implementing formatting loop for standard markdown to ensure context is kept
        header_match = self.header_pattern_live.match(text)
        if header_match.hasMatch():
            hashes = header_match.captured(1)
            level = len(hashes)
            
            header_format = QTextCharFormat()
            header_format.setFontWeight(QFont.Bold)
            
            # Dynamic Sizing & Color
            # Base size typically ~13-14pt.
            if level == 1:
                header_format.setFontPointSize(26) # ~200%
                header_format.setForeground(QColor("#3b82f6")) # Blue-500
            elif level == 2:
                header_format.setFontPointSize(20) # ~150%
                header_format.setForeground(QColor("#60a5fa")) # Blue-400
            elif level == 3:
                header_format.setFontPointSize(16) # ~125%
                header_format.setForeground(QColor("#93c5fd")) # Blue-300
            else:
                header_format.setFontPointSize(14) # Normal-ish but bold
                header_format.setForeground(QColor("#a1a1aa")) # Zinc-400
                
            self.setFormat(0, len(text), header_format)
            if not is_active:
                self.setFormat(header_match.capturedStart(1), header_match.capturedLength(1), self.hidden_format)

        it = self.bold_pattern_live.globalMatch(text)
        while it.hasNext():
            match = it.next()
            fmt = QTextCharFormat()
            fmt.setFontWeight(QFont.Bold)
            self.setFormat(match.capturedStart(), match.capturedLength(), fmt)
            if not is_active:
                self.setFormat(match.capturedStart(1), match.capturedLength(1), self.hidden_format)
                self.setFormat(match.capturedStart(3), match.capturedLength(3), self.hidden_format)
                
        it = self.italic_pattern_live.globalMatch(text)
        while it.hasNext():
            match = it.next()
            fmt = QTextCharFormat()
            fmt.setFontItalic(True)
            self.setFormat(match.capturedStart(), match.capturedLength(), fmt)
            if not is_active:
                self.setFormat(match.capturedStart(1), match.capturedLength(1), self.hidden_format)
                self.setFormat(match.capturedStart(3), match.capturedLength(3), self.hidden_format)


        # Image Links (Standard & WikiLink) - Hide when inactive
        # Standard: ![alt](url)
        img_std_pattern = QRegularExpression(r"!\[.*?\]\((.*?)\)")
        it = img_std_pattern.globalMatch(text)
        while it.hasNext():
            match = it.next()
            # We hide the WHOLE MATCH (including ! and [])
            if not is_active:
                self.setFormat(match.capturedStart(), match.capturedLength(), self.hidden_format)
            else:
                # Optional: Style the link parts differently when active?
                # Gray out the syntax chars, keep url visible?
                # For now just let it be standard text (or use hidden_format logic from others)
                pass

        # WikiLink: ![[image]]
        img_wiki_pattern = QRegularExpression(r"!\[\[(.*?)\]\]")
        it = img_wiki_pattern.globalMatch(text)
        while it.hasNext():
            match = it.next()
            if not is_active:
                self.setFormat(match.capturedStart(), match.capturedLength(), self.hidden_format)

        # Inline Code (`text`)
        # Must be before normal text rules? No, separate regex.
        # User wants: Italic + Emphasis (Color)
        inline_code_pattern = QRegularExpression(r"(`)([^`\n]+)(`)")
        it = inline_code_pattern.globalMatch(text)
        while it.hasNext():
            match = it.next()
            
            # Format Content
            fmt = QTextCharFormat()
            fmt.setFontItalic(True) # Cursiva
            fmt.setFontFamilies(["Consolas", "Monospace", "JetBrains Mono"])
            
            # Use specific colored emphasis
            # We use "string" or "keyword"? We defined "inline_code"
            # We need to fetch it. `self.get_color("inline_code")`
            # Fallback to string color if not found? get_color handles defaults.
            fmt.setForeground(self.get_color("inline_code"))
            # Optional: Start with bold too? "Cierto Enfasis" could mean Bold.
            # User said "Cursiva y con cierto enfasis". Italics IS emphasis. Color is extra.
            
            self.setFormat(match.capturedStart(2), match.capturedLength(2), fmt)
            
            # Hide backticks if not active
            if not is_active:
                self.setFormat(match.capturedStart(1), match.capturedLength(1), self.hidden_format)
                self.setFormat(match.capturedStart(3), match.capturedLength(3), self.hidden_format)
            else:
                # Color the backticks gray
                tick_fmt = QTextCharFormat()
                tick_fmt.setForeground(QColor("gray"))
                self.setFormat(match.capturedStart(1), match.capturedLength(1), tick_fmt)
                self.setFormat(match.capturedStart(3), match.capturedLength(3), tick_fmt)


        # Code Block Logic
        self.setCurrentBlockState(0)

        start_expression = QRegularExpression(r"^```")
        
        previous_state = self.previousBlockState()
        
        # STATE MANAGEMENT:
        # 0 = Markdown Normal
        # 1 = Generic Code Block
        # 100 = End of Block (Transient)
        # N >= 2 = Language specific. Index = N - 2 in self.languages
        
        meta_format = QTextCharFormat()
        meta_format.setForeground(QColor("#808080")) # Gray for delimiters
        meta_format.setFontFamilies(["Consolas", "Monospace", "JetBrains Mono"])
        
        current_state = 0
        
        # If previous was code block (and not end), continue
        if previous_state > 0 and previous_state != 100:
            current_state = previous_state
        
        match = start_expression.match(text)
        if match.hasMatch():
            if previous_state <= 0 or previous_state == 100:
                lang_str = text.strip().replace("```", "").lower().strip()
                
                if not lang_str:
                    current_state = 1
                else:
                    try:
                        if lang_str not in self.languages:
                            self.languages.append(lang_str)
                        current_state = self.languages.index(lang_str) + 2
                    except ValueError:
                         current_state = 1

                # Format the delimiter line
                self.setFormat(0, len(text), meta_format)
                self.setCurrentBlockState(current_state)
                return
        
        if current_state > 0:
            if text.strip() == "```":
                # Ending line
                self.setFormat(0, len(text), meta_format)
                self.setCurrentBlockState(100) # Signal end state
                return
            else:
                # Inside block
                self.setFormat(0, len(text), self.code_format)
                self.highlight_with_pygments(text, current_state)
                self.setCurrentBlockState(current_state)
                return

    def highlight_with_pygments(self, text, state):
        lexer = None
        
        if state == 1:
            # Generic, no highlighting or guess?
            # Creating a guess lexer is expensive per line.
            # Just keep plain color or simple one.
            return
            
        lang_idx = state - 2
        if 0 <= lang_idx < len(self.languages):
            lang_name = self.languages[lang_idx]
            
            # Use Cache
            if lang_name in self.lexer_cache:
                lexer = self.lexer_cache[lang_name]
            else:
                try:
                    lexer = get_lexer_by_name(lang_name, stripall=False)
                    self.lexer_cache[lang_name] = lexer
                except:
                    pass
        
        if not lexer:
            return

        # Token mapping
        tokens = pygments.lex(text, lexer)
        
        index = 0
        from pygments.token import Keyword, Name, Comment, String, Number, Operator
        
        for token, content in tokens:
            length = len(content)
            fmt = QTextCharFormat()
            fmt.setFontFamilies(["Consolas", "Monospace", "JetBrains Mono"])
            # Background is handled by Editor ExtraSelection usually, but we can enforce it?
            # No, text char format background overrides editor background usually.
            # But we want the block background.
            # Let's LEAVE background transparent here so the Editor's block selection shows through.
            # UNLESS we want specific token backgrounds. Only text color for now.
            
            color_key = "default"
            
            if token in Keyword:
                color_key = "keyword"
            elif token in String:
                color_key = "string"
            elif token in Comment:
                color_key = "comment"
            elif token in Name.Function:
                color_key = "function"
            elif token in Name.Class:
                color_key = "class"
            elif token in Number:
                color_key = "number"
            elif token in Operator:
                color_key = "operator"
            elif token in Name.Decorator:
                color_key = "decorator"
            elif token in Name.Builtin.Pseudo:
                color_key = "keyword_pseudo"
            elif token in Name.Builtin:
                color_key = "function" # Treat builtins like echo/print as functions
            elif token in Name.Namespace:
                color_key = "class"
            elif token in Name.Variable:
                color_key = "default" # Or specific variable color if we add one
            
            fmt.setForeground(self.get_color(color_key))
            
            if token in Keyword:
                 fmt.setFontWeight(QFont.Bold)
            
            self.setFormat(index, length, fmt)
            index += length
