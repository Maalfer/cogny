from PySide6.QtGui import QTextDocument, QTextDocumentWriter
from PySide6.QtCore import QUrl
import os
import re

class DocumentExporter:
    """
    Exports content to ODT (Native) and DOCX (via python-docx).
    """
    def __init__(self, file_manager=None):
        self.fm = file_manager

    def export_odt(self, html_content: str, output_path: str, base_url: str = None) -> bool:
        """
        Exports HTML content to ODT using Qt's built-in writer.
        We need to ensure images have absolute paths.
        """
        try:
            # Preprocess HTML to resolve relative paths
            def replace_path(match):
                path = match.group(1)
                if self.fm:
                    resolved = self.fm.resolve_file_path(path)
                    if resolved:
                        # Inject width to prevent overflow and enforce margin adherence
                        # 600px is approximately fitting for A4 with margins (approx 16-17cm printable)
                        return f'src="{resolved}" width="600"'
                return match.group(0)

            # Regex to find src="..." attributes
            # We use a simple regex for efficiency. HTML is likely well-formed from QTextDocument.
            processed_html = re.sub(r'src="([^"]+)"', replace_path, html_content)
            
            doc = QTextDocument()
            if base_url:
                doc.setBaseUrl(QUrl.fromLocalFile(base_url))
            
            doc.setHtml(processed_html)
            
            writer = QTextDocumentWriter(output_path)
            writer.setFormat(b"ODF")
            return writer.write(doc)
        except Exception as e:
            print(f"Error exporting ODT: {e}")
            return False

    def export_docx(self, html_content: str, output_path: str) -> bool:
        """
        Exports HTML content to DOCX using htmldocx.
        """
        try:
            from docx import Document
            from htmldocx import HtmlToDocx

            # Preprocess HTML to resolve relative paths for images
            # htmldocx needs local file paths for images to work correctly.
            def replace_path(match):
                path = match.group(1)
                if self.fm:
                    resolved = self.fm.resolve_file_path(path)
                    if resolved:
                        return f'src="{resolved}"'
                return match.group(0)

            # Resolve paths
            processed_html = re.sub(r'src="([^"]+)"', replace_path, html_content)
            
            # Create a new Document
            doc = Document()
            converter = HtmlToDocx()
            
            # Convert HTML to DOCX
            converter.add_html_to_document(processed_html, doc)
            
            # Save
            doc.save(output_path)
            return True
            
        except ImportError:
            print("htmldocx or python-docx not installed.")
            return False
        except Exception as e:
            print(f"Error exporting DOCX: {e}")
            import traceback
            traceback.print_exc()
            return False
