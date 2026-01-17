import tempfile
import zipfile
import shutil
import os
from app.exporters.pdf_exporter import PDFExporter

class MultiPDFExporter:
    def __init__(self, file_manager):
        self.fm = file_manager
        self.single_exporter = PDFExporter()

    def export_multiple(self, note_list, output_zip_path, theme_name="Light", resolve_image_callback=None):
        """
        Exports multiple notes to PDFs and bundles them into a ZIP file.
        note_list: List of (note_id, title) tuples.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            file_paths = []
            
            for note_id, title in note_list:
                 safe_title = "".join([c for c in title if c.isalpha() or c.isdigit() or c in (' ', '.', '-', '_')]).strip()
                 if not safe_title: safe_title = f"Nota_{os.path.basename(note_id)}"
                 
                 pdf_filename = f"{safe_title}.pdf"
                 pdf_path = os.path.join(temp_dir, pdf_filename)
                 
                 counter = 1
                 while os.path.exists(pdf_path):
                     pdf_path = os.path.join(temp_dir, f"{safe_title}_{counter}.pdf")
                     counter += 1
                 
                 # Fetch Content using FileManager
                 content = self.fm.read_note(note_id)
                 if content:
                     try:
                         # Use provided callback or default to FM resolution
                         resolver = resolve_image_callback
                         if not resolver:
                             resolver = lambda src: self.fm.get_abs_path(src) if src else None

                         self.single_exporter.export_to_pdf(
                             title, 
                             content, 
                             pdf_path, 
                             theme_name,
                             resolve_image_callback=resolver
                         )
                         file_paths.append(pdf_path)
                     except Exception as e:
                         print(f"Error exporting PDF for note {note_id}: {e}")
            
            if file_paths:
                with zipfile.ZipFile(output_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for file_path in file_paths:
                        zipf.write(file_path, arcname=os.path.basename(file_path))
                return True
            else:
                return False

