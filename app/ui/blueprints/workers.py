from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QApplication

class ImportWorker(QThread):
    progress = Signal(str)
    finished = Signal()
    error = Signal(str)

    def __init__(self, db_manager, vault_path):
        super().__init__()
        self.db = db_manager
        self.vault_path = vault_path

    def run(self):
        try:
            from app.importers.obsidian import ObsidianImporter
            importer = ObsidianImporter(self.db)
            importer.import_vault(self.vault_path, progress_callback=self.progress.emit)
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

class ExportWorker(QThread):
    progress = Signal(str)
    finished = Signal()
    error = Signal(str)

    def __init__(self, db_manager, output_path):
        super().__init__()
        self.db = db_manager
        self.output_path = output_path

    def run(self):
        try:
            from app.exporters.obsidian_exporter import ObsidianExporter
            exporter = ObsidianExporter(self.db)
            exporter.export_vault(self.output_path, progress_callback=self.progress.emit)
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

class OptimizeWorker(QThread):
    finished = Signal()
    error = Signal(str)

    def __init__(self, db_manager):
        super().__init__()
        self.db = db_manager

    def run(self):
        try:
            self.db.optimize_database()
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

class NoteLoaderWorker(QThread):
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, db_path, note_id):
        super().__init__()
        self.db_path = db_path
        self.note_id = note_id
        self.is_cancelled = False

    def run(self):
        if self.is_cancelled: return
        
        # Create a dedicated DB connection for this thread
        from app.database.manager import DatabaseManager
        db = DatabaseManager(self.db_path)
        
        try:
            # 1. Fetch Note
            note = db.get_note(self.note_id)
            if not note: 
                self.finished.emit(None)
                return
            
            if self.is_cancelled: return

            # 2. Pre-process content (simulate or perform heavy regex)
            title = note[2]
            content = note[3] if note[3] else ""
            
            result = {
                "note_id": self.note_id,
                "title": title,
                "content": content,
                "is_markdown": False,
                "processed_content": content
            }
            
            # Check format and process Markdown in worker thread
            if content.strip() and not content.lstrip().startswith("<!DOCTYPE HTML"):
                result["is_markdown"] = True
                # Process Markdown in worker thread to avoid blocking UI
                if self.is_cancelled: return
                from app.ui.blueprints.markdown import MarkdownRenderer
                result["processed_content"] = MarkdownRenderer.process_markdown_content(content)
            else:
                result["is_markdown"] = False
                result["processed_content"] = content

            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            # Close connection implicitly by letting logic end, 
            # but explicit close might be better if DatabaseManager has close()
            # Our DatabaseManager uses 'init_db' connection which is per-instance? 
            # check _get_connection usage. 
            # DatabaseManager.__init__ calls init_db.
            # If DatabaseManager doesn't keep self.conn, we are fine.
            pass

    def cancel(self):
        self.is_cancelled = True


