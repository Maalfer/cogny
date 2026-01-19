from PySide6.QtGui import QTextDocument, QTextDocumentWriter
from PySide6.QtCore import QUrl
import os

class DocumentExporter:
    """
    Exports content to ODT (Native) and DOCX (via python-docx).
    """
    def __init__(self, file_manager=None):
        self.fm = file_manager

    def export_odt(self, html_content: str, output_path: str, base_url: str = None) -> bool:
        """
        Exports HTML content to ODT using Qt's built-in writer.
        """
        try:
            doc = QTextDocument()
            if base_url:
                doc.setBaseUrl(QUrl.fromLocalFile(base_url))
            
            doc.setHtml(html_content)
            
            writer = QTextDocumentWriter(output_path)
            writer.setFormat(b"ODF")
            return writer.write(doc)
        except Exception as e:
            print(f"Error exporting ODT: {e}")
            return False

    def export_docx(self, content_text: str, output_path: str) -> bool:
        """
        Exports text content to DOCX using python-docx.
        We primarily export text and basic structure. 
        For full HTML->DOCX we would need pandoc, but python-docx gives us native control.
        """
        try:
            from docx import Document
            from docx.shared import Pt
            
            doc = Document()
            
            # Simple Markdown-ish parsing or just dumping text?
            # User wants "Exportar Documento".
            # If we pass raw markdown, it looks bad.
            # If we pass HTML, python-docx doesn't parse HTML natively.
            # Best effort: Split by lines and try to respect headers/paragraphs.
            
            lines = content_text.split('\n')
            
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    continue
                    
                if stripped.startswith('# '):
                    doc.add_heading(stripped[2:], level=1)
                elif stripped.startswith('## '):
                    doc.add_heading(stripped[3:], level=2)
                elif stripped.startswith('### '):
                    doc.add_heading(stripped[4:], level=3)
                else:
                    # Todo: Detect bullets?
                    if stripped.startswith('- ') or stripped.startswith('* '):
                        doc.add_paragraph(stripped[2:], style='List Bullet')
                    else:
                        doc.add_paragraph(stripped)

            doc.save(output_path)
            return True
            
        except ImportError:
            print("python-docx not installed.")
            return False
        except Exception as e:
            print(f"Error exporting DOCX: {e}")
            return False
