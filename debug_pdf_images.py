from weasyprint import HTML, CSS
import logging

# Setup logging to see WeasyPrint internal warnings (it logs missing images)
logger = logging.getLogger('weasyprint')
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
logger.addHandler(handler)

def custom_fetcher(url, timeout=10, ssl_context=None):
    print(f"DEBUG: Fetcher called with URL: {url}")
    if url.startswith("image://db/"):
        print("DEBUG: Detected internal image!")
        # Return a simple red pixel
        return {
            'string': b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT\x08\xd7c\xf8\xcf\xc0\x00\x00\x03\x01\x01\x00\x18\xdd\x8d\xb0\x00\x00\x00\x00IEND\xaeB`\x82',
            'mime_type': 'image/png'
        }
    return {
        'string': b'', 
        'mime_type': 'text/html' # Fallback
    }

html_content = """
<!DOCTYPE html>
<html>
<body>
    <h1>Test</h1>
    <p>Image below:</p>
    <div style="margin: 10px 0;">
        <img src="image://db/123" style="width: 100px; height: 100px;" />
    </div>
</body>
</html>
"""

print("Starting generation...")
try:
    HTML(string=html_content, base_url=".", url_fetcher=custom_fetcher).write_pdf(
        "test_debug.pdf"
    )
    print("PDF generated successfully.")
except Exception as e:
    print(f"Error: {e}")
