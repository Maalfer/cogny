from PySide6.QtCore import QSettings

class UiStateMixin:
    def closeEvent(self, event):
        # Save State to ConfigManager if available
        if hasattr(self, 'config_manager'):
            # 1. Window State (Geometry + Toolbar/Dock Layout)
            self.config_manager.set_window_state(self.saveGeometry(), self.saveState())
            
            # 2. Last Note
            if hasattr(self, 'tabbed_editor') and self.tabbed_editor.current_note_id:
                 self.config_manager.save_config("last_note_id", self.tabbed_editor.current_note_id)
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

    def on_open_in_new_tab(self, note_id, is_folder, title):
        """Opens a note in a new tab."""
        print(f"DEBUG MainWindow: on_open_in_new_tab received - note_id={note_id}, title={title}")
        if hasattr(self, 'tabbed_editor'):
            self.tabbed_editor.open_note_in_new_tab(note_id, is_folder, title)
    
    def on_tab_switched(self, index):
        """Updates the format toolbar when switching tabs."""
        if index >= 0 and hasattr(self, 'tabbed_editor'):
            current_editor = self.tabbed_editor.get_current_editor()
            if current_editor and hasattr(self, 'editor_toolbar'):
                # Update toolbar to point to new editor's text_editor
                self.editor_toolbar.text_editor = current_editor.text_editor
