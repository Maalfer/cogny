import os
import json
from pathlib import Path
from PySide6.QtCore import QByteArray

class ConfigManager:
    """
    Manages vault-specific configuration stored in .cogny/config.json
    """
    def __init__(self, vault_root: str):
        self.vault_root = vault_root
        self.config_dir = vault_root # Config is now in root
        self.config_file = os.path.join(self.vault_root, "config.json")
        self._config_cache = {}
        self.load_config()

    def load_config(self) -> dict:
        """Loads configuration from disk."""
        if not os.path.exists(self.config_file):
            self._config_cache = {}
            return {}

        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self._config_cache = json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
            self._config_cache = {}
            
        return self._config_cache

    def save_config(self, key: str = None, value = None, items: dict = None):
        """
        Saves configuration. Can update a single key-value pair or multiple items.
        If both are None, just flushes cache to disk.
        """
        if items:
            self._config_cache.update(items)
        elif key is not None:
             self._config_cache[key] = value


        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self._config_cache, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get(self, key: str, default = None):
        return self._config_cache.get(key, default)

    # --- QByteArray Helpers (Geometry/State) ---
    # JSON cannot store binary bytes natively. We hex encode them.
    
    def set_window_state(self, geometry: QByteArray, state: QByteArray):
        data = {
            "window_geometry": geometry.toHex().data().decode('ascii'),
            "window_state": state.toHex().data().decode('ascii')
        }
        self.save_config(items=data)
        
    def get_window_geometry(self) -> QByteArray:
        hex_str = self.get("window_geometry", "")
        if hex_str:
            return QByteArray.fromHex(hex_str.encode('ascii'))
        return QByteArray()

    def get_window_state(self) -> QByteArray:
        hex_str = self.get("window_state", "")
        if hex_str:
            return QByteArray.fromHex(hex_str.encode('ascii'))
        return QByteArray()
