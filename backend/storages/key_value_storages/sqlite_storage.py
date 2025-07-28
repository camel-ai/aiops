import sqlite3
from typing import Any, Dict, List, Optional, Union
import json
import pickle

from . import KeyValueStorage

class SQLiteKeyValueStorage(KeyValueStorage):
    """Key-value storage implementation using SQLite.
    
    This class implements the KeyValueStorage interface using SQLite
    to store key-value pairs.
    
    Args:
        db_path: Path to SQLite database file.
        table_name: Name of the table to use.
        format: Storage format for values ("json" or "pickle").
    """
    
    def __init__(
        self,
        db_path: str,
        table_name: str = "key_value_store",
        format: str = "json"
    ):
        """Initialize a SQLiteKeyValueStorage."""
        self.db_path = db_path
        self.table_name = table_name
        self.format = format.lower()
        
        # Initialize database
        self._init_db()
        
    def _init_db(self):
        """Initialize the database and create table if needed."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create table if it doesn't exist
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                key TEXT PRIMARY KEY,
                value BLOB
            )
        ''')
        
        conn.commit()
        conn.close()
        
    def _serialize(self, value: Any) -> bytes:
        """Serialize a value to bytes.
        
        Args:
            value: The value to serialize.
            
        Returns:
            bytes: The serialized value.
        """
        if self.format == "json":
            return json.dumps(value).encode('utf-8')
        else:
            return pickle.dumps(value)
            
    def _deserialize(self, data: bytes) -> Any:
        """Deserialize bytes to a value.
        
        Args:
            data: The data to deserialize.
            
        Returns:
            Any: The deserialized value.
        """
        if self.format == "json":
            return json.loads(data.decode('utf-8'))
        else:
            return pickle.loads(data)
    
    def get(self, key: str) -> Any:
        """Get a value by key.
        
        Args:
            key: The key to retrieve.
            
        Returns:
            Any: The stored value, or None if key not found.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            f"SELECT value FROM {self.table_name} WHERE key = ?",
            (key,)
        )
        
        result = cursor.fetchone()
        conn.close()
        
        if result is None:
            return None
            
        try:
            return self._deserialize(result[0])
        except Exception:
            return None
    
    def set(self, key: str, value: Any) -> bool:
        """Set a value for a key.
        
        Args:
            key: The key to set.
            value: The value to store.
            
        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            serialized = self._serialize(value)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                f"INSERT OR REPLACE INTO {self.table_name} (key, value) VALUES (?, ?)",
                (key, serialized)
            )
            
            conn.commit()
            conn.close()
            return True
        except Exception:
            return False
    
    def delete(self, key: str) -> bool:
        """Delete a key-value pair.
        
        Args:
            key: The key to delete.
            
        Returns:
            bool: True if successful, False otherwise.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            f"DELETE FROM {self.table_name} WHERE key = ?",
            (key,)
        )
        
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return deleted
    
    def exists(self, key: str) -> bool:
        """Check if a key exists.
        
        Args:
            key: The key to check.
            
        Returns:
            bool: True if key exists, False otherwise.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            f"SELECT 1 FROM {self.table_name} WHERE key = ?",
            (key,)
        )
        
        exists = cursor.fetchone() is not None
        conn.close()
        
        return exists
    
    def keys(self) -> List[str]:
        """Get all keys in the storage.
        
        Returns:
            List[str]: List of all keys.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(f"SELECT key FROM {self.table_name}")
        
        keys = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        return keys
