from PySide6.QtWidgets import QLineEdit, QTreeView
from PySide6.QtGui import QStandardItemModel, QStandardItem, QIcon
from PySide6.QtCore import Qt, QSortFilterProxyModel, QObject, Signal

class SearchManager(QObject):
    def __init__(self, db_manager, tree_view: QTreeView, proxy_model: QSortFilterProxyModel, selection_callback=None):
        super().__init__()
        self.db = db_manager
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
            
            # Reconnect Selection Model if it was changed
            # MainWindow handles the connection, but if we changed the model, the selection model changed.
            # We need a way to maintain the connection or notify MainWindow to reconnect.
            # We can use the callback to notify "model changed" or just handle selection here?
            # MainWindow binds: self.tree_view.selectionModel().currentChanged.connect(self.on_selection_changed)
            # When setModel is called, selectionModel is replaced.
            
            if self.selection_callback:
                self.tree_view.selectionModel().currentChanged.connect(self.selection_callback)

    def perform_smart_search(self, text):
        search_model = QStandardItemModel()
        
        # Smart Search Logic
        # 1. Clean query
        query_text = text.strip()
        
        # 2. Get results from DB
        results = self.search_db_smart(query_text)
        
        note_icon = QIcon.fromTheme("text-x-generic")
        
        for row in results:
            note_id = row[0]
            title = row[1]
            snippet = row[2] # We will fetch snippet if possible of matches
            
            # Display: Title + Snippet (maybe in tooltip or subtitle?)
            # StandardItem only supports text.
            display_text = f"{title}"
            
            item = QStandardItem(display_text)
            item.setEditable(False)
            item.note_id = note_id
            item.setIcon(note_icon)
            
            # Use Tooltip for context/snippet
            if snippet:
                # Clean snippet characters?
                item.setToolTip(f"...{snippet}...")
                
            search_model.appendRow(item)
            
        self.tree_view.setModel(search_model)
        self.tree_view.setRootIsDecorated(False)
        
        if self.selection_callback:
            self.tree_view.selectionModel().currentChanged.connect(self.selection_callback)
            
    def search_db_smart(self, query):
        """
        Implements 'Google-like' search:
        - Splits query into tokens.
        - Tries to match ALL tokens first (AND).
        - Then matches ANY token (OR) for improved recall but lower rank.
        - Uses Prefix matching (*) for each token.
        """
        # We delegate the raw query execution to DB, but we construct the logic here or in DB?
        # User wants logic in buscador.py?
        # But DB access is via self.db reference.
        # Ideally, we call a generic query method on DB or we extend DB.
        # Let's add a 'search_advanced' to DB or modify 'search_notes_fts'.
        # Since I cannot modify DB and buscador.py simultaneously efficiently without multiple tools,
        # I will assume I can call a new method I will add to DB, OR reuse search_notes_fts if I can pass raw query.
        # Existing search_notes_fts builds the query internally: f'"{sanitized}"*'
        # This is too restrictive. I need to modify DB manager first to allow flexible queries or improved logic.
        
        # Let's modify DB manager to accept a raw FTS query or handle the logic there.
        # But the user said "toda la logica del buscador este en ... buscador.py".
        # So buscador.py should construct the FTS query string and pass it to a generic DB search method.
        # BUT search_notes_fts currently HARDCODES the query construction.
        # I MUST refactor DatabaseManager.search_notes_fts to be more flexible.
        
    def search_db_smart(self, query):
        """
        Implements 'Google-like' search:
        - Splits query into tokens.
        - Tries difference strategies combined with OR.
        """
        import re
        
        # 1. Sanitize
        # Remove special chars that might break FTS syntax: " * : ( )
        clean_query = re.sub(r'[\"\*\:\(\)]', '', query).strip()
        if not clean_query:
            return []
            
        tokens = clean_query.split()
        if not tokens:
             return []
             
        # Strategy 1: Exact Phrase (Highest Rank implicitly)
        # "foo bar"
        exact_phrase = f'"{clean_query}"'
        
        # Strategy 2: All terms (AND) with prefix support
        # foo* AND bar*
        and_terms = " AND ".join([f'"{t}"*' for t in tokens])
        
        # Strategy 3: Any term (OR) with prefix support
        # foo* OR bar*
        or_terms = " OR ".join([f'"{t}"*' for t in tokens])
        
        # Combine strategies
        # Note: SQLite FTS5 rank is lower = better.
        # If we just do OR, the ones with more matches appear first naturally.
        # But "AND" matches are effectively a subset of "OR".
        # We can just run the OR query. The ranking function (bm25 default) 
        # naturally ranks documents containing ALL terms higher than those with 1.
        # So we don't need complex boolean logic, just an OR of all terms with prefix.
        
        # However, to prioritize "phrase" matches, we might want to boost them?
        # FTS5 standard ranking handles term proximity to some extent.
        # Let's try: (term1* OR term2* OR ...)
        
        final_query = or_terms
        
        # Execute
        return self.db.advanced_search(final_query)
