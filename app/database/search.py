from typing import List, Tuple
import re
import sqlite3

class SearchMixin:
    def get_detailed_statistics(self) -> dict:
        """Calculate detailed statistics for the vault."""
        stats = {
            "total_notes": 0,
            "total_subnotes": 0,
            "total_images": 0,
            "total_code_fragments": 0,
            "total_words": 0,
            "total_letters": 0
        }
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 1. Counts
        cursor.execute("SELECT COUNT(*) FROM notes")
        stats["total_notes"] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM notes WHERE parent_id IS NOT NULL")
        stats["total_subnotes"] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM images")
        stats["total_images"] = cursor.fetchone()[0]
        
        # 2. Content Analysis
        cursor.execute("SELECT content FROM notes")
        rows = cursor.fetchall()
        
        import re
        
        for row in rows:
            content = row[0]
            if not content:
                continue
                
            # Count Code Blocks
            # Look for ``` start tags (standard markdown style)
            # Since content is HTML, they might be plain text or wrapped.
            # We search for the pattern.
            code_blocks = len(re.findall(r"```", content))
            # Blocks have start and end, so strictly strictly divisible by 2?
            # Or just count occurrences / 2?
            # Or count "starts"? Text editor logic counts starts.
            # User wants "fragments". 
            # If we assume correctly formatted, ```...``` is one fragment.
            # So occurrences / 2 works if valid.
            # Let's count *starts* approximately (odd occurrences?).
            # Actually, `editor.py` counts starts: txt.startswith("```").
            # But here we act on the whole text.
            # Let's count *pairs*?
            # Ideally: len(re.findall(r"```[\s\S]*?```", content))
            # But simpler: count ``` and integer divide by 2.
            stats["total_code_fragments"] += (code_blocks // 2)

            # Strip HTML for words/letters
            # Remove tags
            text_only = re.sub(r'<[^>]+>', ' ', content)
            
            # Words
            words = text_only.split()
            stats["total_words"] += len(words)
            
            # Letters (non-whitespace)
            # Remove all whitespace from text_only
            letters = re.sub(r'\s+', '', text_only)
            stats["total_letters"] += len(letters)
            
        conn.close()
        return stats

    def search_notes_fts(self, query: str) -> List[Tuple]:
        """Search notes using FTS5 match. (Legacy simple prefix search)"""
        # ... existing logic wrapped or reused ...
        sanitized = query.replace('"', '""').strip()
        if not sanitized:
             return []
        fts_query = f'"{sanitized}"*' 
        return self.advanced_search(fts_query)

    def advanced_search(self, fts_query: str) -> List[Tuple]:
        """
        Execute a raw FTS5 query.
        Returns: [(note_id, title, snippet)]
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
             # We use snippet() function for context
             # snippet(table, column_index, start_marker, end_marker, ellipses, max_tokens)
             # Column 2 is content (0=title, 1=content? No, schema: rowid, title, content? FTS table is virtual.)
             # notes_fts columns: title, content.
             # snippet(notes_fts, 1, '<b>', '</b>', '...', 20) -> Snippet of content column
             
             sql = """
                 SELECT rowid, title, snippet(notes_fts, 1, '<b>', '</b>', '...', 15) as snip, rank
                 FROM notes_fts 
                 WHERE notes_fts MATCH ? 
                 ORDER BY rank
             """
             cursor.execute(sql, (fts_query,))
             rows = cursor.fetchall()
             return rows
        except sqlite3.OperationalError as e:
             print(f"FTS Error: {e}")
             return []
        finally:
             conn.close()
