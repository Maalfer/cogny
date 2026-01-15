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
        db = DatabaseManager(self.db_path)
        
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

            # 3. Progressive Markdown Processing
            from app.ui.blueprints.markdown import MarkdownRenderer
            
            # Simple Strategy:
            # Split by double newline (paragraphs) to find safe break points.
            # But wait, code blocks (```) can span newlines.
            
            # Better Strategy for Perceived Speed:
            # 1. Process first N lines (Preview) -> Emit
            # 2. Process Rest -> Emit
            
            lines = content.split('\n')
            total_lines = len(lines)
            CHUNK_SIZE = 50 # Process 50 lines first (Quick Preview)
            
            # Optimization: If small enough, just do it all.
            if total_lines <= CHUNK_SIZE * 2:
                 processed = MarkdownRenderer.process_markdown_content(content)
                 self.chunk_loaded.emit(processed)
                 self.finished.emit({"note_id": self.note_id, "done": True})
                 return

            # Helper to join safely
            def process_chunk(chunk_lines):
                text = "\n".join(chunk_lines)
                # Note: Simply processing a chunk might break if it ends inside a code block.
                # However, MarkdownRenderer.process_markdown_content handles code blocks effectively
                # by regex splitting.
                # If we cut inside a code block, the regex `split(```...```)` won't match correctly
                # in the first chunk (unclosed) or second chunk (unopened).
                #
                # ROBUST APPROACH:
                # Scan for ```. If count is odd, we are inside a code block. Extend chunk until even.
                return text

            current_idx = 0
            
            while current_idx < total_lines:
                if self.is_cancelled: return
                
                # Determine end index
                end_idx = min(current_idx + CHUNK_SIZE, total_lines)
                
                # Check for code block safety
                # We need to ensure we don't split inside a code block
                # Count ``` occurrences in the proposed chunk? No, in the CUMULATIVE text?
                # Actually, we treat chunks as independent for rendering? 
                # If we render chunk 1 safely, it produces HTML.
                # If chunk 2 is rendered, it appends HTML.
                # If a code block spans chunk 1 and 2:
                # Chunk 1 has `<pre><code>...` but no closing `</code></pre>`? 
                # MarkdownRenderer logic `re.split` relies on finding PAIRS of ```. 
                # If chunk 1 has only one ```, it will treat it as text (escaped).
                # Then chunk 2 has closing ```, it will treat it as text.
                # RESULT: BROKEN CODE BLOCK.
                
                # FIX: We must ensure we split OUTSIDE code blocks.
                # Scan lines from current_idx.
                
                scan_idx = current_idx
                in_code_block = False
                
                # Look ahead to find a safe break point
                # We want at least CHUNK_SIZE, but extend if inside code block.
                
                while scan_idx < total_lines:
                    line = lines[scan_idx]
                    if line.strip().startswith("```"):
                        in_code_block = not in_code_block
                    
                    scan_idx += 1
                    
                    # If we have enough lines AND we are NOT inside a code block
                    if scan_idx - current_idx >= CHUNK_SIZE and not in_code_block:
                         break
                
                # Now scan_idx is our split point
                chunk_lines = lines[current_idx:scan_idx]
                chunk_text = "\n".join(chunk_lines)
                
                # Process
                processed = MarkdownRenderer.process_markdown_content(chunk_text)
                
                # If this is not the first chunk, we might need a newline prefix for safety?
                # Actually, process_markdown_content returns a block of HTML.
                # We just emit it.
                if processed:
                    # Add a newline visual or simple break? 
                    # MarkdownRenderer returns block elements usually or text.
                    # Appending HTML works fine.
                    self.chunk_loaded.emit(processed)
                
                current_idx = scan_idx
                
                # Yield to event loop slightly if needed? QThread handles it.
            
            self.finished.emit({"note_id": self.note_id, "done": True})

        except Exception as e:
            self.error.emit(str(e))
        finally:
            pass

    def cancel(self):
        self.is_cancelled = True


