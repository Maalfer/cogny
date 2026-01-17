from PySide6.QtWidgets import QLineEdit, QTreeView
from PySide6.QtGui import QStandardItemModel, QStandardItem, QIcon
from PySide6.QtCore import Qt, QSortFilterProxyModel, QObject, Signal

class SearchManager(QObject):
    def __init__(self, file_manager, tree_view: QTreeView, proxy_model: QSortFilterProxyModel, selection_callback=None):
        super().__init__()
        self.fm = file_manager
        self.tree_view = tree_view
        self.proxy_model = proxy_model
        self.selection_callback = selection_callback
        
        # Debounce Timer
        from PySide6.QtCore import QTimer
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(300) # 300ms delay
        self.search_timer.timeout.connect(self.execute_pending_search)
        
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Buscar notas (Google-like)...")
        self.search_bar.textChanged.connect(self.on_search_text_changed)
        
        # Style
        self.search_bar.setStyleSheet("""
            QLineEdit {
                border: 1px solid #3F3F3F;
                border-radius: 15px;
                padding: 5px 10px;
                background-color: #1E1E1E;
                color: #E0E0E0;
                min-width: 200px;
            }
            QLineEdit:focus {
                border: 1px solid #3b82f6;
            }
        """)

    def get_widget(self):
        return self.search_bar

    def on_search_text_changed(self, text):
        # Restart timer
        self.search_timer.start()

    def execute_pending_search(self):
        text = self.search_bar.text()
        if not text.strip():
            self.restore_tree_view()
        else:
            self.perform_smart_search(text)

    def restore_tree_view(self):
        # Restore Tree View Model
        if self.tree_view.model() != self.proxy_model:
            self.tree_view.setModel(self.proxy_model)
            self.tree_view.setRootIsDecorated(True)
            self.proxy_model.setFilterRegularExpression("")
            
            if self.selection_callback:
                self.tree_view.selectionModel().currentChanged.connect(self.selection_callback)

    def perform_smart_search(self, text):
        search_model = QStandardItemModel()
        
        # Smart Search Logic
        query_text = text.strip().lower()
        
        # Get results from FS
        results = self.search_files(query_text)
        
        note_icon = QIcon.fromTheme("text-x-generic")
        
        for row in results:
            note_id = row[0]
            title = row[1]
            snippet = row[2] 
            
            display_text = f"{title}"
            
            item = QStandardItem(display_text)
            item.setEditable(False)
            item.note_id = note_id
            item.setIcon(note_icon)
            
            # Use Tooltip for context/snippet
            if snippet:
                item.setToolTip(f"...{snippet}...")
                
            search_model.appendRow(item)
            
        self.tree_view.setModel(search_model)
        self.tree_view.setRootIsDecorated(False)
        
        if self.selection_callback:
            self.tree_view.selectionModel().currentChanged.connect(self.selection_callback)
            
    def search_files(self, query):
        """
        Searches all markdown files in the vault.
        Returns list of (rel_path, title, snippet).
        """
        import os
        results = []
        if not query: return []
        
        # Split query for AND logic
        terms = query.split()
        
        for root, dirs, files in os.walk(self.fm.root_path):
            # Skip hidden
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            for file in files:
                if not file.endswith('.md'): continue
                
                path = os.path.join(root, file)
                rel_path = self.fm._get_rel_path(path)
                
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    content_lower = content.lower()
                    title = os.path.splitext(file)[0]
                    title_lower = title.lower()
                    
                    # Check Match (Title OR Content)
                    # Simplified: Check if ALL terms match either Title or Content
                    # For snippet extraction we need to find positions.
                    
                    match = True
                    for term in terms:
                        if term not in title_lower and term not in content_lower:
                            match = False
                            break
                    
                    if match:
                        # Extract Snippet (first term match)
                        snippet = ""
                        idx = content_lower.find(terms[0])
                        if idx != -1:
                            start = max(0, idx - 20)
                            end = min(len(content), idx + 50)
                            snippet = content[start:end].replace("\n", " ")
                        elif terms[0] in title_lower:
                            snippet = "Coincidencia en título"
                            
                        results.append((rel_path, title, snippet))
                        
                except Exception as e:
                    print(f"Error searching {path}: {e}")
                    
        return results
