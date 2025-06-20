"""Cache management for the Profile Scraping MCP Server."""

import sqlite3
import json
import time
from typing import Optional, Any, Dict
from pathlib import Path
from .logger import get_logger

logger = get_logger(__name__)


class CacheManager:
    """Simple SQLite-based cache manager for profile data."""
    
    def __init__(self, db_path: str = "data/cache.db", ttl: int = 3600):
        """
        Initialize cache manager.
        
        Args:
            db_path: Path to SQLite database file
            ttl: Time to live for cache entries in seconds
        """
        self.db_path = db_path
        self.ttl = ttl
        
        # Create directory if it doesn't exist
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize the cache database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    ttl INTEGER NOT NULL
                )
            """)
            
            # Create index for faster lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON cache(timestamp)
            """)
            
            conn.commit()
        
        logger.info(f"Cache database initialized at {self.db_path}")
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT value, timestamp, ttl FROM cache WHERE key = ?",
                    (key,)
                )
                result = cursor.fetchone()
                
                if result is None:
                    return None
                
                value_str, timestamp, ttl = result
                
                # Check if expired
                if time.time() - timestamp > ttl:
                    # Remove expired entry
                    cursor.execute("DELETE FROM cache WHERE key = ?", (key,))
                    conn.commit()
                    return None
                
                # Deserialize and return value
                return json.loads(value_str)
                
        except Exception as e:
            logger.error(f"Error getting cache key {key}: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live (uses default if None)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if ttl is None:
                ttl = self.ttl
            
            value_str = json.dumps(value)
            timestamp = time.time()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT OR REPLACE INTO cache (key, value, timestamp, ttl) VALUES (?, ?, ?, ?)",
                    (key, value_str, timestamp, ttl)
                )
                conn.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"Error setting cache key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """
        Delete value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM cache WHERE key = ?", (key,))
                conn.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"Error deleting cache key {key}: {e}")
            return False
    
    def clear_expired(self) -> int:
        """
        Clear expired cache entries.
        
        Returns:
            Number of entries cleared
        """
        try:
            current_time = time.time()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Find expired entries
                cursor.execute(
                    "SELECT COUNT(*) FROM cache WHERE ? - timestamp > ttl",
                    (current_time,)
                )
                count = cursor.fetchone()[0]
                
                # Delete expired entries
                cursor.execute(
                    "DELETE FROM cache WHERE ? - timestamp > ttl",
                    (current_time,)
                )
                conn.commit()
            
            if count > 0:
                logger.info(f"Cleared {count} expired cache entries")
            
            return count
            
        except Exception as e:
            logger.error(f"Error clearing expired cache entries: {e}")
            return 0
    
    def clear_all(self) -> bool:
        """
        Clear all cache entries.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM cache")
                conn.commit()
            
            logger.info("Cleared all cache entries")
            return True
            
        except Exception as e:
            logger.error(f"Error clearing all cache entries: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Total entries
                cursor.execute("SELECT COUNT(*) FROM cache")
                total_entries = cursor.fetchone()[0]
                
                # Expired entries
                current_time = time.time()
                cursor.execute(
                    "SELECT COUNT(*) FROM cache WHERE ? - timestamp > ttl",
                    (current_time,)
                )
                expired_entries = cursor.fetchone()[0]
                
                # Database size
                cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
                db_size = cursor.fetchone()[0]
            
            return {
                "total_entries": total_entries,
                "expired_entries": expired_entries,
                "valid_entries": total_entries - expired_entries,
                "database_size_bytes": db_size,
                "ttl_seconds": self.ttl
            }
            
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}