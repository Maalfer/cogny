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

    def export_docx(self, content_text: str, output_path: str) -> bool:
        """
        Exports text content to DOCX using python-docx.
        We primarily export text and basic structure. 
        For full HTML->DOCX we would need pandoc, but python-docx gives us native control.
        """
        try:
            from docx import Document
            from docx.shared import Pt, Inches
            from docx.enum.text import WD_ALIGN_PARAGRAPH
            
            doc = Document()
            
            lines = content_text.split('\n')
            
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    continue
                    
                # Check for headers
                if stripped.startswith('# '):
                    doc.add_heading(stripped[2:], level=1)
                elif stripped.startswith('## '):
                    doc.add_heading(stripped[3:], level=2)
                elif stripped.startswith('### '):
                    doc.add_heading(stripped[4:], level=3)
                    
        # Check for images: ![Alt](path)
                elif stripped.startswith('![') and '](' in stripped and stripped.endswith(')'):
                    try:
                        # Extract path
                        # Regex for ![alt](path)
                        match = re.search(r'!\[(.*?)\]\((.*?)\)', stripped)
                        if match:
                            image_path = match.group(2)
                            resolved_path = None
                            if self.fm:
                                resolved_path = self.fm.resolve_file_path(image_path)
                            
                            if resolved_path and os.path.exists(resolved_path):
                                # Calculate available width
                                section = doc.sections[0]
                                available_width = section.page_width - section.left_margin - section.right_margin
                                
                                # Add picture without defining width first to get native size
                                picture = doc.add_picture(resolved_path)
                                
                                # Resize if too large
                                if picture.width > available_width:
                                    picture.width = available_width
                                    
                                # Center the image
                                last_paragraph = doc.paragraphs[-1]
                                last_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                            else:
                                # Fallback: Add as text if image not found
                                doc.add_paragraph(f"[Imagen no encontrada: {image_path}]")
                        else:
                             doc.add_paragraph(stripped)
                    except Exception as img_err:
                        print(f"Error inserting image in DOCX: {img_err}")
                        doc.add_paragraph(stripped)

                # Check for Obsidian-style images: ![[image]]
                elif stripped.startswith('![[') and stripped.endswith(']]'):
                    try:
                        match = re.search(r'!\[\[(.*?)\]\]', stripped)
                        if match:
                            content = match.group(1)
                            # Handle piping for size/alt: [[image.png|100]] or [[image.png|alt]]
                            image_path = content.split('|')[0]
                            
                            resolved_path = None
                            if self.fm:
                                resolved_path = self.fm.resolve_file_path(image_path)
                                
                            if resolved_path and os.path.exists(resolved_path):
                                # Calculate available width
                                section = doc.sections[0]
                                available_width = section.page_width - section.left_margin - section.right_margin
                                
                                picture = doc.add_picture(resolved_path)
                                
                                if picture.width > available_width:
                                    picture.width = available_width
                                    
                                last_paragraph = doc.paragraphs[-1]
                                last_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                            else:
                                doc.add_paragraph(f"[Imagen no encontrada: {image_path}]")
                        else:
                            doc.add_paragraph(stripped)
                    except Exception as img_err:
                        print(f"Error inserting wiki-image in DOCX: {img_err}")
                        doc.add_paragraph(stripped)
                        
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
