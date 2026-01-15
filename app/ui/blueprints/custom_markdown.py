from markdown.extensions import Extension
from markdown.inlinepatterns import InlineProcessor
from markdown.blockprocessors import BlockProcessor
import xml.etree.ElementTree as etree
import re

# Pattern for internal images: <img src="image://db/123" />
# We want to match this and replace it with a DIV > IMG wrapper.
IMAGE_PATTERN = r'(<img\s+src="image://db/(\d+)"\s*/>)'

# Pattern for attachments: <a href="attachment://123">filename</a>
# Or simplistically just detecting the scheme if we want to add an icon?
# Current logic: preserve it.
# If we want to OPTIMIZE, we can leave attachments alone if Markdown doesn't break them.
# The previous issue said placeholders prevented "double underscore" issues.
# If the URL contains underscores, Markdown might bold it.
# But image://db/123 has no underscores. 
# Filenames might?
# Let's keep a processor for attachments to be safe and consistent.
ATTACHMENT_PATTERN = r'(<a\s+href="attachment://(\d+)"[^>]*>.*?</a>)'

class InternalImageProcessor(InlineProcessor):
    def handleMatch(self, m, data):
        # m.group(1) is the whole tag <img ... />
        # m.group(2) is the ID
        img_id = m.group(2)
        
        # Create Element: <div><img ... /></div>
        div = etree.Element('div')
        div.set('style', 'margin: 10px 0;') # As requested in previous iterations
        
        img = etree.SubElement(div, 'img')
        img.set('src', f'image://db/{img_id}')
        img.set('style', 'max-width: 600px; border-radius: 12px; margin-top: 15px; margin-bottom: 15px;') 
        # Note: CSS classes in ThemeManager also apply to 'img', but inline styles override/add.
        # Use inline for specific logic if needed, or rely on ThemeManager.
        # ThemeManager applies to ALL img. 
        # Here we adding a wrapper div.
        
        return div, m.start(0), m.end(0)

class InternalAttachmentProcessor(InlineProcessor):
    def handleMatch(self, m, data):
        # m.group(0) is the whole tag
        # Just return it as is? Or parse it into an Element?
        # Returning string might get re-parsed?
        # InlineProcessor must return an Element or (None, None, None).
        
        # We need to reconstruct the atomic HTML element.
        # This is hard because the inner content of <a> might contain anything.
        # Regex parsing HTML is fragile.
        
        # ALTERNATIVE: Use a 'Preprocessor' to swap these sensitive tags 
        # into a special proprietary block that Markdown ignores, 
        # then a 'Postprocessor' to swap back?
        # That is exactly what the previous code did (Placeholders).
        # The user asked for "Better Integration".
        
        # "Better Integration" usually means using the tree.
        # But if the input is ALREADY HTML strings mixed with Markdown, 
        # python-markdown's 'md_in_html' extension is technically the standard way handling mixed content.
        # But we want specific transformation for Images (wrapping in div).
        
        # Let's stick to the InlineProcessor for Images because they are self-closing and simple.
        # For attachments, it's safer to use the existing placeholder strategy OR 
        # trust that Markdown won't break `<a href="...">`.
        # Underscores in href="" ARE ignored by standard Markdown.
        # Underscores in the *body* of the link: <a>foo_bar</a> -> <a>foo<em>bar</em></a>?
        # Yes, standard markdown parses inside HTML blocks unless `markdown.extensions.extra` -> `markdown.extensions.md_in_html` usage.
        
        # Let's try to just handle Images neatly first.
        # Attachments might be fine without special handling if we assume they are standard HTML.
        
        pass

class CognyInternalExtension(Extension):
    def extendMarkdown(self, md):
        # Register new pattern.
        # Priority > 175 (RawHtml) to catch it before it's treated as generic HTMl.
        md.inlinePatterns.register(InternalImageProcessor(IMAGE_PATTERN, md), 'cogny_image', 180)

def make_extension(**kwargs):
    return CognyInternalExtension(**kwargs)
