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
    chunk_loaded = Signal(str) # New signal for progressive chunks
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
        # Skip init (backup/integrity check) to avoid freezing!
        db = DatabaseManager(self.db_path, initialize=False)
        
        try:
            # 1. Fetch Content
            # For massive notes, we might want to fetch only part, but currently fetch_one fetches all.
            # Optimization: Given fetch is instant (~0.02s), the bottleneck is Processing.
            content = db.get_note_content(self.note_id)
            if content is None: 
                content = ""
            
            if self.is_cancelled: return

            # 2. Check format
            is_markdown = content.strip() and not content.lstrip().startswith("<!DOCTYPE HTML")
            
            if not is_markdown:
                # If HTML, we can't easily split safely without parser. Just emit all.
                self.chunk_loaded.emit(content)
                self.finished.emit({"note_id": self.note_id, "done": True})
                return

            # 3. Full Markdown Processing (Safe & Robust)
            # Chunking with python-markdown is dangerous because it breaks block/context awareness.
            # We process the entire file at once.
            
            from app.ui.blueprints.markdown import MarkdownRenderer
            
            processed = MarkdownRenderer.process_markdown_content(content)
            self.chunk_loaded.emit(processed)
            self.finished.emit({"note_id": self.note_id, "done": True})

        except Exception as e:
            self.error.emit(str(e))
        finally:
            pass

    def cancel(self):
        self.is_cancelled = True


