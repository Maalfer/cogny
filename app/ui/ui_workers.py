from PySide6.QtWidgets import QProgressDialog, QFileDialog
from PySide6.QtCore import Qt, QTimer
from app.ui.widgets import ModernInfo, ModernAlert, ModernConfirm
from app.ui.blueprints.workers import ImportWorker, ExportWorker, OptimizeWorker

class UiWorkersMixin:
    def import_obsidian_vault(self):
        # 1. Select Vault Directory
        vault_path = QFileDialog.getExistingDirectory(self, "Seleccionar Bóveda de Obsidian")
        if not vault_path: return

        # 2. Select Destination Database
        import os
        db_path, _ = QFileDialog.getSaveFileName(self, "Guardar Nueva Base de Datos", 
                                            os.path.expanduser("~/Documentos"), 
                                            "Cogny Database (*.cdb)")
        
        if not db_path: return
        if not db_path.endswith(".cdb"): db_path += ".cdb"

        # 3. Switch to the new database (Creates it empty and reloads UI)
        # We assume self.switch_database is available (from UiActionsMixin)
        self.switch_database(db_path)

        # 4. Start Import Process
        self.progress_dialog = QProgressDialog("Importando Bóveda...", "Cancelar", 0, 0, self)
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setCancelButton(None)
        self.progress_dialog.show()

        self.worker = ImportWorker(self.db, vault_path)
        self.worker.progress.connect(self.progress_dialog.setLabelText)
        self.worker.finished.connect(self.on_import_finished)
        self.worker.error.connect(self.on_worker_error)
        self.worker.start()

    def on_import_finished(self):
        if self.progress_dialog: self.progress_dialog.close()
        self.clean_worker()
        self.sidebar.model.load_notes()
        self.editor_area.clear()
        QTimer.singleShot(100, lambda: ModernInfo.show(self, "Éxito", "¡Bóveda importada correctamente!"))

    def export_obsidian_vault(self):
        output_path = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta de Destino para Exportar")
        if not output_path: return

        self.progress_dialog = QProgressDialog("Exportando Bóveda...", "Cancelar", 0, 0, self)
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setCancelButton(None)
        self.progress_dialog.show()

        self.worker = ExportWorker(self.db, output_path)
        self.worker.progress.connect(self.progress_dialog.setLabelText)
        self.worker.finished.connect(self.on_export_finished)
        self.worker.error.connect(self.on_worker_error)
        self.worker.start()

    def on_export_finished(self):
        if self.progress_dialog: self.progress_dialog.close()
        self.clean_worker()
        QTimer.singleShot(100, lambda: ModernInfo.show(self, "Éxito", "¡Bóveda exportada correctamente!"))

    def optimize_database_action(self):
        self.progress_dialog = QProgressDialog("Optimizando Base de Datos...", None, 0, 0, self)
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setCancelButton(None)
        self.progress_dialog.setRange(0, 0)
        self.progress_dialog.show()

        self.worker = OptimizeWorker(self.db)
        self.worker.finished.connect(self.on_optimize_finished)
        self.worker.error.connect(self.on_worker_error)
        self.worker.start()

    def on_optimize_finished(self):
        if self.progress_dialog: self.progress_dialog.close()
        self.clean_worker()
        QTimer.singleShot(100, lambda: ModernInfo.show(self, "Éxito", "Optimización completada."))

    def on_worker_error(self, error_msg):
        if self.progress_dialog: self.progress_dialog.close()
        self.clean_worker()
        ModernAlert.show(self, "Error", f"Ocurrió un error: {error_msg}")

    def clean_worker(self):
        if hasattr(self, "worker") and self.worker:
            self.worker.quit()
            self.worker.wait()
            self.worker.deleteLater()
            self.worker = None
        self.progress_dialog = None
