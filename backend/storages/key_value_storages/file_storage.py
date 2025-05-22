import os
import json
import pickle
from typing import Any, Dict, List, Optional, Union

from . import KeyValueStorage

class FileKeyValueStorage(KeyValueStorage):
    """Key-value storage implementation using files.
    
    This class implements the KeyValueStorage interface using files
    to store key-value pairs.
    
    Args:
        storage_dir: Directory to store files in.
        format: Storage format ("json" or "pickle").
    """
    
    def __init__(
        self,
        storage_dir: str,
        format: str = "json"
    ):
        """Initialize a FileKeyValueStorage."""
        self.storage_dir = storage_dir
        self.format = format.lower()
        
        # Create storage directory if it doesn't exist
        os.makedirs(storage_dir, exist_ok=True)
        
    def _get_path(self, key: str) -> str:
        """Get the file path for a key.
        
        Args:
            key: The key to get path for.
            
        Returns:
            str: The file path.
        """
        # Sanitize key for use as filename
        safe_key = key.replace('/', '_').replace('\\', '_')
        
        if self.format == "json":
            return os.path.join(self.storage_dir, f"{safe_key}.json")
        else:
            return os.path.join(self.storage_dir, f"{safe_key}.pkl")
    
    def get(self, key: str) -> Any:
        """Get a value by key.
        
        Args:
            key: The key to retrieve.
            
        Returns:
            Any: The stored value, or None if key not found.
        """
        path = self._get_path(key)
        
        if not os.path.exists(path):
            return None
            
        try:
            if self.format == "json":
                with open(path, 'r') as f:
                    return json.load(f)
            else:
                with open(path, 'rb') as f:
                    return pickle.load(f)
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
        path = self._get_path(key)
        
        try:
            if self.format == "json":
                with open(path, 'w') as f:
                    json.dump(value, f)
            else:
                with open(path, 'wb') as f:
                    pickle.dump(value, f)
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
        path = self._get_path(key)
        
        if not os.path.exists(path):
            return False
            
        try:
            os.remove(path)
            return True
        except Exception:
            return False
    
    def exists(self, key: str) -> bool:
        """Check if a key exists.
        
        Args:
            key: The key to check.
            
        Returns:
            bool: True if key exists, False otherwise.
        """
        path = self._get_path(key)
        return os.path.exists(path)
    
    def keys(self) -> List[str]:
        """Get all keys in the storage.
        
        Returns:
            List[str]: List of all keys.
        """
        keys = []
        
        for filename in os.listdir(self.storage_dir):
            if self.format == "json" and filename.endswith(".json"):
                keys.append(filename[:-5])  # Remove .json extension
            elif self.format == "pickle" and filename.endswith(".pkl"):
                keys.append(filename[:-4])  # Remove .pkl extension
                
        return keys
