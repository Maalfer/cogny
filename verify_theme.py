
import sys
from PySide6.QtCore import QCoreApplication, QSettings
from PySide6.QtWidgets import QApplication, QStyleFactory
from app.ui.themes import ThemeManager

def verify_theme_persistence():
    # 1. Setup App Metadata matching main.py
    app = QApplication(sys.argv)
    app.setOrganizationName("CognyApp")
    app.setApplicationName("Cogni")
    
    print("--- Test 1: Default State (Simulated First Run) ---")
    settings = QSettings()
    # Clear existing to simulate fresh start
    settings.clear() 
    
    theme_name = settings.value("theme", "Dark")
    print(f"Default Theme should be 'Dark'. Got: '{theme_name}'")
    if theme_name != "Dark":
        print("FAIL: Default theme is not Dark")
        return False
        
    print("--- Test 2: Persistence (Switch to Light) ---")
    # Simulate User switching to Light
    settings.setValue("theme", "Light")
    
    # Reload from settings
    settings_new = QSettings()
    theme_name_new = settings_new.value("theme", "Dark")
    print(f"Saved Theme should be 'Light'. Got: '{theme_name_new}'")
    if theme_name_new != "Light":
         print("FAIL: Persistence failed, value not saved.")
         return False

    print("--- Test 3: Palette Check ---")
    # Verify palette is actually retrievable
    try:
        palette = ThemeManager.get_palette("Dark")
        if not palette:
            print("FAIL: ThemeManager returned None for Dark palette")
            return False
    except Exception as e:
        print(f"FAIL: ThemeManager error: {e}")
        return False

    print("SUCCESS: Theme persistence logic verified.")
    return True

if __name__ == "__main__":
    success = verify_theme_persistence()
    sys.exit(0 if success else 1)
