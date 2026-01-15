import os
import re
from app.database.manager import DatabaseManager

class ObsidianImporter:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', '.webp'}
        self.attachment_map = {} # filename -> full_path

    def import_vault(self, vault_path: str, progress_callback=None):
        if not os.path.exists(vault_path):
            raise ValueError("La ruta de la bóveda no existe")

        # 1. Wipe DB
        if progress_callback: progress_callback("Limpiando base de datos...")
        self.db.clear_database()

        # 2. Index Attachments (Images + Others)
        if progress_callback: progress_callback("Indexando adjuntos...")
        self._index_attachments(vault_path)

        # 3. Traverse and Import
        # Map directory path -> parent_note_id (db id)
        # Root of vault -> None
        dir_map = {vault_path: None}

        # We must index directories first or walk top-down correctly
        # Pre-calculate total for better progress?
        # For now, just string status updates.
        
        for root, dirs, files in os.walk(vault_path):
            dirs.sort()
            # Register directories as "Notes" (Folders)
            parent_id = dir_map.get(root)
            
            for d in dirs:
                if d.startswith('.'): continue
                full_path = os.path.join(root, d)
                
                if progress_callback: progress_callback(f"Creando carpeta: {d}")
                
                # Create Folder Note
                note_id = self.db.add_note(d, parent_id, "", is_folder=True)
                dir_map[full_path] = note_id

            files.sort()
            for f in files:
                if f.startswith('.'): continue
                name, ext = os.path.splitext(f)
                if ext.lower() == '.md':
                    if progress_callback: progress_callback(f"Importando nota: {f}")
                    self._import_note(root, f, parent_id)

    def _index_attachments(self, vault_path):
        for root, dirs, files in os.walk(vault_path):
            for f in files:
                if f.startswith('.'): continue
                _, ext = os.path.splitext(f)
                # Index everything that is NOT a markdown file
                if ext.lower() != '.md':
                    self.attachment_map[f] = os.path.join(root, f)

    def _import_note(self, root, filename, parent_id):
        full_path = os.path.join(root, filename)
        title, _ = os.path.splitext(filename)
        
        try:
            with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
        except Exception as e:
            print(f"Error reading {full_path}: {e}")
            return

        # Create Note first to get ID
        note_id = self.db.add_note(title, parent_id, "")

        # Parse Content for Links/Attachments
        new_content = self._process_links(content, note_id)
        
        # GENERATE CACHE (Double Column Architecture)
        from app.ui.blueprints.markdown import MarkdownRenderer
        raw_html = MarkdownRenderer.process_markdown_content(new_content)
        # Wrap in pre-wrap div to prevent whitespace collapse in QTextEdit
        cached_html = f'<div style="white-space: pre-wrap;">{raw_html}</div>'
        
        self.db.update_note(note_id, title, new_content, cached_html=cached_html)

    def _process_links(self, content, note_id):
        # 1. WikiLinks: ![[image.png]] (Embed) or [[doc.pdf]] (Link)
        def replace_wiki(match):
            raw = match.group(1) # "image.png" or "image.png|100"
            is_embed = match.group(0).startswith('!')
            
            if '|' in raw:
                fname = raw.split('|')[0]
            else:
                fname = raw
            
            return self._resolve_link(fname, note_id, is_embed=is_embed)

        content = re.sub(r'!?\[\[(.*?)\]\]', replace_wiki, content)

        # 2. Standard Markdown: ![alt](image.png) or [text](doc.pdf)
        def replace_md(match):
            is_embed = match.group(0).startswith('!')
            # alt = match.group(1)
            path = match.group(2)
            fname = os.path.basename(path) 
            return self._resolve_link(fname, note_id, is_embed=is_embed)

        content = re.sub(r'!?\[(.*?)\]\((.*?)\)', replace_md, content)
        
        return content

    def _resolve_link(self, filename, note_id, is_embed=False):
        _, ext = os.path.splitext(filename)
        ext = ext.lower()
        
        # Determine if it's an image
        is_image = ext in self.image_extensions
        
        # Find path
        path = self.attachment_map.get(filename)
        if not path:
             # Link to a Note?
             # If it's a link [[Note Name]], we might want to handle internal note linking later.
             # For now, if not in attachment map and looks like a note, ignore or keep text.
             # Returning name for now.
             return filename
            
        try:
            with open(path, 'rb') as f:
                data = f.read()
            
            if is_image:
                # Embed Image
                img_id = self.db.add_image(note_id, data)
                return f'<img src="image://db/{img_id}" />'
            else:
                # Embed Attachment Link
                att_id = self.db.add_attachment(note_id, filename, data)
                # User friendly HTML anchor
                return f'&nbsp;<span style="font-size: 16px;">📎</span>&nbsp;<a href="attachment://{att_id}" style="color: #4A90E2; text-decoration: none;">{filename}</a>&nbsp;'
                
        except Exception as e:
            print(f"Error al incrustar {filename}: {e}")
            return f"[Error cargando {filename}]"
