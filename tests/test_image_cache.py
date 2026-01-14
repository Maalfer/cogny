"""
Test suite for SQLite-based image cache functionality.

Tests verify:
- Cache persistence in database
- Load/save operations
- Cache portability with database
- Memory and database cache layers
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from PySide6.QtGui import QImage, QColor
from PySide6.QtCore import QByteArray, QBuffer, QIODevice
from app.database.manager import DatabaseManager
from app.ui.image_cache import GlobalImageCache


def create_test_image(width=100, height=100, color=QColor(255, 0, 0)):
    """Create a simple test QImage."""
    img = QImage(width, height, QImage.Format_RGB32)
    img.fill(color)
    return img


def image_to_bytes(img):
    """Convert QImage to bytes for comparison."""
    ba = QByteArray()
    buffer = QBuffer(ba)
    buffer.open(QIODevice.WriteOnly)
    img.save(buffer, "PNG")
    return bytes(ba)


def test_cache_basic_operations():
    """Test basic cache set/get operations."""
    print("\n=== Test 1: Basic Cache Operations ===")
    
    # Create temporary database
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.cdb")
        
        # Initialize database and cache
        db = DatabaseManager(db_path)
        GlobalImageCache._instance = None  # Reset singleton
        GlobalImageCache.set_db_path(db_path)
        cache = GlobalImageCache.get_instance()
        
        # Create and add test image to database
        test_img = create_test_image(color=QColor(255, 0, 0))
        img_bytes = image_to_bytes(test_img)
        
        # Add note first (foreign key requirement), then image
        with db.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO notes (title, content) VALUES (?, ?)", ("Test Note", "Content"))
            note_id = cursor.lastrowid
            cursor.execute("INSERT INTO images (note_id, data) VALUES (?, ?)", (note_id, img_bytes))
            image_id = cursor.lastrowid
        
        # Test cache set/get
        cache.set(image_id, test_img)
        cached_img = cache.get(image_id)
        
        assert cached_img is not None, "Failed to retrieve cached image"
        assert cached_img.width() == 100, "Image width mismatch"
        assert cached_img.height() == 100, "Image height mismatch"
        
        print("✓ Basic cache operations work correctly")


def test_cache_persistence():
    """Test cache persistence to database."""
    print("\n=== Test 2: Cache Persistence ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.cdb")
        
        # Phase 1: Create cache and save to DB
        db = DatabaseManager(db_path)
        GlobalImageCache._instance = None
        GlobalImageCache.set_db_path(db_path)
        cache = GlobalImageCache.get_instance()
        
        #Add test image to database
        test_img = create_test_image(color=QColor(0, 255, 0))
        img_bytes = image_to_bytes(test_img)
        
        with db.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO notes (title, content) VALUES (?, ?)", ("Test Note", "Content"))
            note_id = cursor.lastrowid
            cursor.execute("INSERT INTO images (note_id, data) VALUES (?, ?)", (note_id, img_bytes))
            image_id = cursor.lastrowid
        
        # Cache the image and save to DB
        cache.set(image_id, test_img)
        cache.save_to_db()
        
        # Verify it was saved to database
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM image_cache WHERE image_id = ?", (image_id,))
        count = cursor.fetchone()[0]
        conn.close()
        
        assert count == 1, "Image was not saved to database cache"
        print("✓ Image saved to database cache")
        
        # Phase 2: Clear memory cache and reload from DB
        GlobalImageCache._instance = None  # Reset singleton
        GlobalImageCache.set_db_path(db_path)
        cache2 = GlobalImageCache.get_instance()
        
        # Image should load from database cache
        cached_img = cache2.get(image_id)
        
        assert cached_img is not None, "Failed to load from database cache"
        assert cached_img.width() == 100, "Loaded image width mismatch"
        print("✓ Image successfully reloaded from database cache")


def test_cache_portability():
    """Test that cache moves with database file."""
    print("\n=== Test 3: Cache Portability ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create initial DB in location A
        location_a = os.path.join(tmpdir, "location_a")
        os.makedirs(location_a)
        db_path_a = os.path.join(location_a, "notes.cdb")
        
        # Setup database and cache
        db = DatabaseManager(db_path_a)
        GlobalImageCache._instance = None
        GlobalImageCache.set_db_path(db_path_a)
        cache = GlobalImageCache.get_instance()
        
        # Add test image
        test_img = create_test_image(color=QColor(0, 0, 255))
        img_bytes = image_to_bytes(test_img)
        
        with db.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO notes (title, content) VALUES (?, ?)", ("Test Note", "Content"))
            note_id = cursor.lastrowid
            cursor.execute("INSERT INTO images (note_id, data) VALUES (?, ?)", (note_id, img_bytes))
            image_id = cursor.lastrowid
        
        # Cache and save
        cache.set(image_id, test_img)
        cache.save_to_db()
        
        # Move database to location B
        location_b = os.path.join(tmpdir, "location_b")
        os.makedirs(location_b)
        db_path_b = os.path.join(location_b, "notes.cdb")
        shutil.copy2(db_path_a, db_path_b)
        
        print(f"✓ Database moved from {location_a} to {location_b}")
        
        # Verify cache exists in new location
        GlobalImageCache._instance = None
        GlobalImageCache.set_db_path(db_path_b)
        cache_b = GlobalImageCache.get_instance()
        
        # Load from cache in new location
        cached_img = cache_b.get(image_id)
        
        assert cached_img is not None, "Cache not found after moving database"
        assert cached_img.width() == 100, "Image corrupted after move"
        
        # Verify no leftover files in location A (except the DB itself)
        leftover_files = [f for f in os.listdir(location_a) if f != "notes.cdb"]
        assert len(leftover_files) == 0, f"Leftover files found: {leftover_files}"
        
        print("✓ Cache successfully moved with database")
        print("✓ No orphaned cache files left behind")


def test_cache_auto_cleanup():
    """Test that cache is cleaned up when image is deleted."""
    print("\n=== Test 4: Auto Cleanup on Image Delete ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.cdb")
        
        db = DatabaseManager(db_path)
        GlobalImageCache._instance = None
        GlobalImageCache.set_db_path(db_path)
        cache = GlobalImageCache.get_instance()
        
        # Add test image
        test_img = create_test_image()
        img_bytes = image_to_bytes(test_img)
        
        with db.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO notes (title, content) VALUES (?, ?)", ("Test Note", "Content"))
            note_id = cursor.lastrowid
            cursor.execute("INSERT INTO images (note_id, data) VALUES (?, ?)", (note_id, img_bytes))
            image_id = cursor.lastrowid
        
        # Cache and save
        cache.set(image_id, test_img)
        cache.save_to_db()
        
        # Verify cache exists
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys=ON")  # Enable CASCADE
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM image_cache WHERE image_id = ?", (image_id,))
        assert cursor.fetchone()[0] == 1, "Cache not created"
        
        # Delete image from database
        cursor.execute("DELETE FROM images WHERE id = ?", (image_id,))
        conn.commit()
        
        # Verify cache was auto-deleted (CASCADE)
        cursor.execute("SELECT COUNT(*) FROM image_cache WHERE image_id = ?", (image_id,))
        count = cursor.fetchone()[0]
        conn.close()
        
        assert count == 0, "Cache not auto-deleted with image"
        print("✓ Cache automatically cleaned up when image deleted")


def test_dual_layer_cache():
    """Test memory and database cache layers."""
    print("\n=== Test 5: Dual-Layer Cache ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.cdb")
        
        db = DatabaseManager(db_path)
        GlobalImageCache._instance = None
        GlobalImageCache.set_db_path(db_path)
        cache = GlobalImageCache.get_instance()
        
        # Add test image
        test_img = create_test_image()
        img_bytes = image_to_bytes(test_img)
        
        with db.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO notes (title, content) VALUES (?, ?)", ("Test Note", "Content"))
            note_id = cursor.lastrowid
            cursor.execute("INSERT INTO images (note_id, data) VALUES (?, ?)", (note_id, img_bytes))
            image_id = cursor.lastrowid
        
        # Test 1: Get from memory cache (fast path)
        cache.set(image_id, test_img)
        cached_img = cache.get(image_id)
        assert cached_img is not None, "Failed to get from memory cache"
        print("✓ Memory cache working")
        
        # Save to database
        cache.save_to_db()
        
        # Clear memory cache only
        cache.clear()
        assert cache.get_size() == 0, "Memory cache not cleared"
        print("✓ Memory cache cleared")
        
        # Test 2: Get from database cache (slower path, auto-loads to memory)
        cached_img = cache.get(image_id)
        assert cached_img is not None, "Failed to get from database cache"
        assert cache.get_size() == 1, "Image not re-added to memory cache"
        print("✓ Database cache working and auto-loads to memory")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Testing SQLite-Based Image Cache")
    print("=" * 60)
    
    try:
        test_cache_basic_operations()
        test_cache_persistence()
        test_cache_portability()
        test_cache_auto_cleanup()
        test_dual_layer_cache()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        return 0
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
