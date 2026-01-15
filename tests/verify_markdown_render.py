import sys
import os

# Make sure we can import 'app'
current_dir = os.getcwd()
if current_dir.endswith("tests"):
    project_root = os.path.dirname(current_dir)
else:
    project_root = current_dir
sys.path.append(project_root)

from app.ui.blueprints.markdown import MarkdownRenderer

def test_markdown_features():
    # 1. Table
    table_md = """
| Header 1 | Header 2 |
|----------|----------|
| Cell 1   | Cell 2   |
"""
    html_table = MarkdownRenderer.process_markdown_content(table_md)
    print("--- Table HTML ---")
    print(html_table)
    if "<table>" in html_table and "<thead>" in html_table:
        print("PASS: Table rendering")
    else:
        print("FAIL: Table rendering")

    # 2. Code Block (Python)
    code_md = """
```python
def foo():
    print("bar")
```
"""
    html_code = MarkdownRenderer.process_markdown_content(code_md)
    print("\n--- Code Block HTML ---")
    print(html_code)
    # Check for inline styles (e.g., color: ...) which indicate codehilite is working with noclasses=True
    if 'style="' in html_code:
        print("PASS: Code highlighting (inline styles detected)")
    else:
        print("FAIL: Code highlighting (no inline styles)")

if __name__ == "__main__":
    test_markdown_features()
