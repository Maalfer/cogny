from app.database.manager import DatabaseManager
from app.ui.themes import ThemeManager
from app.ui.blueprints.markdown import MarkdownRenderer
from weasyprint import HTML, CSS, default_url_fetcher
import re

class PDFExporter:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def export_to_pdf(self, title: str, content: str, output_path: str, theme_name: str = "Light"):
        """
        Exports the content to PDF using WeasyPrint for high-quality rendering.
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
        
        # PDF Specific CSS (Pagination, @page, Resets)
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
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol";
            font-size: 11pt;
            line-height: 1.6;
            color: {text_color};
            background-color: {bg_color};
            margin: 0;
            padding: 0;
        }}
        
        /* Document Title */
        h1.doc-title {{
            font-size: 24pt;
            font-weight: bold;
            text-align: center;
            margin-bottom: 2em;
            padding-bottom: 0.5em;
            border-bottom: 2px solid {border_color};
        }}

        /* Smart Page Breaks */
        h1, h2, h3, h4, h5, h6 {{ 
            break-after: avoid; 
            margin-top: 1.5em;
        }}
        pre, blockquote, table, img, figure {{ 
            break-inside: avoid; 
        }}
        
        /* Table Tweaks for PDF */
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 1em;
        }}
        th, td {{
            border: 1px solid {border_color};
            padding: 8px;
        }}
        
        /* Pre/Code Tweaks */
        pre {{
            padding: 10px;
            border-radius: 5px;
            white-space: pre-wrap; /* Wrap long lines in PDF */
            font-size: 10pt;
            border: 1px solid {border_color};
        }}
        
        /* Images */
        img {{
            max-width: 100%;
            height: auto;
            border-radius: 8px;
        }}
        """
        
        # Combine CSS
        full_css_str = base_css + "\n" + pdf_css
        
        # 3. Full HTML Document
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
        
        # 4. Generate PDF with Custom Fetcher for DB Images
        html_obj = HTML(string=full_html, base_url=".", url_fetcher=self._db_url_fetcher)
        css_obj = CSS(string=full_css_str)
        
        html_obj.write_pdf(
            output_path, 
            stylesheets=[css_obj]
        )

    def _db_url_fetcher(self, url, timeout=10, ssl_context=None):
        """
        Custom URL fetcher to intercept image://db/{id} requests and return data from SQLite.
        Delegates other schemes to default_url_fetcher.
        """
        if url.startswith("image://db/"):
            try:
                # Extract ID
                # url format: image://db/123
                img_id = url.split("image://db/")[-1]
                if not img_id.isdigit():
                    raise ValueError("Invalid Image ID")
                    
                img_id = int(img_id)
                blob = self.db.get_image(img_id)
                
                if blob:
                    # Detect mime type? 
                    # We usually store raw bytes. We detect header or assume png/jpg.
                    # Simple heuristic:
                    mime = 'image/png'
                    if blob.startswith(b'\xff\xd8'): mime = 'image/jpeg'
                    elif blob.startswith(b'GIF'): mime = 'image/gif'
                    elif blob.startswith(b'<svg'): mime = 'image/svg+xml'
                    
                    return {
                        'string': blob,
                        'mime_type': mime,
                        'encoding': None,
                        'redirected_url': None
                    }
                else:
                     raise FileNotFoundError(f"Image {img_id} not found in DB")
                     
            except Exception as e:
                print(f"WeasyPrint Fetcher Error: {e}")
                # Return empty or placeholder?
                # Raise to let WeasyPrint handle (it shows broken image icon)
                raise e
        
        # Fallback for http, file, attachment://...
        # attachment:// is internal too but usually just a link, not loaded resource.
        # MarkdownRenderer protects attachments as <a> links, so WeasyPrint won't fetch them unless <link/img>.
        return default_url_fetcher(url, timeout, ssl_context)


