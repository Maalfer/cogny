import os
import shutil
from typing import List, Optional, Dict, Tuple
from pathlib import Path
 # Remove MetadataCache and VaultIndexer imports
from app.storage.watcher import VaultWatcher
from PySide6.QtCore import QObject

class FileManager(QObject):
    """
    Manages file system operations for the note application.
    Acts as an Obsidian-compatible vault manager with file-system based operations.
    """
    def __init__(self, root_path: str):
        super().__init__()
        self.root_path = os.path.abspath(root_path)
        # Use 'images' folder as requested by user
        self.images_path = os.path.join(self.root_path, "images")
        
        # Ensure images directory exists
        if not os.path.exists(self.images_path):
            os.makedirs(self.images_path, exist_ok=True)

        # File System Watcher
        self.watcher = VaultWatcher(self.root_path)
        # Connect Watcher -> We can expose a signal if needed, or just let UI handle reloads
        # For now, we can emit a signal ourselves if we want to emulate old indexer behavior,
        # but UI mostly refreshes on its own or triggered actions.
        # Let's keep the watcher running.

    def _get_rel_path(self, abs_path: str) -> str:
        return os.path.relpath(abs_path, self.root_path)

    def _get_abs_path(self, rel_path: str) -> str:
        return os.path.join(self.root_path, rel_path)

    def list_files(self) -> List[Dict]:
        """
        Returns a flat list of files for the tree builder.
        """
        items = []
        
        for root, dirs, files in os.walk(self.root_path):
            # Skip hidden directories like .obsidian, .git, .cogny
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            rel_dir = os.path.relpath(root, self.root_path)
            if rel_dir == ".":
                parent_id = None
            else:
                parent_id = os.path.dirname(rel_dir)
                if parent_id == "": parent_id = None
            
            # Subdirectories (Nodes)
            for d in dirs:
                path = os.path.join(rel_dir, d)
                if path.startswith("./"): path = path[2:]
                
                p_id = rel_dir
                if p_id == ".": p_id = None
                
                items.append({
                    'id': path,
                    'title': d, 
                    'is_folder': True, 
                    'parent_id': p_id
                })
                
            # Files (Leaves)
            for f in files:
                if not f.endswith('.md'): continue
                
                path = os.path.join(rel_dir, f)
                if path.startswith("./"): path = path[2:]
                
                p_id = rel_dir
                if p_id == ".": p_id = None
                
                items.append({
                    'id': path, 
                    'title': os.path.splitext(f)[0], 
                    'is_folder': False, 
                    'parent_id': p_id
                })
                
        return items

    def get_children(self, parent_rel_path: Optional[str] = None) -> List[Dict]:
        """
        Returns children of a specific directory (lazy loading).
        parent_rel_path: relative path to root. None for root.
        """
        if parent_rel_path is None:
            abs_path = self.root_path
        else:
            abs_path = self._get_abs_path(parent_rel_path)
            
        if not os.path.exists(abs_path) or not os.path.isdir(abs_path):
            return []
            
        items = []
        try:
            with os.scandir(abs_path) as it:
                for entry in it:
                     if entry.name.startswith('.'): 
                         continue
                     
                     if entry.name == "Adjuntos":
                         continue
                         
                     if entry.is_dir():
                         rel_path = self._get_rel_path(entry.path)
                         items.append({
                             'id': rel_path,
                             'title': entry.name,
                             'is_folder': True
                         })
                     elif entry.is_file():
                         is_md = entry.name.endswith('.md')
                         is_image = entry.name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'))
                         
                         if is_md or is_image:
                             rel_path = self._get_rel_path(entry.path)
                             items.append({
                                 'id': rel_path,
                                 'title': os.path.splitext(entry.name)[0] if is_md else entry.name,
                                 'is_folder': False
                             })
                         
            # Sort: Folders first, then items, alphabetical
            items.sort(key=lambda x: (not x['is_folder'], x['title'].lower()))
            return items
        except Exception as e:
            print(f"Error listing children of {abs_path}: {e}")
            return []

    def read_note(self, rel_path: str) -> Optional[str]:
        """Reads content of a markdown file."""
        path = self._get_abs_path(rel_path)
        if not os.path.exists(path):
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"Error reading file {path}: {e}")
            return None

    def save_note(self, rel_path: str, content: str) -> bool:
        """Saves content to a markdown file."""
        path = self._get_abs_path(rel_path)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except Exception as e:
            print(f"Error saving file {path}: {e}")
            return False

    def create_note(self, rel_path: str, is_folder: bool = False) -> bool:
        """Creates a new note or folder."""
        path = self._get_abs_path(rel_path)
        try:
            if is_folder:
                os.makedirs(path, exist_ok=True)
            else:
                # Ensure parent exists
                os.makedirs(os.path.dirname(path), exist_ok=True)
                if not path.endswith('.md'): path += '.md'
                with open(path, 'w', encoding='utf-8') as f:
                    f.write("")
            return True
        except Exception as e:
            print(f"Error creating {path}: {e}")
            return False
            
    def delete_item(self, rel_path: str):
        path = self._get_abs_path(rel_path)
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
            
    def rename_item(self, old_rel_path: str, new_name: str) -> str:
        """Returns new relative path."""
        old_path = self._get_abs_path(old_rel_path)
        parent = os.path.dirname(old_path)
        
        # Keep extension if file
        if os.path.isfile(old_path) and not new_name.endswith('.md'):
            # Check if old had extension
            _, ext = os.path.splitext(old_path)
            if ext == '.md':
                new_name += '.md'
                
        new_path = os.path.join(parent, new_name)
        os.rename(old_path, new_path)
        return self._get_rel_path(new_path)

    def move_item(self, rel_path: str, new_parent_rel_path: Optional[str]) -> Optional[str]:
        """Moves an item to a new parent directory."""
        old_path = self._get_abs_path(rel_path)
        if new_parent_rel_path:
            new_parent_path = self._get_abs_path(new_parent_rel_path)
        else:
            new_parent_path = self.root_path
            
        filename = os.path.basename(old_path)
        new_path = os.path.join(new_parent_path, filename)
        
        try:
            shutil.move(old_path, new_path)
            # Indexer update removed (watcher handles it)
            return self._get_rel_path(new_path)
        except Exception as e:
            print(f"Error moving {old_path} to {new_path}: {e}")
            return None

    def save_image(self, data: bytes, filename: str) -> str:
        """
        Saves an image to the 'images' directory.
        """
        if not os.path.exists(self.images_path):
             os.makedirs(self.images_path, exist_ok=True)
             
        path = os.path.join(self.images_path, filename)
        
        # Rename if exists
        base, ext = os.path.splitext(filename)
        counter = 1
        while os.path.exists(path):
            path = os.path.join(self.images_path, f"{base}_{counter}{ext}")
            counter += 1
            
        with open(path, 'wb') as f:
            f.write(data)
            
        return os.path.join("images", os.path.basename(path))

    def search_content(self, query: str) -> List[Dict]:
        """
        Simple file-system based full text search.
        Case-insensitive.
        Returns list of {'path': rel_path, 'title': title, 'snippet': snippet}
        """
        query = query.lower()
        results = []
        
        # Limit results for performance
        MAX_RESULTS = 50
        
        for root, dirs, files in os.walk(self.root_path):
            # Skip hidden
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            for f in files:
                if not f.endswith('.md'): continue
                
                path = os.path.join(root, f)
                rel_path = os.path.relpath(path, self.root_path)
                
                try:
                    with open(path, 'r', encoding='utf-8', errors='ignore') as file_obj:
                        content = file_obj.read()
                        
                        lower_content = content.lower()
                        if query in lower_content:
                            # Create Snippet
                            idx = lower_content.find(query)
                            start = max(0, idx - 40)
                            end = min(len(content), idx + len(query) + 40)
                            snippet = content[start:end].replace('\n', ' ')
                            
                            # Highlight match in snippet (HTML bold)
                            # We need to do this carefully on the original case text
                            # A simple replace on snippet might miss case, but for now:
                            # snippet = snippet.replace(query, f"<b>{query}</b>") # Case issue
                            
                            results.append({
                                'path': rel_path,
                                'title': os.path.splitext(f)[0],
                                'snippet': f"...{snippet}..."
                            })
                            
                            if len(results) >= MAX_RESULTS:
                                return results
                except Exception as e:
                    print(f"Error searching {rel_path}: {e}")
                    
        return results
