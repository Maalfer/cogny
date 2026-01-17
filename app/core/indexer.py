import os
import re
import time
from typing import List, Tuple, Dict
from PySide6.QtCore import QObject, QRunnable, Signal, QThreadPool, QFileSystemWatcher
from app.storage.metadata_cache import MetadataCache

class IndexerSignals(QObject):
    started = Signal()
    progress = Signal(str) # current file
    finished = Signal()
    file_updated = Signal(str) # path

class VaultIndexer(QObject):
    """
    Manages background indexing of the vault.
    """
    def __init__(self, vault_path: str, cache: MetadataCache):
        super().__init__()
        self.vault_path = vault_path
        self.cache = cache
        self.thread_pool = QThreadPool()
        self.signals = IndexerSignals()
        self.is_indexing = False

    def scan_all(self):
        if self.is_indexing: return
        self.is_indexing = True
        
        worker = IndexingWorker(self.vault_path, self.cache)
        worker.signals.started.connect(self.signals.started)
        worker.signals.progress.connect(self.signals.progress)
        worker.signals.finished.connect(self._on_finished)
        
        self.thread_pool.start(worker)

    def _on_finished(self):
        self.is_indexing = False
        self.signals.finished.emit()

    def update_file(self, rel_path: str):
        """Update a single file in the background."""
        worker = FileUpdateWorker(self.vault_path, rel_path, self.cache)
        worker.signals.finished.connect(lambda: self.signals.file_updated.emit(rel_path))
        self.thread_pool.start(worker)


