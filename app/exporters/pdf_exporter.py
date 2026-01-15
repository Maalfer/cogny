from PySide6.QtGui import QTextDocument, QPageSize, QPageLayout, QPdfWriter, QImage, QAbstractTextDocumentLayout
from PySide6.QtCore import QSizeF, QMarginsF, QUrl
from app.database.manager import DatabaseManager
from app.ui.themes import ThemeManager
from app.ui.blueprints.markdown import MarkdownRenderer
import re
import html

class PDFExporter:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def export_to_pdf(self, title: str, content: str, output_path: str, theme_name: str = "Light"):
        """
        Exports the content to PDF using specialized HTML rendering.
        Matches the editor's look and feel including syntax highlighting.
        """
        
        # 1. Render Markdown to HTML using the Unified Renderer
        # This ensures tables, code blocks (with inline styles), and internal images 
        # are processed exactly as they appear in the editor.
        html_content = MarkdownRenderer.process_markdown_content(content)
        
        # 2. Setup Document
        doc = QTextDocument()
        
        # 3. Add Styles
        self._apply_styles(doc, theme_name)
        
        # 4. Load Images
        self._load_images(doc, html_content)
        
        # 5. Construct Full HTML
        # We wrap content in a div that matches the Editor's class to apply scoped styles if any,
        # but mostly we rely on global styles from ThemeManager.
        full_html = f"""
        <html>
        <head>
            <title>{title}</title>
        </head>
        <body class="NoteEditor">
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
        
        # Standard professional margins (20mm ~ 0.8 inch)
        margins = QMarginsF(20, 20, 20, 20)
        layout = QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Portrait, margins)
        writer.setPageLayout(layout)
        
        # 7. Print
        doc.print_(writer)
        
    def _apply_styles(self, doc: QTextDocument, theme_name: str):
        """Applies CSS consistent with the chosen theme."""
        # 1. Get Base CSS from ThemeManager
        # This includes h1-h6, table, pre, code, blockquote, img
        base_css = ThemeManager.get_editor_style(theme_name)
        
        # 2. Augment for PDF Specifics
        # - Font adjustments for Print (Points instead of Pixels?) 
        #   (Qt usually treats px as points in print context or depends on resolution, 
        #    but explicit pt is safer for text).
        # - We replace pixels with points or trust the scaling.
        # - We add specific Body styling.
        
        is_dark = (theme_name == "Dark")
        bg_color = "#1e1e1e" if is_dark else "#FAFAFA"
        text_color = "#d4d4d4" if is_dark else "#202020"
        
        pdf_overrides = f"""
            body {{ 
                font-family: "Segoe UI", sans-serif; 
                font-size: 14pt; 
                color: {text_color}; 
                background-color: {bg_color}; 
                line-height: 1.5;
            }}
            .doc-title {{ 
                font-size: 24pt; 
                font-weight: bold; 
                color: {text_color}; 
                margin-bottom: 30px; 
                text-align: center; 
                border-bottom: 2px solid {'#454545' if is_dark else '#C0C0C0'}; 
                padding-bottom: 15px; 
            }}
            /* Ensure Tables use Full Width in PDF */
            table {{ width: 100%; margin-bottom: 20px; }}
            
            /* Clean up code blocks for Print */
            pre {{ 
                font-size: 10pt; 
                padding: 10px; 
                background-color: {'#2d2d2d' if is_dark else '#F0F0F0'};
                white-space: pre-wrap;
            }}
            
            /* Adjust Images */
            img {{ max-width: 100%; }}
        """
        
        # Combine
        full_css = base_css + "\n" + pdf_overrides
        doc.setDefaultStyleSheet(full_css)

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


