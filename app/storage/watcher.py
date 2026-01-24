import os
from PySide6.QtCore import QObject, Signal, QFileSystemWatcher

class VaultWatcher(QObject):
    file_changed = Signal(str) # rel_path
    directory_changed = Signal(str) # path changed
    
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
        print(f"DEBUG: Directory changed: {path}")
        self.directory_changed.emit(path)

    def _on_file_changed(self, path):
        # Update specific file
        rel_path = os.path.relpath(path, self.vault_path)
        self.file_changed.emit(rel_path)
