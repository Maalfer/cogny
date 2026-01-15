"""
Global image cache for the application.

This module provides a singleton cache that stores processed images
in the SQLite database, avoiding redundant image processing and ensuring
cache portability with the database file.
"""

from collections import OrderedDict
from PySide6.QtGui import QImage
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QMutex, QMutexLocker


class GlobalImageCache:
    """
    Singleton image cache with LRU eviction and SQLite persistence.
    
    Stores processed QImage objects in memory and persists them to
    the database's image_cache table for cross-session availability.
    """
    
    _instance = None
    _db_path = None
    
    def __init__(self):
        """Initialize the cache. Use get_instance() instead of direct instantiation."""
        self._cache = OrderedDict()
        self._max_size = 100  # Maximum number of cached images in memory
        self._mutex = QMutex()
    
    @classmethod
    def get_instance(cls):
        """Get the singleton instance of the global image cache."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def set_db_path(cls, db_path: str):
        """Set the database path and load cache from database."""
        cls._db_path = db_path
        instance = cls.get_instance()
        instance._load_from_db()
    
    def _load_from_db(self):
        """Load cached images from database on startup."""
        locker = QMutexLocker(self._mutex)
        if not self._db_path:
            return
        
        try:
            import sqlite3
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            
            # Load most recent cached images (up to max_size)
            cursor.execute("""
                SELECT image_id, processed_data 
                FROM image_cache 
                ORDER BY cached_at DESC 
                LIMIT ?
            """, (self._max_size,))
            
            for image_id, blob in cursor.fetchall():
                if blob:
                    img = QImage()
                    if img.loadFromData(QByteArray(blob)):
                        key = f"image://db/{image_id}"
                        self._cache[key] = img
            
            conn.close()
        except Exception as e:
            print(f"Failed to load image cache from database: {e}")
    
    def save_to_db(self):
        """Save all in-memory cached images to database."""
        locker = QMutexLocker(self._mutex)
        if not self._db_path:
            return
        
        try:
            import sqlite3
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            
            # We need to copy items to avoid runtime error if cache changes during iteration
            # (though mutex should prevent that from other threads, but safe logic is good)
            items = list(self._cache.items())

            for key, qimage in items:
                # Extract image_id from key "image://db/123"
                image_id = int(key.split("/")[-1])
                
                # Convert QImage to PNG bytes
                ba = QByteArray()
                buffer = QBuffer(ba)
                buffer.open(QIODevice.WriteOnly)
                qimage.save(buffer, "PNG")
                blob = bytes(ba)
                
                # Insert or replace in database
                cursor.execute("""
                    INSERT OR REPLACE INTO image_cache (image_id, processed_data, cached_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                """, (image_id, blob))
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Failed to save image cache to database: {e}")
    
    def get(self, image_id: int) -> QImage:
        """
        Retrieve a cached image by ID.
        
        First checks memory cache, then database cache.
        
        Args:
            image_id: Database ID of the image
            
        Returns:
            Cached QImage if found, None otherwise
        """
        locker = QMutexLocker(self._mutex)
        key = f"image://db/{image_id}"
        
        # Check memory cache first
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        
        # Check database cache
        if self._db_path:
            try:
                import sqlite3
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT processed_data FROM image_cache WHERE image_id = ?", (image_id,))
                row = cursor.fetchone()
                conn.close()
                
                if row and row[0]:
                    img = QImage()
                    if img.loadFromData(QByteArray(row[0])):
                        # Add to memory cache
                        # We must respect max size even here
                        if len(self._cache) >= self._max_size:
                             self._cache.popitem(last=False)
                             
                        self._cache[key] = img
                        self._cache.move_to_end(key)
                        return img
            except Exception as e:
                print(f"Failed to load image from DB cache: {e}")
        
        return None
    
    def set(self, image_id: int, image_data: QImage):
        """
        Store an image in memory cache.
        
        Image will be persisted to database when save_to_db() is called.
        
        Args:
            image_id: Database ID of the image
            image_data: Processed QImage to cache
        """
        locker = QMutexLocker(self._mutex)
        key = f"image://db/{image_id}"
        
        # Remove oldest entry if cache is full
        if len(self._cache) >= self._max_size and key not in self._cache:
            self._cache.popitem(last=False)
        
        # Add/update and move to end
        self._cache[key] = image_data
        self._cache.move_to_end(key)
    
    def clear(self):
        """Clear memory cache. Database cache remains intact."""
        locker = QMutexLocker(self._mutex)
        self._cache.clear()
    
    def clear_db_cache(self):
        """Clear all cached images from database."""
        locker = QMutexLocker(self._mutex)
        if not self._db_path:
            return
        
        try:
            import sqlite3
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM image_cache")
            conn.commit()
            conn.close()
            self._cache.clear()
        except Exception as e:
            print(f"Failed to clear database cache: {e}")
    
    def set_max_size(self, size: int):
        """Set the maximum cache size."""
        locker = QMutexLocker(self._mutex)
        self._max_size = max(1, size)
        while len(self._cache) > self._max_size:
            self._cache.popitem(last=False)
    
    def get_size(self) -> int:
        """Get current number of cached images in memory."""
        locker = QMutexLocker(self._mutex)
        return len(self._cache)
    
    def get_max_size(self) -> int:
        """Get maximum cache capacity."""
        locker = QMutexLocker(self._mutex)
        return self._max_size
