from PySide6.QtWidgets import QMainWindow, QToolBar
from PySide6.QtGui import QIcon
from PySide6.QtCore import QSettings, Signal
import os

from app.storage.file_manager import FileManager
from app.ui.ui_state import UiStateMixin
from app.ui.ui_theme import UiThemeMixin
from app.ui.ui_actions import UiActionsMixin
from app.ui.ui_setup import UiSetupMixin

class MainWindow(UiStateMixin, UiThemeMixin, UiActionsMixin, UiSetupMixin, QMainWindow):
    ready = Signal()
    def __init__(self, vault_path=None, is_draft=False):
        super().__init__()
        
        # Frameless Window for Custom Title Bar
        from PySide6.QtCore import Qt
        self.setWindowFlags(Qt.FramelessWindowHint)
        
        # Window state tracking
        self._is_maximized = False
        self._normal_geometry = None
        self._is_resizing = False
        self._resize_direction = None
        self._resize_margin = 5  # pixels for resize detection
        
        self.is_draft = is_draft
        self.vault_path = vault_path
        
        display_name = 'Borrador' if is_draft else (os.path.basename(vault_path) if vault_path else 'Sin Bóveda')
        self.setWindowTitle(f"Cogny - {display_name}")
        self.resize(1200, 800)
        
        # Resolve Assets Path
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        icon_path = os.path.join(base_dir, "assets", "logo.png")
        self.setWindowIcon(QIcon(icon_path))

        # File/Vault Setup
        if not vault_path:
             # Fallback or empty state
             vault_path = os.path.expanduser("~/Documentos")
             
        self.fm = FileManager(vault_path)
        
        # Initialize Config Manager
        from app.storage.config_manager import ConfigManager
        self.config_manager = ConfigManager(self.fm.root_path)
        
        self.setup_ui()
        
        # Apply Initial Theme (Stylesheets)
        # settings = QSettings() -> Removed global settings for theme
        current_theme = self.config_manager.get("theme", "Dark")
        self.switch_theme(current_theme)
        
        # Initialize System Tray
        self.setup_tray_icon()
    
    def setWindowTitle(self, title):
        """Override to also update custom title bar."""
        super().setWindowTitle(title)
        if hasattr(self, 'title_bar'):
            self.title_bar.set_title(title)

    def preload_initial_state(self):
        """Called by splash to pre-load content before showing window."""
        # [CRITICAL] PRELOAD LOGIC - DO NOT MODIFY
        # This function is the ONLY place where the initial note should be loaded.
        # It MUST use async_load=True to keep the Splash Screen animations running.
        # It MUST handle the Fallback scenario (finding any note) if the last note is missing.
        # 1. Check for last opened note in Vault Config
        last_note = self.config_manager.get("last_opened_note", "")
        
        if last_note and self.fm.file_exists(last_note): # Check existence
             print(f"DEBUG: Found last note: {last_note}. Starting preload...")
             # Connect to editor area loaded signal
             self.editor_area.note_loaded.connect(self._on_preload_finished)
             
             # Determine title (basename)
             # Determine title (basename)
             title = os.path.basename(last_note)
             
             # Trigger Load Synchronously
             # We use async_load=True to allow the Event Loop to run (animations, splash screen updates)
             # while the note loads in the background. The 'ready' signal will still only be emitted when done.
             self.editor_area.load_note(last_note, is_folder=False, title=title, preload_images=True, async_load=True)
             return

        # Fallback: If no last note, try to find ANY note to warm up the editor
        # This prevents the "First Note Slow" issue by ensuring the engine is initialized.
        print(f"DEBUG: Last note '{last_note}' not found. Searching for fallback...")
        
        fallback_note = None
        # Use FileManager to list files or search
        # Simple walk to find first .md
        for root, dirs, files in os.walk(self.fm.root_path):
             # Skip hidden
             dirs[:] = [d for d in dirs if not d.startswith('.')]
             for f in files:
                  if f.endswith('.md'):
                       fallback_note = self.fm._get_rel_path(os.path.join(root, f))
                       break
             if fallback_note:
                  break
                  
        if fallback_note:
             print(f"DEBUG: Found fallback note: {fallback_note}. Preloading...")
             self.editor_area.note_loaded.connect(self._on_preload_finished)
             title = os.path.basename(fallback_note)
             self.editor_area.load_note(fallback_note, is_folder=False, title=title, preload_images=True, async_load=True)
        else:
             print("DEBUG: No notes found in vault. Ready immediately.")
             # Nothing to load, ready immediately
             self.ready.emit()
             
    def _on_preload_finished(self, success):
        self.editor_area.note_loaded.disconnect(self._on_preload_finished)
        
        # [CRITICAL] SIDEBAR SYNC
        # We MUST block signals to prevent the Sidebar from triggering a "selection changed" event,
        # which would cause a circular note reload and double-loading.
        if self.editor_area.current_note_id:
            try:
                self.sidebar.blockSignals(True)
                self.sidebar.select_note(self.editor_area.current_note_id)
            finally:
                self.sidebar.blockSignals(False)
        
        self.ready.emit()

    def load_vault(self, vault_path):
        import os
        from app.storage.file_manager import FileManager
        
        # 1. Update Settings
        settings = QSettings()
        settings.setValue("last_vault_path", vault_path)
        
        # 2. Init new File Manager
        self.fm = FileManager(vault_path)
        self.vault_path = vault_path
        
        # 3. Update Child Components
        self.sidebar.set_file_manager(self.fm)
        self.editor_area.set_file_manager(self.fm)
        
        # 4. Update Title
        self.setWindowTitle(f"Cogny - {os.path.basename(vault_path)}")
        
        # 5. Clear Image Cache
        from app.ui.editor import NoteEditor
        NoteEditor.clear_image_cache()

    def switch_vault(self, new_path):
        # 1. Update Settings
        settings = QSettings()
        settings.setValue("last_vault_path", new_path)
        
        # Clear Draft Flag
        self.is_draft = False
        self.vault_path = new_path
        
        # 2. Re-initialize File Manager
        self.fm = FileManager(new_path)
        
        # Re-init Config Manager
        from app.storage.config_manager import ConfigManager
        self.config_manager = ConfigManager(self.fm.root_path)
        
        # 3. Clear image cache
        from app.ui.editor import NoteEditor
        NoteEditor.clear_image_cache()
        
        # 4. Restart UI
        # We can either full restart or just reload components.
        # Clearing splitter allows recreating Sidebar and EditorArea with new fm
        self.menuBar().clear()
        for toolbar in self.findChildren(QToolBar):
            self.removeToolBar(toolbar)
            
        # Clear Central Widget (Splitter)
        if self.centralWidget():
            self.centralWidget().deleteLater()
            
        # Re-run setup
        self.setup_ui()
            
        # Update Title
        self.setWindowTitle(f"Cogny - {os.path.basename(new_path)}")
    
    def toggle_maximize_restore(self):
        """Toggle between maximized and normal window state."""
        if self.isMaximized():
            self.showNormal()
            self._is_maximized = False
        else:
            self._normal_geometry = self.geometry()
            self.showMaximized()
            self._is_maximized = True
        
        # Update title bar icon
        if hasattr(self, 'title_bar'):
            self.title_bar.update_maximize_icon(self._is_maximized)
    
    def _get_resize_direction(self, pos):
        """Determine resize direction based on mouse position."""
        margin = self._resize_margin
        rect = self.rect()
        
        on_left = pos.x() <= margin
        on_right = pos.x() >= rect.width() - margin
        on_top = pos.y() <= margin
        on_bottom = pos.y() >= rect.height() - margin
        
        if on_top and on_left:
            return 'top-left'
        elif on_top and on_right:
            return 'top-right'
        elif on_bottom and on_left:
            return 'bottom-left'
        elif on_bottom and on_right:
            return 'bottom-right'
        elif on_left:
            return 'left'
        elif on_right:
            return 'right'
        elif on_top:
            return 'top'
        elif on_bottom:
            return 'bottom'
        return None
    
    def mousePressEvent(self, event):
        """Handle mouse press for window resizing."""
        from PySide6.QtCore import Qt
        if event.button() == Qt.LeftButton and not self.isMaximized():
            self._resize_direction = self._get_resize_direction(event.pos())
            if self._resize_direction:
                self._is_resizing = True
                self._resize_start_geometry = self.geometry()
                self._resize_start_pos = event.globalPosition().toPoint()
                event.accept()
                return
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Handle mouse move for window resizing and cursor changes."""
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QCursor
        
        if self._is_resizing and self._resize_direction:
            delta = event.globalPosition().toPoint() - self._resize_start_pos
            geo = self._resize_start_geometry
            new_geo = geo
            
            # Calculate new geometry based on resize direction
            if 'left' in self._resize_direction:
                new_geo.setLeft(geo.left() + delta.x())
            if 'right' in self._resize_direction:
                new_geo.setRight(geo.right() + delta.x())
            if 'top' in self._resize_direction:
                new_geo.setTop(geo.top() + delta.y())
            if 'bottom' in self._resize_direction:
                new_geo.setBottom(geo.bottom() + delta.y())
            
            # Set minimum size
            if new_geo.width() >= self.minimumWidth() and new_geo.height() >= self.minimumHeight():
                self.setGeometry(new_geo)
            event.accept()
        elif not self.isMaximized():
            # Change cursor based on position
            direction = self._get_resize_direction(event.pos())
            if direction:
                if direction in ['top', 'bottom']:
                    self.setCursor(QCursor(Qt.SizeVerCursor))
                elif direction in ['left', 'right']:
                    self.setCursor(QCursor(Qt.SizeHorCursor))
                elif direction in ['top-left', 'bottom-right']:
                    self.setCursor(QCursor(Qt.SizeFDiagCursor))
                elif direction in ['top-right', 'bottom-left']:
                    self.setCursor(QCursor(Qt.SizeBDiagCursor))
            else:
                self.setCursor(QCursor(Qt.ArrowCursor))
        
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release to stop resizing."""
        self._is_resizing = False
        self._resize_direction = None
        super().mouseReleaseEvent(event)

    def setup_tray_icon(self):
        """Initialize System Tray Icon with Context Menu."""
        from PySide6.QtWidgets import QSystemTrayIcon, QMenu
        from PySide6.QtGui import QAction

        # Check if System Tray is available
        if not QSystemTrayIcon.isSystemTrayAvailable():
            print("WARNING: System Tray not available on this system.")
            return

        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.windowIcon())
        
        # Create Context Menu
        tray_menu = QMenu()
        
        open_action = QAction("Abrir Cogny", self)
        open_action.triggered.connect(self.show_normal_and_raise)
        tray_menu.addAction(open_action)
        
        tray_menu.addSeparator()
        
        quit_action = QAction("Salir", self)
        quit_action.triggered.connect(self.force_quit)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.tray_icon.show()
        
        # Flag to distinguish between minimize-to-tray and actual quit
        self._force_quit = False

    def on_tray_icon_activated(self, reason):
        """Handle tray icon clicks."""
        from PySide6.QtWidgets import QSystemTrayIcon
        
        if reason == QSystemTrayIcon.Trigger:
            if self.isVisible():
                if self.isMinimized():
                    self.show_normal_and_raise()
                else:
                    self.hide()
            else:
                self.show_normal_and_raise()

    def show_normal_and_raise(self):
        """Restore window and bring to front."""
        self.show()
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def force_quit(self):
        """Fully quit the application."""
        self._force_quit = True
        self.tray_icon.hide() # Ensure icon disappears immediately
        from PySide6.QtWidgets import QApplication
        QApplication.instance().quit()

    def closeEvent(self, event):
        """Override close event to minimize to tray unless force quitting."""
        # If we are effectively quitting (force_quit called or just normal close if no tray)
        if getattr(self, '_force_quit', False):
             event.accept()
        elif hasattr(self, 'tray_icon') and self.tray_icon.isVisible():
             event.ignore()
             self.hide()
        else:
             event.accept()
