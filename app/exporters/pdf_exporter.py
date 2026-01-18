from app.ui.themes import ThemeManager
from app.ui.markdown_renderer import MarkdownRenderer
from weasyprint import HTML, CSS, default_url_fetcher
import os

class PDFExporter:
    def __init__(self):
        pass

    def export_to_pdf(self, title: str, content: str, output_path: str, theme_name: str = "Light", resolve_image_callback=None, base_url: str = "."):
        """
        Exports the content to PDF using WeasyPrint for high-quality rendering.
        resolve_image_callback: function(src) -> absolute_path
        base_url: Root path of the vault for resolving relative links
        """
        
        # 1. Render HTML
        body_html = MarkdownRenderer.process_markdown_content(content)
        
        # 2. Prepare CSS
        # Base Editor Styles
        base_css = ThemeManager.get_editor_style(theme_name)
        
        # Theme Colors
        is_dark = (theme_name == "Dark")
        bg_color = "#1e1e1e" if is_dark else "#FAFAFA"
        text_color = "#d4d4d4" if is_dark else "#202020"
        border_color = "#454545" if is_dark else "#C0C0C0"
        
        # PDF Specific CSS
        pdf_css = f"""
        @page {{
            size: A4;
            margin: 2.5cm;
            @bottom-center {{
                content: "Página " counter(page) " de " counter(pages);
                font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                font-size: 9pt;
                color: {text_color};
            }}
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            font-size: 11pt;
            line-height: 1.6;
            color: {text_color};
            background-color: {bg_color};
            margin: 0;
            padding: 0;
        }}
        
        h1.doc-title {{
            font-size: 24pt;
            font-weight: bold;
            text-align: center;
            margin-bottom: 2em;
            padding-bottom: 0.5em;
            border-bottom: 2px solid {border_color};
        }}

        h1, h2, h3, h4, h5, h6 {{ 
            break-after: avoid; 
            margin-top: 1.5em;
        }}
        pre, blockquote, table, img, figure {{ 
            break-inside: avoid; 
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 1em;
        }}
        th, td {{
            border: 1px solid {border_color};
            padding: 8px;
        }}
        
        pre {{
            padding: 10px;
            border-radius: 5px;
            white-space: pre-wrap; 
            font-size: 10pt;
            border: 1px solid {border_color};
        }}
        
        img {{
            max-width: 100%;
            height: auto;
            border-radius: 8px;
        }}
        """
        
        full_css_str = base_css + "\n" + pdf_css
        
        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{title}</title>
            <meta charset="utf-8">
        </head>
        <body class="NoteEditor">
            <h1 class="doc-title">{title}</h1>
            {body_html}
        </body>
        </html>
        """
        
        # Custom Fetcher Wrapper
        def custom_fetcher(url):
            return self._fs_url_fetcher(url, resolve_image_callback)
        
        html_obj = HTML(string=full_html, base_url=base_url, url_fetcher=custom_fetcher)
        css_obj = CSS(string=full_css_str)
        
        html_obj.write_pdf(
            output_path, 
            stylesheets=[css_obj]
        )

    def _fs_url_fetcher(self, url, resolve_callback):
        """
        Url fetcher that resolves local images using the callback.
        """
    def _fs_url_fetcher(self, url, resolve_callback):
        """
        Url fetcher that resolves local images using the callback.
        """
        try:
            from urllib.parse import unquote
            
            # Prepare a clean path if it's a file URL or looks like one
            path_to_check = url
            if url.startswith("file://"):
                path_to_check = url[7:]
            
            # Always unquote (WeasyPrint might encode spaces)
            path_to_check = unquote(path_to_check)
            
            # 1. Direct Check (Absolute or relative if CWD matches)
            if os.path.exists(path_to_check):
                 return default_url_fetcher(url)
            
            # 2. Fallback to callback (Smart Search)
            if resolve_callback:
                 # Pass the CLEANED path, not the raw URL
                 resolved = resolve_callback(path_to_check)
                 if resolved and os.path.exists(resolved):
                     from weasyprint.urls import path2url
                     return default_url_fetcher(path2url(resolved))
            
            # 3. Last resort
            return default_url_fetcher(url)
             
        except Exception as e:
            print(f"Fetcher Error: {e}")
            raise e


