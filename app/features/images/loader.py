from PySide6.QtCore import QRunnable, QObject, Signal, QThreadPool, Qt
from PySide6.QtGui import QImage
import os

class ImageLoaderSignals(QObject):
    finished = Signal(str, QImage)

class ImageLoader(QRunnable):
    def __init__(self, path, processor, root_path):
        super().__init__()
        self.path = path
        self.processor = processor
        self.root_path = root_path
        self.signals = ImageLoaderSignals()
        
    def run(self):
        target_path = self.path
        found = False
        
        if os.path.exists(target_path) and os.path.isfile(target_path):
            found = True
        elif self.root_path:
            # Smart Search
            basename = os.path.basename(self.path)
            
            # 1. Quick check commonly used folders
            candidates = [
                os.path.join(self.root_path, "images", basename),
                os.path.join(self.root_path, "adjuntos", basename), 
                os.path.join(self.root_path, "Adjuntos", basename),
                os.path.join(self.root_path, "assets", basename),
                os.path.join(self.root_path, basename)
            ]
            
            for c in candidates:
                if os.path.exists(c) and os.path.isfile(c):
                    target_path = c
                    found = True
                    break
            
            # 2. Recursive Search (if not found in candidates)
            # OPTIMIZED: Limit depth or better, rely on user structure. 
            # Walking entire vault is too slow (causing lag).
            # For now, we restrict to depth 3 and specific asset folders if possible.
            # Or better: ONLY search if path looks relative?
            # Let's simple skip full walk to improve performance. 
            # Users should put images in standard places.
            if not found:
                # print(f"DEBUG: Deep search disabled for performance.")
                pass
                # for root, dirs, files in os.walk(self.root_path):
                #     dirs[:] = [d for d in dirs if not d.startswith('.')]
                #     if basename in files:
                #         target_path = os.path.join(root, basename)
                #         found = True
                #         break

        img = QImage()
        if found:
            try:
                loaded = QImage(target_path)
                if not loaded.isNull():
                    img = loaded
                    if self.processor:
                        img = self.processor(img)
                else:
                    print(f"DEBUG: Failed to load QImage from {target_path}")
            except Exception as e:
                    print(f"ERROR: Image load exception: {e}")
        else:
            print(f"DEBUG: Could not find image {self.path} - Root: {self.root_path}")
                                
        self.signals.finished.emit(self.path, img)

class ImageHandler:
    """
    Manages async image loading and caching for editors.
    Singleton-like behavior via shared cache.
    """
    _image_cache = {}  # {image_id: QImage}
    _image_cache_order = []  # For LRU eviction
    _max_cached_images = 100
    _loading_images = set() 
    _thread_pool = None

    @classmethod
    def get_thread_pool(cls):
        if cls._thread_pool is None:
            cls._thread_pool = QThreadPool()
            cls._thread_pool.setMaxThreadCount(4) 
        return cls._thread_pool

    @classmethod
    def get_cached_image(cls, path):
        return cls._image_cache.get(path)

    @classmethod
    def is_loading(cls, path):
        return path in cls._loading_images

    @classmethod
    def cache_image(cls, image_id, image):
        """Add image to cache with LRU eviction."""
        # Evict oldest if at capacity
        while len(cls._image_cache) >= cls._max_cached_images:
            if cls._image_cache_order:
                oldest_id = cls._image_cache_order.pop(0)
                cls._image_cache.pop(oldest_id, None)
            else:
                break
        
        cls._image_cache[image_id] = image
        cls._image_cache_order.append(image_id)

    @classmethod
    def clear_cache(cls):
        cls._image_cache.clear()
        cls._image_cache_order.clear()

    @classmethod
    def mark_loading(cls, path):
        cls._loading_images.add(path)

    @classmethod
    def mark_finished(cls, path):
        if path in cls._loading_images:
            cls._loading_images.remove(path)

    @staticmethod
    def process_image_static(image):
        """Standard processing (resizing) for images."""
        max_width = 1200
        if image.width() > max_width:
             image = image.scaledToWidth(max_width, Qt.SmoothTransformation)
        return image

    @classmethod
    def load_async(cls, path, root_path, callback):
        """
        Starts async load. 
        callback: function(path, image) to call on main thread when done.
        """
        cls.mark_loading(path)
        loader = ImageLoader(path, cls.process_image_static, root_path)
        # Force QueuedConnection to ensure callback runs in Main Thread (GUI Safety)
        loader.signals.finished.connect(callback, Qt.QueuedConnection)
        
        # print(f"DEBUG ImageHandler: Starting async load for {os.path.basename(path)}")
        cls.get_thread_pool().start(loader)
