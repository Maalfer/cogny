import sys
import os
import subprocess
from PySide6.QtCore import QUrl

def show_in_explorer(path_or_url):
    """
    Opens the system file explorer and selects the file, or opens the folder.
    Supports file:// URLs and absolute paths.
    """
    path = str(path_or_url)
    if path.startswith("file://"):
         path = QUrl(path).toLocalFile()
    
    path = os.path.abspath(path)
    
    if not os.path.exists(path):
         print(f"ERROR: Path not found: {path}")
         return

    if sys.platform == 'win32':
        subprocess.run(['explorer', '/select,', os.path.normpath(path)])
    elif sys.platform == 'darwin':
        subprocess.run(['open', '-R', path])
    else:
        # Linux
        try:
            # If it's a file, try to select it if file manager supports it, or just open parent
            # Standard 'xdg-open' opens the default app for the file type (which opens image viewer for images)
            # We want FILE EXPLORER.
            
            # Common file managers usually accept directory to open.
            target = path
            if os.path.isfile(path):
                target = os.path.dirname(path)
            
            # Safe generic fallback: open the folder containing the item.
            # dbus methods are cleaner but complex. 
            
            # 1. Try 'gio open' (GNOME/Cosmic native)
            if subprocess.call(['which', 'gio'], stdout=subprocess.DEVNULL) == 0:
                 subprocess.Popen(['gio', 'open', target])
            else:
                 # 2. Fallback to xdg-open
                 subprocess.Popen(['xdg-open', target])
        except Exception as e:
            print(f"Error opening explorer: {e}")
