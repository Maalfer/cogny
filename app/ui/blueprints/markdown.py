
class MarkdownRenderer:
    @staticmethod
    def process_markdown_content(text):
        """
        Full Markdown Rendering using `markdown` library.
        - Preserves Internal Images/Attachments via placeholders.
        - Supports Tables, Code Blocks, standard formatting.
        """
        import markdown
        import re
        import uuid
        import sys
        
        # Increase recursion limit for deep nested structures (e.g. lists)
        sys.setrecursionlimit(3000)
        
        # 1. Protect Internal HTML (Images & Attachments)
        placeholders = {}
        
        def preserve_match(match):
            # Use a token that won't trigger Markdown formatting (no underscores/asterisks)
            token = f"HTML-PLACEHOLDER-{uuid.uuid4().hex}-END"
            placeholders[token] = match.group(0)
            return token
            
        # Regex for Image
        text = re.sub(r'<img src="image://db/\d+"\s*/>', preserve_match, text)
        
        # Regex for Attachment
        text = re.sub(r'<a href="attachment://\d+".*?>.*?</a>', preserve_match, text)
        text = re.sub(r'<span[^>]*>📎</span>', preserve_match, text)
        text = re.sub(r'&nbsp;', preserve_match, text)
        
        # 2. Convert Markdown to HTML
        # Extensions: 
        # - extra: tables, fenced_code, footnotes, attr_list, def_list, abbr
        # - nl2br: newlines become <br> (optional, mostly desired for notes)
        # - sane_lists: better list handling
        try:
            html_content = markdown.markdown(
                text, 
                extensions=['extra', 'nl2br', 'sane_lists', 'codehilite'],
                extension_configs={
                    'codehilite': {
                        'noclasses': True,
                        'pygments_style': 'default'
                    }
                }
            )
        except Exception as e:
            print(f"Markdown Error: {e}")
            html_content = text # Fallback
        
        # 3. Restore Placeholders
        for token, original in placeholders.items():
            # Apply Image Wrapping (User Request)
            if original.startswith('<img'):
                 replacement = f'<div style="margin: 10px 0;">{original}</div>'
            else:
                 replacement = original
                 
            html_content = html_content.replace(token, replacement)
            
        return html_content


