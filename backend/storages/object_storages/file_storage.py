import os
import shutil
from typing import Any, Dict, List, Optional, Union, BinaryIO
import json

from . import ObjectStorage

class FileObjectStorage(ObjectStorage):
    """Object storage implementation using local files.
    
    This class implements the ObjectStorage interface using the local
    filesystem to store objects.
    
    Args:
        storage_dir: Directory to store objects in.
    """
    
    def __init__(self, storage_dir: str):
        """Initialize a FileObjectStorage."""
        self.storage_dir = storage_dir
        self.metadata_dir = os.path.join(storage_dir, ".metadata")
        
        # Create storage directories if they don't exist
        os.makedirs(storage_dir, exist_ok=True)
        os.makedirs(self.metadata_dir, exist_ok=True)
        
    def _get_object_path(self, key: str) -> str:
        """Get the file path for an object.
        
        Args:
            key: The object key.
            
        Returns:
            str: The file path.
        """
        # Sanitize key for use as path
        safe_key = key.replace('..', '')
        return os.path.join(self.storage_dir, safe_key)
        
    def _get_metadata_path(self, key: str) -> str:
        """Get the file path for object metadata.
        
        Args:
            key: The object key.
            
        Returns:
            str: The metadata file path.
        """
        # Sanitize key for use as path
        safe_key = key.replace('..', '')
        return os.path.join(self.metadata_dir, f"{safe_key}.meta.json")
    
    def put(
        self, 
        key: str, 
        data: Union[bytes, BinaryIO, str],
        metadata: Optional[Dict[str, str]] = None
    ) -> bool:
        """Store an object.
        
        Args:
            key: Key to store the object under.
            data: Object data to store.
            metadata: Optional metadata for the object.
            
        Returns:
            bool: True if successful, False otherwise.
        """
        object_path = self._get_object_path(key)
        metadata_path = self._get_metadata_path(key)
        
        # Create parent directories if they don't exist
        os.makedirs(os.path.dirname(object_path), exist_ok=True)
        os.makedirs(os.path.dirname(metadata_path), exist_ok=True)
        
        try:
            # Write object data
            if isinstance(data, bytes):
                with open(object_path, 'wb') as f:
                    f.write(data)
            elif hasattr(data, 'read'):
                with open(object_path, 'wb') as f:
                    shutil.copyfileobj(data, f)
            elif isinstance(data, str):
                with open(object_path, 'w', encoding='utf-8') as f:
                    f.write(data)
            else:
                raise TypeError("Data must be bytes, file-like object, or string")
                
            # Write metadata if provided
            if metadata:
                with open(metadata_path, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f)
                    
            return True
        except Exception:
            # Clean up if there was an error
            if os.path.exists(object_path):
                os.remove(object_path)
            if os.path.exists(metadata_path):
                os.remove(metadata_path)
            return False
    
    def get(self, key: str) -> Optional[bytes]:
        """Get an object by key.
        
        Args:
            key: Key of the object to get.
            
        Returns:
            Optional[bytes]: Object data if found, None otherwise.
        """
        object_path = self._get_object_path(key)
        
        if not os.path.exists(object_path):
            return None
            
        try:
            with open(object_path, 'rb') as f:
                return f.read()
        except Exception:
            return None
    
    def get_metadata(self, key: str) -> Optional[Dict[str, str]]:
        """Get object metadata by key.
        
        Args:
            key: Key of the object to get metadata for.
            
        Returns:
            Optional[Dict[str, str]]: Metadata if found, None otherwise.
        """
        metadata_path = self._get_metadata_path(key)
        
        if not os.path.exists(metadata_path):
            return None
            
        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None
    
    def delete(self, key: str) -> bool:
        """Delete an object by key.
        
        Args:
            key: Key of the object to delete.
            
        Returns:
            bool: True if successful, False otherwise.
        """
        object_path = self._get_object_path(key)
        metadata_path = self._get_metadata_path(key)
        
        success = True
        
        # Delete object file
        if os.path.exists(object_path):
            try:
                os.remove(object_path)
            except Exception:
                success = False
                
        # Delete metadata file
        if os.path.exists(metadata_path):
            try:
                os.remove(metadata_path)
            except Exception:
                success = False
                
        return success
    
    def list(self, prefix: Optional[str] = None) -> List[str]:
        """List objects with optional prefix.
        
        Args:
            prefix: Optional prefix to filter by.
            
        Returns:
            List[str]: List of object keys.
        """
        result = []
        
        for root, _, files in os.walk(self.storage_dir):
            # Skip metadata directory
            if root.startswith(self.metadata_dir):
                continue
                
            for file in files:
                # Get relative path as key
                path = os.path.join(root, file)
                key = os.path.relpath(path, self.storage_dir)
                
                # Convert Windows path separators to forward slashes
                key = key.replace('\\', '/')
                
                # Filter by prefix if provided
                if prefix is None or key.startswith(prefix):
                    result.append(key)
                    
        return result
