from PySide6.QtWidgets import QSplitter, QToolBar
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from app.ui.buscador import SearchManager
from app.ui.barra_herramientas import FormatToolbar
from app.ui.sidebar import Sidebar
from app.ui.tabbed_editor_area import TabbedEditorArea

class UiSetupMixin:
    def setup_ui(self):
        # 1. Main Container & Layout
        from app.ui.custom_title_bar import CustomTitleBar
        from PySide6.QtWidgets import QWidget, QVBoxLayout, QMenuBar
        
        container = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        container.setLayout(main_layout)
        
        # 2. Custom Title Bar (Top)
        self.title_bar = CustomTitleBar(self)
        self.title_bar.minimize_clicked.connect(self.showMinimized)
        self.title_bar.maximize_clicked.connect(self.toggle_maximize_restore)
        self.title_bar.close_clicked.connect(self.close)
        main_layout.addWidget(self.title_bar)
        
        # 3. Instantiate Components (Needed for Actions)
        self.splitter = QSplitter(Qt.Horizontal)
        
        self.sidebar = Sidebar(file_manager=self.fm, parent=self)
        self.sidebar.note_selected.connect(self.on_sidebar_note_selected)
        self.sidebar.action_requested.connect(self.on_sidebar_action)
        self.sidebar.open_in_new_tab.connect(self.on_open_in_new_tab)
        
        self.tabbed_editor = TabbedEditorArea(file_manager=self.fm, parent=self)
        self.tabbed_editor.status_message.connect(self.on_editor_status)
        
        # 4. Create Actions (Now dependencies exist)
        self.create_actions()
        
        # 5. Menu Bar (Below Title Bar)
        self.create_menus(main_layout)
        
        # 6. Toolbars (Below Menu Bar)
        self.create_toolbar(main_layout)
        
        # 7. Assemble Content
        self.splitter.addWidget(self.sidebar)
        self.splitter.addWidget(self.tabbed_editor)
        self.splitter.setSizes([300, 700])
        
        main_layout.addWidget(self.splitter)
        
        # Set Container as Central Widget
        self.setCentralWidget(container)
        
        # Restore State
        self.restore_state()

    def create_toolbar(self, layout):
        # Main Toolbar
        from PySide6.QtWidgets import QSizePolicy
        toolbar = QToolBar("Barra Principal")
        toolbar.setObjectName("MainToolbarV2")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        layout.addWidget(toolbar)
        
        # Search Bar
        self.search_manager = SearchManager(self.fm, self.sidebar.tree_view, self.sidebar.proxy_model, self.sidebar.on_selection_changed)
        toolbar.addWidget(self.search_manager.get_widget())
        
        toolbar.addSeparator()
        toolbar.addAction(self.act_export_pdf)
        toolbar.addAction(self.act_mode_toggle) # Ensure toggle is here
        
        # Editor Format Toolbar (Below Main Toolbar)
        # Get current editor's text_editor
        current_editor = self.tabbed_editor.get_current_editor()
        text_editor = current_editor.text_editor if current_editor else None
        self.editor_toolbar = FormatToolbar(self, text_editor)
        self.editor_toolbar.setMovable(False)
        self.editor_toolbar.setFloatable(False)
        self.editor_toolbar.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        layout.addWidget(self.editor_toolbar)
        
        # Connect tab change to update toolbar
        self.tabbed_editor.tab_widget.currentChanged.connect(self.on_tab_switched)

    def create_menus(self, layout):
        # Manual Menu Bar
        from PySide6.QtWidgets import QMenuBar, QSizePolicy
        menubar = QMenuBar() # No parent initially
        menubar.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        layout.addWidget(menubar)

        # File Menu
        file_menu = menubar.addMenu("&Archivo")
        file_menu.addAction(self.act_new_vault) 
        file_menu.addAction(self.act_open_vault)
        
        file_menu.addAction(self.act_new_root)
        file_menu.addAction(self.act_new_folder_root)
        file_menu.addSeparator()
        file_menu.addAction(self.act_new_child)
        file_menu.addAction(self.act_new_folder_child)
        file_menu.addSeparator()
        # Export / Import Submenu
        export_menu = file_menu.addMenu("Exportar / Importar")
        export_menu.addAction(self.act_export_pdf)
        export_menu.addAction(self.act_export_doc)
        export_menu.addSeparator()
        export_menu.addAction(self.act_backup)

        file_menu.addSeparator()
        file_menu.addAction(self.act_attach)
        file_menu.addSeparator()
        file_menu.addAction(self.act_save)
        file_menu.addSeparator()
        file_menu.addAction(self.act_exit)

        # Edit Menu
        edit_menu = menubar.addMenu("&Editar")
        edit_menu.addAction(self.act_undo)
        edit_menu.addAction(self.act_redo)
        edit_menu.addSeparator()
        edit_menu.addAction(self.act_cut)
        edit_menu.addAction(self.act_copy)
        edit_menu.addAction(self.act_paste)
        edit_menu.addSeparator()
        edit_menu.addAction(self.act_delete)
        
        # View Menu
        view_menu = menubar.addMenu("&Ver")
        
        self.act_toggle_toolbar = QAction("Barra de Formato", self, checkable=True)
        self.act_toggle_toolbar.setChecked(True)
        self.act_toggle_toolbar.triggered.connect(self.toggle_editor_toolbar)
        view_menu.addAction(self.act_toggle_toolbar)
        view_menu.addSeparator()
        view_menu.addAction(self.act_zoom_in)
        view_menu.addAction(self.act_zoom_out)
        view_menu.addSeparator()
        view_menu.addAction(self.act_page_zoom_in)
        view_menu.addAction(self.act_page_zoom_out)
        
        # Tools Menu
        tools_menu = menubar.addMenu("&Herramientas")
        tools_menu.addAction(self.act_theme)
        
        
        # Help Menu
        help_menu = menubar.addMenu("&Ayuda")
        help_menu.addAction(self.act_about)
