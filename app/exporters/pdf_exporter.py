from PySide6.QtGui import QTextDocument, QPageSize, QPageLayout, QPdfWriter, QImage, QAbstractTextDocumentLayout
from PySide6.QtCore import QSizeF, QMarginsF, QUrl
from app.database.manager import DatabaseManager
import re

class PDFExporter:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def export_to_pdf(self, title: str, html_content: str, output_path: str):
        """
        Exports the content to PDF using HTML rendering (WYSIWYG).
        Preserves the internal application look (Tables rendered, Text escaped).
        """
        
        # 1. Setup Document
        doc = QTextDocument()
        
        # 2. Add Styles
        self._apply_styles(doc)
        
        # 3. Load Images
        # We scan the HTML for image://db/ patterns and load them as resources
        self._load_images(doc, html_content)
        
        # 4. Construct Full HTML
        # We need to ensure the HTML structure is valid
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
        
        # 5. Setup PDF Writer
        writer = QPdfWriter(output_path)
        writer.setPageSize(QPageSize(QPageSize.A4))
        writer.setResolution(300) 
        writer.setCreator("Cogni App")
        
        margins = QMarginsF(20, 20, 20, 20)
        layout = QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Portrait, margins)
        writer.setPageLayout(layout)
        
        # 6. Print
        doc.print_(writer)
        
    def _apply_styles(self, doc: QTextDocument):
        """Applies CSS consistent with the Editor theme."""
        # Using a clean generic style that matches the editor's Hybrid feel
        css = """
            body { font-family: "Segoe UI", sans-serif; font-size: 14px; color: #202020; line-height: 1.6; }
            h1.doc-title { font-size: 24px; font-weight: bold; color: #2c3e50; margin-bottom: 25px; text-align: center; border-bottom: 2px solid #eee; padding-bottom: 10px; }
            
            /* Tables: We want them to look like the editor's tables */
            table { border-collapse: collapse; width: 100%; margin: 15px 0; }
            th, td { border: 1px solid #C0C0C0; padding: 8px; text-align: left; }
            th { background-color: #EFEFEF; font-weight: bold; }
            
            img { max-width: 100%; height: auto; margin: 15px 0; border-radius: 8px; }
            
            /* Code blocks (which are escaped text in Hybrid view) */
            /* We can't easily style them unless wrapped in <pre> or similar, 
               but process_markdown_content wraps escaped code in... nothing/escaped text? 
               Wait, process_markdown_content escapes code blocks. They appear as text. 
               We might simply rely on body font. */
        """
        doc.setDefaultStyleSheet(css)

    def _load_images(self, doc: QTextDocument, content: str):
        """
        Finds all image://db/{id} patterns and loads them into the document's resource cache.
        """
        # Pattern: image://db/(\d+)
        refs = re.findall(r'image://db/(\d+)', content)
        # Use set to avoid duplicates
        unique_ids = set(refs)
        
        for img_id_str in unique_ids:
            try:
                img_id = int(img_id_str)
                blob = self.db.get_image(img_id)
                if blob:
                    image = QImage()
                    if image.loadFromData(blob):
                        # Add to document resources
                        url = QUrl(f"image://db/{img_id}")
                        doc.addResource(QTextDocument.ImageResource, url, image)
            except Exception as e:
                print(f"Failed to load image resource {img_id}: {e}")
