from PySide6.QtCore import QSettings

class UiStateMixin:
    def closeEvent(self, event):
        # Save State to ConfigManager if available
        if hasattr(self, 'config_manager'):
            # 1. Window State (Geometry + Toolbar/Dock Layout)
            self.config_manager.set_window_state(self.saveGeometry(), self.saveState())
            
            # 2. Last Note
            if hasattr(self, 'editor_area') and self.editor_area.current_note_id:
                 self.config_manager.save_config("last_note_id", self.editor_area.current_note_id)
            else:
                 self.config_manager.save_config("last_note_id", None)
                 
        super().closeEvent(event)

    def restore_state(self):
        if not hasattr(self, 'config_manager'):
            return

        # 1. Restore Window State
        geo_data = self.config_manager.get_window_geometry()
        state_data = self.config_manager.get_window_state()
        
        if not geo_data.isEmpty():
            self.restoreGeometry(geo_data)
        if not state_data.isEmpty():
            self.restoreState(state_data)
            
        # 2. Restore Last Note (Handled by Sidebar mostly via signal, or manual call)
        # 2. Restore Last Note -> REMOVED to avoid double-loading with Splash Preload logic.
        # [CRITICAL] DO NOT UNCOMMENT OR RE-IMPLEMENT note RESTORATION HERE.
        # The Splash Screen now handles the "initial note load" to ensure it happens before the window is shown.
        # See MainWindow.preload_initial_state
        pass
