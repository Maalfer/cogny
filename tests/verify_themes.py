import sys
import os

# Add project root to path
# Assuming this is run from the project root or tests/ dir, we need to ensure project root is in path.
# If run from 'tests/', '..' is root. If run from root, '.' is root.
# Let's try to detect.
current_dir = os.getcwd()
if current_dir.endswith("tests"):
    project_root = os.path.dirname(current_dir)
else:
    project_root = current_dir

sys.path.append(project_root)

try:
    from app.ui.themes import ThemeManager
    print("Successfully imported ThemeManager")
    
    dark_style = ThemeManager.get_editor_style("Dark")
    print(f"Dark Style generated successfully. Length: {len(dark_style)}")
    
    light_style = ThemeManager.get_editor_style("Light")
    print(f"Light Style generated successfully. Length: {len(light_style)}")
    
    # Basic check for expected CSS content
    if "NoteEditor {" in dark_style and "background-color: #1e1e1e" in dark_style:
         print("PASS: Dark Theme Basic Check")
    else:
         print("FAIL: Dark Theme Basic Check")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
