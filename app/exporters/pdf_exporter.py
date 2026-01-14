from PySide6.QtGui import QTextDocument, QPageSize, QPageLayout, QPdfWriter, QImage, QAbstractTextDocumentLayout
from PySide6.QtCore import QSizeF, QMarginsF, QUrl
from app.database.manager import DatabaseManager
from app.ui.themes import ThemeManager
import re
import html
import uuid

# Pygments imports
from pygments import highlight
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.formatters import HtmlFormatter

class PDFExporter:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def export_to_pdf(self, title: str, content: str, output_path: str, theme_name: str = "Light"):
        """
        Exports the content to PDF using specialized HTML rendering.
        Matches the editor's look and feel including syntax highlighting.
        """
        
        # 1. Render Markdown to HTML with Highlighting & Protection
        html_content = self.render_markdown(content, theme_name)
        
        # 2. Setup Document
        doc = QTextDocument()
        
        # 3. Add Styles
        self._apply_styles(doc, theme_name)
        
        # 4. Load Images
        self._load_images(doc, html_content)
        
        # 5. Construct Full HTML
        # We assume light/dark background is handled by body style in _apply_styles
        full_html = f"""
        <html>
        <head>
            <title>{title}</title>
        </head>
        <body>
            <h1 class="doc-title">{title}</h1>
            {html_content}
        </body>
        </html>
        """
        
        doc.setHtml(full_html)
        
        # 6. Setup PDF Writer
        writer = QPdfWriter(output_path)
        writer.setPageSize(QPageSize(QPageSize.A4))
        writer.setResolution(300) 
        writer.setCreator("Cogni App")
        
        margins = QMarginsF(20, 20, 20, 20)
        layout = QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Portrait, margins)
        writer.setPageLayout(layout)
        
        # 7. Print
        doc.print_(writer)
        
    def _apply_styles(self, doc: QTextDocument, theme_name: str):
        """Applies CSS consistent with the chosen theme."""
        # Get Editor Styles
        # Note: We might need to adjust some pixel values for PDF resolution (300DPI) 
        # but pure CSS often scales with font-size.
        
        # Get base colors from ThemeManager
        # We can't access instance of Main Window, so we rely on static methods or passed theme.
        
        # Construct CSS
        # We need generic body styles + pygments styles + specific element styles
        
        # 1. Base Editor Style
        base_style = ThemeManager.get_editor_style(theme_name)
        
        # Adjust generic styles for PDF context (Body selector for Qt)
        # Qt's QTextDocument supports a subset of CSS.
        # NoteEditor selector in get_editor_style won't match "body".
        # We need to map NoteEditor styles to body.
        
        # Extract bg color and color from base_style to apply to body
        # Simple parsing or explicit reconstruction
        is_dark = (theme_name == "Dark")
        bg_color = "#1e1e1e" if is_dark else "#FAFAFA"
        text_color = "#d4d4d4" if is_dark else "#202020"
        
        # 2. Pygments CSS
        # Generated dynamic CSS based on the theme colors defined in ThemeManager
        pygments_style = self._generate_pygments_css(theme_name)
        
        css = f"""
            body {{ font-family: "Segoe UI", sans-serif; font-size: 14pt; color: {text_color}; background-color: {bg_color}; line-height: 1.6; }}
            h1.doc-title {{ font-size: 24pt; font-weight: bold; color: {text_color}; margin-bottom: 25px; text-align: center; border-bottom: 2px solid #777; padding-bottom: 10px; }}
            
            /* Tables */
            table {{ border-collapse: collapse; width: 100%; margin: 15px 0; border: 1px solid #777; }}
            th, td {{ border: 1px solid #777; padding: 8px; text-align: left; }}
            th {{ background-color: {'#2D2D2D' if is_dark else '#EFEFEF'}; font-weight: bold; }}
            
            img {{ max-width: 100%; height: auto; margin: 15px 0; border-radius: 8px; }}
            
            hr {{ border: none; background-color: #777; height: 1px; margin: 20px 0; }}
            
            /* Code Blocks */
            pre {{ background-color: {'#2d2d2d' if is_dark else '#EEF1F4'}; padding: 15px; border-radius: 8px; font-family: "Consolas", monospace; font-size: 12pt; white-space: pre-wrap; }}
            
            {pygments_style}
        """
        doc.setDefaultStyleSheet(css)

    def _generate_pygments_css(self, theme_name: str) -> str:
        """Generates CSS for syntax highlighting based on app theme."""
        colors = ThemeManager.get_syntax_colors(theme_name)
        
        # We map our custom keys to Pygments classes
        # .k = Keyword, .s = String, .c = Comment, etc.
        # This is manual mapping to ensure exact match with Editor
        
        return f"""
            .k {{ color: {colors['keyword']}; font-weight: bold; }} /* Keyword */
            .kp {{ color: {colors['keyword_pseudo']}; }} /* Keyword.Pseudo */
            .s {{ color: {colors['string']}; }} /* String */
            .s1 {{ color: {colors['string']}; }} /* String.Double */
            .s2 {{ color: {colors['string']}; }} /* String.Single */
            .c {{ color: {colors['comment']}; font-style: italic; }} /* Comment */
            .c1 {{ color: {colors['comment']}; font-style: italic; }} /* Comment.Single */
            .nf {{ color: {colors['function']}; }} /* Name.Function */
            .nc {{ color: {colors['class']}; font-weight: bold; }} /* Name.Class */
            .m {{ color: {colors['number']}; }} /* Number */
            .mi {{ color: {colors['number']}; }} /* Number.Integer */
            .mf {{ color: {colors['number']}; }} /* Number.Float */
            .o {{ color: {colors['operator']}; }} /* Operator */
            .nd {{ color: {colors['decorator']}; }} /* Name.Decorator */
        """

    def render_markdown(self, text: str, theme_name: str) -> str:
        """
        Custom renderer that handles:
        1. Code Blocks -> Pygments HTML
        2. Internal patterns -> Placeholders -> Restoration
        3. Basic Markdown -> HTML
        """
        
        # 1. Protect Internal HTML (Images & Attachments)
        placeholders = {}
        
        def preserve_match(match):
            token = f"__INTERNAL_HTML_PLACEHOLDER_{uuid.uuid4().hex}__"
            placeholders[token] = match.group(0)
            return token
            
        # Protect Images
        text = re.sub(r'<img src="image://db/\d+"\s*/>', preserve_match, text)
        # Protect Attachments (Anchor + Icon Span)
        text = re.sub(r'<a href="attachment://\d+".*?>.*?</a>', preserve_match, text)
        text = re.sub(r'<span[^>]*>📎</span>', preserve_match, text)
        text = re.sub(r'&nbsp;', preserve_match, text) # Preserve spacing around attachments

        # 2. Process Code Blocks
        parts = re.split(r'(```[\s\S]*?```)', text)
        processed_parts = []
        
        # Setup Formatter
        # We use explicit CSS classes (no inline styles) so we can control them via stylesheet
        formatter = HtmlFormatter(nowrap=True, classprefix="") 
        
        for part in parts:
            if part.startswith("```") and part.endswith("```"):
                # Extract language and code
                # Format: ```lang\ncode\n```
                lines = part.strip().split('\n')
                if len(lines) >= 2:
                    lang = lines[0].strip('`').strip()
                    code = '\n'.join(lines[1:-1])
                    
                    try:
                        lexer = get_lexer_by_name(lang)
                    except:
                        lexer = guess_lexer(code)
                        
                    highlighted = highlight(code, lexer, formatter)
                    
                    # Wrap in pre for block styling
                    processed_parts.append(f'<pre>{highlighted}</pre>')
                else:
                    # Empty or malformed
                    processed_parts.append(html.escape(part))
            else:
                # Normal Text
                # We need to handle TABLES and basic formatting
                
                # Protect placeholders in this chunk from html.escape?
                # Actually placeholders are safe UUIDs.
                
                # Render Tables
                part = self._render_tables(part)
                
                # We do NOT html.escape the whole part because _render_tables returns HTML
                # But non-table text needs escaping? 
                # _render_tables escapes cell content. 
                # What about text OUTSIDE tables?
                # My _render_tables logic splits lines and protects non-table lines?
                # Let's verify _render_tables implementation below.
                
                processed_parts.append(part)
                
        content = "".join(processed_parts)
        
        # 3. Horizontal Rules
        content = re.sub(r'(?m)^[-*_]{3,}\s*$', '<hr>', content)
        
        # 4. Paragraphs / Line Breaks
        # Simple nl2br for text that isn't html tags?
        # Creating valid HTML paragraphs is hard without proper parser.
        # But QTextDocument handles newlines reasonably well if using pre-wrap?
        # Or we replace \n with <br>.
        # CAUTION: We don't want to break HTML we just generated (tables, pre).
        # Since we are constructing a hybrid HTML doc, we should be careful.
        # Ideally, we used `white-space: pre-wrap` on body, avoiding <br> hell.
        # Let's try relying on CSS `white-space: pre-wrap` in body, but <img> tags are block or inline?
        # If we wrap everything in <pre> it breaks images.
        # Let's replace \n with <br> ONLY in text segments? Too complex.
        # Let's trust QTextDocument to handle newlines as line breaks if we don't strictly enforce paragraphs.
        # Actually standard behavior: HTML ignores newlines.
        # We should replace \n with <br> in the "text" parts of _render_tables.
        
        # 5. Restore Placeholders
        for token, original in placeholders.items():
            content = content.replace(token, original)
            
        return content

    def _render_tables(self, text: str) -> str:
        """Parses markdown tables and returns HTML, escaping other text."""
        lines = text.split('\n')
        in_table = False
        table_lines = []
        final_output = []
        
        for line in lines:
            stripped = line.strip()
            # Basic table detection
            if stripped.startswith('|') and (stripped.endswith('|') or len(stripped.split('|')) > 1):
                in_table = True
                table_lines.append(line)
            else:
                if in_table:
                    final_output.append(self._lines_to_html_table(table_lines))
                    table_lines = []
                    in_table = False
                
                # Regular line: Escape and add BR
                # But if it's customized HTML (hr, pre) we shouldn't escape?
                # We haven't added hr/pre yet in this chunk.
                # Placeholders are safe.
                escaped_line = html.escape(line)
                final_output.append(escaped_line + "<br>")
                
        if in_table:
            final_output.append(self._lines_to_html_table(table_lines))
            
        return "\n".join(final_output)

    def _lines_to_html_table(self, lines: list) -> str:
        if len(lines) < 2:
            return "<br>".join([html.escape(l) for l in lines]) + "<br>"
            
        html_out = ['<table border="1" cellspacing="0" cellpadding="5">']
        
        header_row = lines[0].strip().strip('|').split('|')
        html_out.append("<thead><tr>")
        for h in header_row:
             html_out.append(f"<th>{html.escape(h.strip())}</th>")
        html_out.append("</tr></thead>")
        
        html_out.append("<tbody>")
        
        start_idx = 1
        if len(lines) > 1 and '---' in lines[1]:
            start_idx = 2
            
        for i in range(start_idx, len(lines)):
            row = lines[i].strip().strip('|').split('|')
            html_out.append("<tr>")
            for cell in row:
                html_out.append(f"<td>{html.escape(cell.strip())}</td>")
            html_out.append("</tr>")
            
        html_out.append("</tbody></table>")
        return "".join(html_out)

    def _load_images(self, doc: QTextDocument, content: str):
        """
        Finds all image://db/{id} patterns and loads them into the document's resource cache.
        """
        refs = re.findall(r'image://db/(\d+)', content)
        unique_ids = set(refs)
        
        for img_id_str in unique_ids:
            try:
                img_id = int(img_id_str)
                blob = self.db.get_image(img_id)
                if blob:
                    image = QImage()
                    if image.loadFromData(blob):
                        url = QUrl(f"image://db/{img_id}")
                        doc.addResource(QTextDocument.ImageResource, url, image)
            except Exception as e:
                print(f"Failed to load image resource {img_id}: {e}")

