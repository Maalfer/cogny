from PySide6.QtWidgets import QMainWindow, QToolBar, QSplitter, QWidget, QVBoxLayout, QMenuBar, QSizePolicy, QApplication
from PySide6.QtGui import QIcon, QAction, QCursor
from PySide6.QtCore import QSettings, Signal, QTimer, Qt, QEvent, QPoint
import os

from app.storage.file_manager import FileManager
from app.storage.config_manager import ConfigManager
from app.ui.ui_state import UiStateMixin
from app.ui.ui_theme import UiThemeMixin
# from app.ui.ui_actions import UiActionsMixin -> Superseded by ActionManager
# from app.ui.ui_setup import UiSetupMixin -> Integrated/Simplified

from app.ui.managers.action_manager import ActionManager
from app.ui.custom_title_bar import CustomTitleBar
from app.ui.sidebar import Sidebar
from app.ui.tabbed_editor_area import TabbedEditorArea
from app.ui.features.search import SearchManager
from app.ui.views.toolbar import FormatToolbar

class MainWindow(UiStateMixin, UiThemeMixin, QMainWindow):
    """
    Main Window of the application.
    Uses Composition for Actions and Setup logic.
    """
    ready = Signal()
    
    def __init__(self, vault_path=None, is_draft=False):
        super().__init__()
        
        # Frameless Window
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setMouseTracking(True)
        
        # Window state tracking
        self._is_maximized = False
        self._normal_geometry = None
        # self._resize_margin = 5 -> Moved to Handler

        # Resize Handler
        from app.ui.managers.window_manager import WindowResizeHandler
        self.resize_handler = WindowResizeHandler(self)
        
        # Install Event Filter for Resizing
        QApplication.instance().installEventFilter(self)
        
        self.is_draft = is_draft
        self.vault_path = vault_path
        
        # Resolve Assets Path
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")) 
        # Path: app/ui/views/main_window.py -> 3 levels to app/
        # Check if assets is in root.
        icon_path = os.path.join(base_dir, "assets", "logo.png")
        self.setWindowIcon(QIcon(icon_path))

        # Setup Vault
        if not vault_path:
             vault_path = os.path.expanduser("~/Documentos")
             
        self.fm = FileManager(vault_path)
        self.config_manager = ConfigManager(self.fm.root_path)
        
        # 1. UI Setup (Inline or Helper)
        self.setup_ui()
        
        # 2. Action Manager (Handles Menus/Actions)
        self.action_manager = ActionManager(self)
        
        # 3. Post-Setup Wiring
        self.setup_menus_and_toolbars()
        
        display_name = 'Borrador' if is_draft else (os.path.basename(vault_path) if vault_path else 'Sin Bóveda')
        self.setWindowTitle(f"Cogny - {display_name}")
        self.resize(1200, 800)
        
        # Apply Initial Theme
        current_theme = self.config_manager.get("theme", "Dark")
        self.switch_theme(current_theme)
        
        self.setup_tray_icon()
        self.setup_autosave()
    
    def setup_ui(self):
        container = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        container.setLayout(main_layout)
        
        # Custom Title Bar
        self.title_bar = CustomTitleBar(self)
        self.title_bar.minimize_clicked.connect(self.showMinimized)
        self.title_bar.maximize_clicked.connect(self.toggle_maximize_restore)
        self.title_bar.close_clicked.connect(self.close)
        
        main_layout.addWidget(self.title_bar)
        
        # Components
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setOpaqueResize(False)
        
        self.sidebar = Sidebar(file_manager=self.fm, parent=self)
        self.sidebar.note_selected.connect(self.on_sidebar_note_selected)
        # We need to bridge sidebar actions to action manager or handle them here?
        # Sidebar emits 'action_requested'. 
        self.sidebar.action_requested.connect(self.on_sidebar_action)
        self.sidebar.open_in_new_tab.connect(self.on_open_in_new_tab)
        self.title_bar.sidebar_toggle_clicked.connect(lambda: self.sidebar.setVisible(not self.sidebar.isVisible()))
        
        self.tabbed_editor = TabbedEditorArea(file_manager=self.fm, parent=self)
        self.tabbed_editor.status_message.connect(self.on_editor_status)
        
        # Search Manager
        self.search_manager = SearchManager(self.fm, self.sidebar.tree_view, self.sidebar.proxy_model, self.sidebar.on_selection_changed)
        self.title_bar.add_search_widget(self.search_manager.get_widget())
        
        self.splitter.addWidget(self.sidebar)
        self.splitter.addWidget(self.tabbed_editor)
        self.splitter.setSizes([300, 700])
        
        main_layout.addWidget(self.splitter)
        self.setCentralWidget(container)
        
        # Restore State
        self.restore_state()

    def setup_menus_and_toolbars(self):
        # Add Actions to Title Bar specific widgets
        self.title_bar.add_toggle_button(self.action_manager.act_mode_toggle)
        
        # Menu Bar (Delegate to ActionManager? No, AM created actions, we map them here)
        # Actually ActionManager can construct the menu if we pass the menubar?
        # Or we keep menu construction in MainWindow but using AM actions.
        # Let's simple Copy-Paste menu logic but use self.action_manager.act_...
        
        menubar = QMenuBar()
        menubar.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.title_bar.set_menu_bar(menubar)
        
        am = self.action_manager
        
        # File
        file = menubar.addMenu("&Archivo")
        file.addAction(am.act_new_vault)
        file.addAction(am.act_open_vault)
        file.addAction(am.act_open_explorer) # New
        file.addAction(am.act_new_root)
        file.addAction(am.act_new_folder_root)
        file.addSeparator()
        file.addAction(am.act_new_child)
        file.addAction(am.act_new_folder_child)
        file.addSeparator()
        exp = file.addMenu("Exportar / Importar")
        exp.addAction(am.act_export_pdf)
        exp.addAction(am.act_export_doc)
        exp.addSeparator()
        exp.addAction(am.act_backup)
        file.addSeparator()
        file.addSeparator()
        file.addAction(am.act_save)
        file.addSeparator()
        file.addAction(am.act_options)
        file.addSeparator()
        file.addAction(am.act_exit)
        
        # Edit
        edit = menubar.addMenu("&Editar")
        edit.addAction(am.act_undo)
        edit.addAction(am.act_redo)
        edit.addSeparator()
        edit.addAction(am.act_cut)
        edit.addAction(am.act_copy)
        edit.addAction(am.act_paste)
        edit.addSeparator()
        edit.addAction(am.act_delete)
        
        # View
        view = menubar.addMenu("&Ver")
        self.act_toggle_toolbar = QAction("Barra de Formato", self, checkable=True)
        self.act_toggle_toolbar.setChecked(True)
        self.act_toggle_toolbar.triggered.connect(self.toggle_editor_toolbar)
        view.addAction(self.act_toggle_toolbar)
        view.addSeparator()
        view.addAction(am.act_zoom_in)
        view.addAction(am.act_zoom_out)
        view.addSeparator()
        view.addAction(am.act_page_zoom_in)
        view.addAction(am.act_page_zoom_out)
        
        # Tools
        tools = menubar.addMenu("&Herramientas")
        tools.addAction(am.act_theme)
        
        # Help
        help = menubar.addMenu("&Ayuda")
        help.addAction(am.act_about)
        
        # Toolbar
        self.create_extra_toolbars()

    def create_extra_toolbars(self):
        # We need to access main_layout... wait, setup_ui scoped layout locally.
        # But we can access layout via centralWidget().layout()
        layout = self.centralWidget().layout()
        
        # Insert toolbar before splitter (index 1? TitleBar is 0)
        # Format Toolbar
        current_editor = self.tabbed_editor.get_current_editor()
        text_editor = current_editor.text_editor if current_editor else None
        
        self.editor_toolbar = FormatToolbar(self, text_editor)
        self.editor_toolbar.setMovable(False)
        self.editor_toolbar.setFloatable(False)
        self.editor_toolbar.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        
        # Add to layout at index 1 (between TitleBar and Splitter)
        # Except TitleBar is 0. Splitter is... wait setup_ui added Splitter last.
        # Check children count?
        layout.insertWidget(1, self.editor_toolbar)
        
        # Connect tab change
        self.tabbed_editor.tab_widget.currentChanged.connect(self.on_tab_switched)

    def on_tab_switched(self, index):
        # Update toolbar target
        current = self.tabbed_editor.get_current_editor()
        if current:
            self.editor_toolbar.set_editor(current.text_editor)
            # Also update ActionManager context if it cached editor? No, it calls get_active_editor() dynamically.
            # But we might need to update Mode Icon state.
            self.action_manager.update_mode_action_icon()

    def on_sidebar_action(self, action, arg):
        # Delegate to Action Manager logic if possible or handle locally
        if action == "export_pdf":
            self.action_manager.export_note_pdf(arg)
        elif action == "note_deleted":
            if self.tabbed_editor.current_note_id == arg:
                self.tabbed_editor.clear()

    # --- Wrappers that were previously Methods in MainWindow but now delegated or handled differently ---
    
    def on_save_triggered(self):
        # Delegate to action manager logic OR logic is here?
        # Logic touches UI state (is_draft), so maybe keep here or expose state to AM.
        if self.is_draft:
            self.action_manager.save_as_vault() # AM has logic?
            # Wait, AM has save_as_vault logic inside it?
            # I put it in AM.
            return
        
        self.tabbed_editor.save_current_note()

    def toggle_editor_toolbar(self, checked):
        self.editor_toolbar.setVisible(checked)

    def on_sidebar_note_selected(self, note_id, is_folder):
        self.tabbed_editor.save_current_note()
        name = os.path.basename(note_id)
        self.tabbed_editor.load_note(note_id, is_folder, title=name)
        if not is_folder:
            self.config_manager.save_config("last_opened_note", note_id)

    def on_open_in_new_tab(self, note_id, is_folder, title):
        self.tabbed_editor.open_new_tab(note_id, title)

    def on_editor_status(self, msg, timeout):
        if timeout > 0:
            self.statusBar().showMessage(msg, timeout)
        else:
            self.statusBar().showMessage(msg)
            if not msg: self.statusBar().clearMessage()

    # --- Window State & Misc ---
    def setWindowTitle(self, title):
        super().setWindowTitle(title)
        if hasattr(self, 'title_bar'):
            self.title_bar.set_title(title)

    def toggle_maximize_restore(self):
        if self.isMaximized():
            self.showNormal()
            self._is_maximized = False
        else:
            self._normal_geometry = self.geometry()
            self.showMaximized()
            self._is_maximized = True
        if hasattr(self, 'title_bar'):
            self.title_bar.update_maximize_icon(self._is_maximized)

    # --- Event Filter for Resizing ---
    def eventFilter(self, obj, event):
        # Delegate to Resize Handler
        if self.resize_handler.handle_event(obj, event):
            return True

        return super().eventFilter(obj, event)

    # _check_resize_area, _get_edges, _start_system_resize moved to WindowResizeHandler

    def setup_tray_icon(self):
        from PySide6.QtWidgets import QSystemTrayIcon, QMenu
        if not QSystemTrayIcon.isSystemTrayAvailable(): return
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.windowIcon())
        menu = QMenu()
        menu.addAction("Abrir", self.showNormal)
        menu.addAction("Salir", self.force_quit)
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(lambda r: self.showNormal() if r == QSystemTrayIcon.Trigger else None)
        self.tray_icon.show()

    def force_quit(self):
        self._force_quit = True
        self.tray_icon.hide()
        from PySide6.QtWidgets import QApplication
        QApplication.instance().quit()

    def closeEvent(self, event):
        if getattr(self, '_force_quit', False):
             event.accept()
        elif hasattr(self, 'tray_icon') and self.tray_icon.isVisible():
             event.ignore()
             self.hide()
        else:
             QApplication.instance().removeEventFilter(self)
             event.accept()

    def preload_initial_state(self):
        # Preload Logic (Simplified copy from original)
        last_note = self.config_manager.get("last_opened_note", "")
        if last_note and self.fm.file_exists(last_note):
             self.tabbed_editor.note_loaded.connect(self._on_preload_finished)
             title = os.path.basename(last_note)
             self.tabbed_editor.load_note(last_note, is_folder=False, title=title, preload_images=True, async_load=True)
             return
        
        # Fallback
        fallback = None
        for root, dirs, files in os.walk(self.fm.root_path):
             for f in files:
                  if f.endswith('.md'):
                       fallback = self.fm._get_rel_path(os.path.join(root, f))
                       break
             if fallback: break
        
        if fallback:
             self.tabbed_editor.note_loaded.connect(self._on_preload_finished)
             self.tabbed_editor.load_note(fallback, is_folder=False, title=os.path.basename(fallback), preload_images=True, async_load=True)
        else:
             self.ready.emit()

    def _on_preload_finished(self):
        try: self.tabbed_editor.note_loaded.disconnect(self._on_preload_finished)
        except: pass
        
        if self.tabbed_editor.current_note_id:
            self.sidebar.blockSignals(True)
            self.sidebar.select_note(self.tabbed_editor.current_note_id)
            self.sidebar.blockSignals(False)
        self.ready.emit()

    def load_vault(self, path):
        # Full reload logic mostly delegated to switch_vault or re-init
        self.switch_vault(path)

    def switch_vault(self, new_path):
        import sys
        
        # Clean up event filter
        QApplication.instance().removeEventFilter(self)
        
        # Re-init is smoother.
        self.is_draft = False
        self.vault_path = new_path
        
        # Persistence: Save Global Setting
        settings = QSettings()
        settings.setValue("last_vault_path", new_path)
        settings.sync()
        
        self.fm = FileManager(new_path)
        self.config_manager = ConfigManager(self.fm.root_path)
        
        from app.ui.editors.note_editor import NoteEditor
        NoteEditor.clear_image_cache()
        
        # Clear UI
        self.centralWidget().deleteLater()
        self.menuBar().clear()
        
        # Rebuild
        self.setup_ui()
        self.action_manager = ActionManager(self)
        self.setup_menus_and_toolbars()
        
        self.setWindowTitle(f"Cogny - {os.path.basename(new_path)}")
        
        # Re-install filter? The object is the same, so it should persist unless we explicitly removed it? 
        # Actually EventFilter is on SELF. If self is not destroyed, it persists. 
        # But we called removeEventFilter at start of this method just in case.
        QApplication.instance().installEventFilter(self)

    def setup_autosave(self):
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setInterval(2000)
        self.autosave_timer.setSingleShot(True)
        self.autosave_timer.timeout.connect(lambda: self.tabbed_editor.save_current_note(silent=True) if self.tabbed_editor.current_note_id else None)
        self.tabbed_editor.content_changed.connect(self.autosave_timer.start)
