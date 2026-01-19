import os
import shutil
import zipfile
import tarfile
import subprocess
from datetime import datetime

class BackupManager:
    """
    Manages the creation of backups for the vault.
    Supports .zip (with optional password via system zip command) and .tar.
    """
    def __init__(self, vault_path: str):
        self.vault_path = os.path.abspath(vault_path)

    def create_backup(self, output_path: str, format_type: str, password: str = None) -> tuple[bool, str]:
        """
        Creates a backup.
        :param output_path: Destination path (e.g. /home/user/backup.zip)
        :param format_type: 'zip' or 'tar'
        :param password: Password for zip (optional). Not supported for tar.
        :return: (Success, Message)
        """
        try:
            if format_type == 'zip':
                return self._create_zip(output_path, password)
            elif format_type == 'tar':
                return self._create_tar(output_path)
            else:
                return False, "Formato no soportado."
        except Exception as e:
            return False, str(e)

    def _create_zip(self, output_path: str, password: str = None) -> tuple[bool, str]:
        """
        Creates a ZIP backup. Uses system 'zip' command if password is provided.
        """
        if password:
            # Check availability of 'zip' command
            if shutil.which("zip") is None:
                return False, "El comando 'zip' no está instalado. Instálalo con 'sudo apt install zip' para usar contraseña."
            
            # Use subprocess to call zip with password
            # zip -r -P password output.zip .
            try:
                # We rename the root folder in the zip to the vault name
                vault_name = os.path.basename(self.vault_path)
                parent_dir = os.path.dirname(self.vault_path)
                
                # Command construction
                # We run from parent dir to include the vault folder name
                cmd = ["zip", "-r", "-P", password, output_path, vault_name, "-x", f"{vault_name}/.obsidian/*"]
                
                result = subprocess.run(cmd, cwd=parent_dir, capture_output=True, text=True)
                
                if result.returncode == 0:
                    return True, f"Respaldo (protegido) creado en: {output_path}"
                else:
                    return False, f"Error de zip: {result.stderr}"
            except Exception as e:
                return False, f"Error ejecutando zip: {str(e)}"
        
        else:
            # Use Python's zipfile for standard zip
            try:
                base_dir = os.path.basename(self.vault_path)
                with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for root, dirs, files in os.walk(self.vault_path):
                        # Exclude .obsidian or other systemic folders if needed?
                        # User wants FULL backup, so includes everything usually.
                        
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.join(base_dir, os.path.relpath(file_path, self.vault_path))
                            zipf.write(file_path, arcname)
                            
                return True, f"Respaldo creado en: {output_path}"
            except Exception as e:
                return False, str(e)

    def _create_tar(self, output_path: str) -> tuple[bool, str]:
        """
        Creates a TAR backup (tar.gz).
        """
        try:
            base_dir = os.path.basename(self.vault_path)
            with tarfile.open(output_path, "w:gz") as tar:
                tar.add(self.vault_path, arcname=base_dir)
            return True, f"Respaldo creado en: {output_path}"
        except Exception as e:
            return False, str(e)
