from PySide6.QtWidgets import QProgressDialog, QFileDialog
from PySide6.QtCore import Qt, QTimer
from app.ui.widgets import ModernInfo, ModernAlert, ModernConfirm

class UiWorkersMixin:
    def import_obsidian_vault(self):
        # Deprecated: "Importing" is just opening the folder now.
        ModernInfo.show(self, "Información", 
            "La importación ya no es necesaria. Simplemente usa 'Abrir Bóveda' y selecciona la carpeta de tu bóveda Obsidian.\\n\\nCogny ahora trabaja directamente con archivos Markdown.")

    def export_obsidian_vault(self):
        # Deprecated: The vault is already files.
        ModernInfo.show(self, "Información",
            "Tu bóveda ya está en formato compatible (Markdown). Simplemente copia la carpeta de tu bóveda si deseas moverla.")

    def on_import_finished(self):
        pass

    def on_export_finished(self):
        pass

    def optimize_database_action(self):
        pass

    def on_optimize_finished(self):
        pass

    def on_worker_error(self, error_msg):
        pass

    def clean_worker(self):
        pass
