from PySide6.QtWidgets import QProgressDialog, QFileDialog
from PySide6.QtCore import Qt, QTimer
from app.ui.widgets import ModernInfo, ModernAlert, ModernConfirm
from app.ui.blueprints.workers import ImportWorker, ExportWorker, OptimizeWorker

class UiWorkersMixin:
    def import_obsidian_vault(self):
        ret = ModernConfirm.show(self, "Confirmar Importación", 
                                  "Importar una Bóveda de Obsidian BORRARÁ todas las notas actuales.\\n\\n¿Estás seguro de que quieres continuar?",
                                  "Sí", "Cancelar")
        if not ret: return

        vault_path = QFileDialog.getExistingDirectory(self, "Seleccionar Bóveda de Obsidian")
        if not vault_path: return

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