class IndexingWorker(QRunnable):
    def __init__(self, vault_path, cache):
        super().__init__()
        self.vault_path = vault_path
        self.cache = cache
        self.signals = IndexerSignals()

    def run(self):
        self.signals.started.emit()
        
        # 1. Get current DB state
        db_files = self.cache.get_all_files() # {rel_path: mtime}
        
        found_files = set()
        
        # 2. Walk Directory
        for root, dirs, files in os.walk(self.vault_path):
            # Ignore hidden dirs (like .cogny, .git)
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            for file in files:
                if not file.endswith('.md'): continue
                
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, self.vault_path)
                mtime = os.path.getmtime(abs_path)
                size = os.path.getsize(abs_path)
                
                found_files.add(rel_path)
                
                # Check if needs update
                if rel_path not in db_files or db_files[rel_path] != mtime:
                    self.signals.progress.emit(rel_path)
                    self._index_file(rel_path, abs_path, mtime, size)

        # 3. Clean up deleted files
        for rel_path in db_files:
            if rel_path not in found_files:
                self.cache.remove_file(rel_path)
                
        self.signals.finished.emit()

    def _index_file(self, rel_path, abs_path, mtime, size):
        try:
            with open(abs_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 1. Upsert File
            file_id = self.cache.upsert_file(rel_path, mtime, size)
            if not file_id: return

            # 2. Parse Metadata
            parser = MarkdownParser(content)
            
            self.cache.add_links(file_id, parser.extract_links())
            self.cache.add_tags(file_id, parser.extract_tags())
            self.cache.add_frontmatter(file_id, parser.extract_frontmatter())
            self.cache.add_headers(file_id, parser.extract_headers())
            
            # 3. Update FTS
            title = os.path.splitext(os.path.basename(rel_path))[0]
            self.cache.update_fts(file_id, title, content)
            
        except Exception as e:
            print(f"Error indexing {rel_path}: {e}")

class FileUpdateWorker(QRunnable):
    def __init__(self, vault_path, rel_path, cache):
        super().__init__()
        self.vault_path = vault_path
        self.rel_path = rel_path
        self.cache = cache
        self.signals = IndexerSignals()

    def run(self):
        abs_path = os.path.join(self.vault_path, self.rel_path)
        if not os.path.exists(abs_path):
            self.cache.remove_file(self.rel_path)
            self.signals.finished.emit()
            return

        try:
            mtime = os.path.getmtime(abs_path)
            size = os.path.getsize(abs_path)
            
            with open(abs_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            file_id = self.cache.upsert_file(self.rel_path, mtime, size)
            if file_id:
                parser = MarkdownParser(content)
                self.cache.add_links(file_id, parser.extract_links())
                self.cache.add_tags(file_id, parser.extract_tags())
                self.cache.add_frontmatter(file_id, parser.extract_frontmatter())
                self.cache.add_headers(file_id, parser.extract_headers())
                
                title = os.path.splitext(os.path.basename(self.rel_path))[0]
                self.cache.update_fts(file_id, title, content)
                
        except Exception as e:
            print(f"Error updating file {self.rel_path}: {e}")
        
        self.signals.finished.emit()


class MarkdownParser:
    def __init__(self, content):
        self.content = content
        self.lines = content.splitlines()

    def extract_links(self) -> List[Tuple[str, str, int]]:
        links = []
        # Standard: [alt](url)
        regex_std = re.compile(r"!{0,1}\[.*?\]\((.*?)\)")
        # Wiki: [[target]] or [[target|alias]]
        regex_wiki = re.compile(r"!{0,1}\[\[(.*?)\]\]")
        
        for i, line in enumerate(self.lines):
            line_num = i + 1
            
            for m in regex_std.finditer(line):
                target = m.group(1)
                links.append((target, 'markdown', line_num))
                
            for m in regex_wiki.finditer(line):
                content = m.group(1)
                target = content.split('|')[0]
                links.append((target, 'wikilink', line_num))
                
        return links

    def extract_tags(self) -> List[Tuple[str, int]]:
        tags = []
        # Fix: Avoid variable-width lookbehind (?<=^| )
        # Use (?:^|\s) to match start or whitespace, then capture tag without hash in group 1
        regex_tag = re.compile(r"(?:^|\s)#([a-zA-Z0-9_\-]+)")
        
        for i, line in enumerate(self.lines):
            line_num = i + 1
            for m in regex_tag.finditer(line):
                tags.append((m.group(1), line_num))
        return tags

    def extract_frontmatter(self) -> Dict[str, str]:
        fm = {}
        if self.content.startswith("---"):
            try:
                # Find end of frontmatter
                end_idx = self.content.find("\n---", 3)
                if end_idx != -1:
                    fm_block = self.content[3:end_idx]
                    import yaml
                    try:
                        data = yaml.safe_load(fm_block)
                        if isinstance(data, dict):
                            fm = data
                    except: pass
            except: pass
        return fm

    def extract_headers(self) -> List[Tuple[int, str, int]]:
        headers = []
        for i, line in enumerate(self.lines):
            if line.startswith("#"):
                m = re.match(r"^(#{1,6})\s+(.*)", line)
                if m:
                    level = len(m.group(1))
                    text = m.group(2).strip()
                    headers.append((level, text, i + 1))
        return headers

class VaultWatcher(QObject):
    file_changed = Signal(str) # rel_path
    
    def __init__(self, vault_path: str):
        super().__init__()
        self.vault_path = vault_path
        self.watcher = QFileSystemWatcher()
        self.watcher.addPath(vault_path)
        
        # Recursively add subdirectories
        for root, dirs, _ in os.walk(vault_path):
            # Ignore hidden
            if any(part.startswith('.') for part in root.split(os.sep)):
                continue
            self.watcher.addPath(root)
            
        self.watcher.directoryChanged.connect(self._on_dir_changed)
        self.watcher.fileChanged.connect(self._on_file_changed)

    def _on_dir_changed(self, path):
        # Re-scan dir to find new subdirs or files?
        # QFileSystemWatcher on directories signals when content changes (add/remove file)
        # But doesn't tell us WHAT changed in standard API.
        # Ideally we'd trigger a quick scan or use a better watcher like watchdog.
        # For this prototype: we can rely on Indexer's periodic scan or 
        # just assume user added/removed something and trigger Indexer scan if we want to be safe.
        # BUT for created files, we need to add them to watcher if they are directories.
        pass

    def _on_file_changed(self, path):
        # Update specific file
        rel_path = os.path.relpath(path, self.vault_path)
        self.file_changed.emit(rel_path)
