from PySide6.QtWidgets import QSplitter, QToolBar
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from app.ui.buscador import SearchManager
from app.ui.barra_herramientas import FormatToolbar
from app.ui.blueprints.sidebar import Sidebar
from app.ui.blueprints.editor_area import EditorArea

class UiSetupMixin:
    def setup_ui(self):
        # Central Widget
        self.splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(self.splitter)

        # 1. Sidebar Blueprint
        self.sidebar = Sidebar(self.db, self)
        self.sidebar.note_selected.connect(self.on_sidebar_note_selected)
        self.sidebar.action_requested.connect(self.on_sidebar_action)
        self.splitter.addWidget(self.sidebar)

        # 2. Editor Blueprint
        self.editor_area = EditorArea(self.db, self)
        self.editor_area.status_message.connect(self.on_editor_status)
        self.splitter.addWidget(self.editor_area)
        
        self.splitter.setSizes([300, 700])

        # Create Actions and Menus
        self.create_actions()
        self.create_menus()
        self.create_toolbar()
        
        # Restore State
        self.restore_state()

    def create_toolbar(self):
        toolbar = QToolBar("Barra Principal")
        self.addToolBar(toolbar)
        
        # Search Bar
        # We need to link SearchManager to Sidebar's tree and model
        self.search_manager = SearchManager(self.db, self.sidebar.tree_view, self.sidebar.proxy_model, self.sidebar.on_selection_changed)
        toolbar.addWidget(self.search_manager.get_widget())
        
        self.addToolBarBreak() 
        
        self.editor_toolbar = FormatToolbar(self, self.editor_area.text_editor)
        self.addToolBar(self.editor_toolbar)

    def create_menus(self):
        menubar = self.menuBar()

        # File Menu
        file_menu = menubar.addMenu("&Archivo")
        file_menu.addAction(self.act_new_db)
        file_menu.addAction(self.act_open_db)
        file_menu.addAction(self.act_save_as_db)
        
        file_menu.addSeparator()
        file_menu.addAction(self.act_read_later_list)
        
        file_menu.addSeparator()
        
        file_menu.addAction(self.act_new_root)
        file_menu.addAction(self.act_new_folder_root)
        file_menu.addSeparator()
        file_menu.addAction(self.act_new_child)
        file_menu.addAction(self.act_new_folder_child)
        file_menu.addSeparator()
        file_menu.addAction(self.act_import_obsidian)
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
        
        action_import_obsidian = QAction("Importar Obsidian...", self)
        action_import_obsidian.triggered.connect(self.import_obsidian_vault)
        tools_menu.addAction(action_import_obsidian)

        action_export_obsidian = QAction("Exportar a Obsidian...", self)
        action_export_obsidian.triggered.connect(self.export_obsidian_vault)
        tools_menu.addAction(action_export_obsidian)
        
        action_optimize = QAction("Optimizar Base de Datos", self)
        action_optimize.triggered.connect(self.optimize_database_action)
        tools_menu.addAction(action_optimize)
        
        # Help Menu
        help_menu = menubar.addMenu("&Ayuda")
        help_menu.addAction(self.act_about)
