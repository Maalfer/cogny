from app.database.manager import DatabaseManager
from app.exporters.pdf_exporter import PDFExporter
import tempfile
import zipfile
import shutil
import os

class MultiPDFExporter:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.single_exporter = PDFExporter(db_manager)

    def export_multiple(self, note_list, output_zip_path, theme_name="Light"):
        """
        Exports multiple notes to PDFs and bundles them into a ZIP file.
        
        Args:
            note_list: List of (note_id, title) tuples.
            output_zip_path: Destination path for the .zip file.
            theme_name: Theme to use for PDF generation (default Light).
        """
        # Create a temporary directory to generate PDFs
        with tempfile.TemporaryDirectory() as temp_dir:
            file_paths = []
            
            for note_id, title in note_list:
                 # Sanitize filename
                 safe_title = "".join([c for c in title if c.isalpha() or c.isdigit() or c in (' ', '.', '-', '_')]).strip()
                 if not safe_title: safe_title = f"Nota_{note_id}"
                 
                 pdf_filename = f"{safe_title}.pdf"
                 pdf_path = os.path.join(temp_dir, pdf_filename)
                 
                 # Handle duplicates names
                 counter = 1
                 while os.path.exists(pdf_path):
                     pdf_path = os.path.join(temp_dir, f"{safe_title}_{counter}.pdf")
                     counter += 1
                 
                 # Fetch Content
                 note_data = self.db.get_note(note_id)
                 if note_data:
                     # Generate PDF using existing logic
                     # Uses WeasyPrint, ThemeManager, Database Images
                     try:
                         self.single_exporter.export_to_pdf(
                             note_data['title'], 
                             note_data['content'], 
                             pdf_path, 
                             theme_name
                         )
                         file_paths.append(pdf_path)
                     except Exception as e:
                         print(f"Error exporting PDF for note {note_id}: {e}")
            
            # Create ZIP
            if file_paths:
                with zipfile.ZipFile(output_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for file_path in file_paths:
                        zipf.write(file_path, arcname=os.path.basename(file_path))
                return True
            else:
                return False
