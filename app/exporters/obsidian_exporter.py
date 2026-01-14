import os
import re
from app.database.manager import DatabaseManager

class ObsidianExporter:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def export_vault(self, output_path: str, progress_callback=None):
        """
        Exports the entire vault to the specified output_path.
        """
        if not os.path.exists(output_path):
            os.makedirs(output_path)

        # 1. Create Images Directory
        images_dir = os.path.join(output_path, "images")
        if not os.path.exists(images_dir):
            os.makedirs(images_dir)

        # 2. Get Root Notes (notes with no parent)
        # We need a way to traverse the whole tree.
        # DatabaseManager doesn't have a full tree traversal method easy available 
        # that gives us the structure. 
        # We can implement a recursive method here.
        
        if progress_callback: progress_callback("Iniciando exportación...")
        
        # Helper to get children efficiently? 
        # Doing query inside loop is okay for local DB.
        self._process_children(None, output_path, images_dir)
        
        if progress_callback: progress_callback("Exportación completada.")

    def _process_children(self, parent_id, current_path, images_dir_abs):
        """
        Recursive function to process children of a note (or root).
        """
        # Get children
        children = self.db.get_children(parent_id) 
        # check if manager.get_children returns full rows or list of tuples
        # implementation says: SELECT id, title FROM notes ...
        
        for (note_id, title) in children:
            # Get full note data (content)
            note_row = self.db.get_note(note_id)
            # note_row is likely (id, parent_id, title, content, created_at, updated_at) - see init_db schema
            # schema: id, parent_id, title, content, ...
            # Row index lookup via name if configured, but let's assume indices relative to schema.
            # id=0, parent=1, title=2, content=3
            
            content = note_row[3] if note_row[3] else ""
            
            # Sanitized Title for filesystem
            safe_title = self._sanitize_filename(title)
            
            # Check if this note has children (is it a folder?)
            grand_children = self.db.get_children(note_id)
            is_folder = len(grand_children) > 0
            
            # Case 1: Is Folder
            if is_folder:
                new_folder_path = os.path.join(current_path, safe_title)
                if not os.path.exists(new_folder_path):
                    os.makedirs(new_folder_path)
                
                # Recurse
                self._process_children(note_id, new_folder_path, images_dir_abs)
                
                # If it also has content, create a file inside
                if content.strip():
                     # To avoid name collision if a file "Title.md" exists (unlikely in Obsidian strict structure, strict uniqueness),
                     # but here we separate folder and file.
                     # Obsidian practice: Folder "Title" and File "Title.md" typically side-by-side?
                     # OR File "Title.md" inside Folder "Title"? Obsidian doesn't autopreview that.
                     # Let's put "Title.md" side-by-side with Folder "Title".
                     # Wait, if I'm processing children, they will go INTO the folder.
                     # So if I make a file "Title.md" at `current_path`, it sits next to `new_folder_path`.
                     pass 

            # Create the Markdown File
            # Even if it's a folder, if it has content (or even if empty but is a note), we usually want a file.
            # Importer creates "Notes" for directories.
            # If content is EMPTY and it IS a folder, maybe skip creating a useless empty .md file?
            # User wants "Export to Obsidian".
            # If I skip, I lose metadata if any. But usually folders are just containers.
            
            if not content.strip() and is_folder:
                continue

            # Determine file path
            # If it's a folder, do we put the text in `Folder/Title.md`? No that's recursive.
            # We put it at `current_path/Title.md`.
            file_path = os.path.join(current_path, f"{safe_title}.md")
            
            # Process Content (Images)
            final_content = self._process_content(content, note_id, images_dir_abs, current_path)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(final_content)

    def _process_content(self, content: str, note_id: int, images_dir_abs: str, note_dir_abs: str) -> str:
        """
        Replaces image://db/{id} with relative paths to exported images.
        """
        if not content:
            return ""

        # Pattern for images: <img src="image://db/123" ... /> or ![...](image://db/123)
        # The editor saves as HTML usually `src="image://db/..."`.
        # Obsidian expects Markdown `![[image.png]]` or `![alt](path/image.png)`.
        
        # 1. Convert HTML img tags to Markdown if necessary?
        # The database stores HTML content?
        # `pdf_exporter` assumes HTML. `obsidian.py` import creates Markdown? 
        # CHECK: Obsidian Importer: `_process_links` takes MD `![[...]]` and converts to `image://db/...` (custom HTML string) or `attachment://`
        # `return f'<img src="image://db/{img_id}" />'`
        # So YES, the DB content is storing HTML tags for images.
        
        def replace_img_tag(match):
            # match: <img src="image://db/123" ... />
            # We need to extract ID
            full_tag = match.group(0)
            src_match = re.search(r'src="image://db/(\d+)"', full_tag)
            if not src_match:
                return full_tag # Keep as is if format weird
            
            img_id = int(src_match.group(1))
            
            # Export the image
            filename = self._export_image_to_fs(img_id, images_dir_abs)
            
            # Create Relative path for Link
            # From `note_dir_abs` to `images_dir_abs/filename`
            # But standard Obsidian Wikilink `![[filename]]` is easiest and works if "Use WikiLinks" is on (default).
            # User asked: "donde las notas tendran vinculado correctamente donde esta cada imagen"
            # If I use `![[filename]]`, Obsidian finds it in the vault (if unique).
            # If I use relative path: `rel = os.path.relpath(os.path.join(images_dir_abs, filename), note_dir_abs)`
            # `![image](rel)`
            
            # Let's use standard Markdown relative path for maximum compatibility.
            image_abs_path = os.path.join(images_dir_abs, filename)
            rel_path = os.path.relpath(image_abs_path, note_dir_abs)
            
            return f"![{filename}]({rel_path})"

        # Replace standard HTML <img> tags
        new_content = re.sub(r'<img[^>]+src="image://db/\d+"[^>]*>', replace_img_tag, content)
        
        # Also clean up other HTML?
        # DB content seems to be HTML (from `QTextEdit` likely).
        # We might need a full HTML -> Markdown converter.
        # But for now, user asked specifically about images.
        # If I leave `<b>`, Obsidian renders it? Yes, Obsidian renders HTML.
        # But a true "Export to Obsidian" usually implies Markdown.
        # `pdf_exporter` treats it as HTML.
        # `ObsidianImporter` reads Markdown, converts links to HTML tags, and saves.
        # So if I import valid MD, it becomes MD with HTML tags for images.
        # If I edit it in app, it might gain `<div>`, `<span>` etc from rich text editor?
        # Assuming we just handle images for now as requested.
        
        return new_content

    def _export_image_to_fs(self, img_id: int, images_dir: str) -> str:
        """
        Reads image from DB, saves to fs, returns filename.
        """
        # Check if already exported? 
        # IDs are unique, so name `image_{id}.png` is unique.
        filename = f"image_{img_id}.png"
        path = os.path.join(images_dir, filename)
        
        if not os.path.exists(path):
            blob = self.db.get_image(img_id)
            if blob:
                with open(path, 'wb') as f:
                    f.write(blob)
        
        return filename

    def _sanitize_filename(self, name: str) -> str:
        # Basic sanitization
        return re.sub(r'[<>:"/\\|?*]', '_', name).strip()
