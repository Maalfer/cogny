
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
        
        # 0. Pre-process: Unescape characters commonly escaped by Qt's toMarkdown
        # This fixes issues where code blocks (\```) and images (!\[) rendering as literal text.
        text = text.replace(r'\```', '```')
        text = text.replace(r'!\[', '![')
        text = text.replace(r'\]', ']')

        # 0.1 Convert Obsidian/WikiLinks ![[image.png|options]] -> ![image.png](image.png)
        # Simple regex to catch ![[filename|...]] or ![[filename]]
        # We assume the user wants to display them.
        def wikilink_sub(match):
            content = match.group(1)
            if '|' in content:
                filename = content.split('|')[0]
            else:
                filename = content
            return f"![{filename}]({filename})"
        
        text = re.sub(r'!\[\[(.*?)\]\]', wikilink_sub, text)
        
        # 1. Protect Internal HTML (Attachments Only - Images handled by Extension)
        placeholders = {}
        
        def preserve_match(match):
            token = f"HTML-PLACEHOLDER-{uuid.uuid4().hex}-END"
            placeholders[token] = match.group(0)
            return token
            
        # Regex for Attachment
        text = re.sub(r'<a href="attachment://\d+".*?>.*?</a>', preserve_match, text)
        text = re.sub(r'<span[^>]*>📎</span>', preserve_match, text)
        text = re.sub(r'&nbsp;', preserve_match, text)
        
        # 2. Convert Markdown to HTML
        try:
            from app.ui.blueprints.custom_markdown import CognyInternalExtension
            
            html_content = markdown.markdown(
                text, 
                extensions=[
                    'extra', 
                    'nl2br', 
                    'sane_lists', 
                    'codehilite',
                    CognyInternalExtension()
                ],
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
            html_content = html_content.replace(token, original)
            
        return html_content


