import boto3
import io
from typing import Any, Dict, List, Optional, Union, BinaryIO
import json

from . import ObjectStorage

class S3ObjectStorage(ObjectStorage):
    """Object storage implementation using Amazon S3.
    
    This class implements the ObjectStorage interface using Amazon S3
    to store objects.
    
    Args:
        bucket_name: Name of the S3 bucket.
        prefix: Optional prefix for all objects.
        aws_access_key_id: Optional AWS access key ID.
        aws_secret_access_key: Optional AWS secret access key.
        region_name: Optional AWS region name.
    """
    
    def __init__(
        self,
        bucket_name: str,
        prefix: str = "",
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        region_name: Optional[str] = None
    ):
        """Initialize an S3ObjectStorage."""
        self.bucket_name = bucket_name
        self.prefix = prefix.rstrip('/') + '/' if prefix else ""
        
        # Initialize S3 client
        self.s3 = boto3.client(
            's3',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name
        )
        
    def _get_full_key(self, key: str) -> str:
        """Get the full S3 key including prefix.
        
        Args:
            key: The object key.
            
        Returns:
            str: The full S3 key.
        """
        return f"{self.prefix}{key}"
    
    def put(
        self, 
        key: str, 
        data: Union[bytes, BinaryIO, str],
        metadata: Optional[Dict[str, str]] = None
    ) -> bool:
        """Store an object in S3.
        
        Args:
            key: Key to store the object under.
            data: Object data to store.
            metadata: Optional metadata for the object.
            
        Returns:
            bool: True if successful, False otherwise.
        """
        full_key = self._get_full_key(key)
        
        try:
            # Prepare data
            if isinstance(data, str):
                data = data.encode('utf-8')
                
            # Prepare metadata
            extra_args = {}
            if metadata:
                extra_args['Metadata'] = metadata
                
            # Upload to S3
            if hasattr(data, 'read'):
                self.s3.upload_fileobj(data, self.bucket_name, full_key, ExtraArgs=extra_args)
            else:
                self.s3.put_object(Bucket=self.bucket_name, Key=full_key, Body=data, **extra_args)
                
            return True
        except Exception:
            return False
    
    def get(self, key: str) -> Optional[bytes]:
        """Get an object from S3 by key.
        
        Args:
            key: Key of the object to get.
            
        Returns:
            Optional[bytes]: Object data if found, None otherwise.
        """
        full_key = self._get_full_key(key)
        
        try:
            response = self.s3.get_object(Bucket=self.bucket_name, Key=full_key)
            return response['Body'].read()
        except Exception:
            return None
    
    def get_metadata(self, key: str) -> Optional[Dict[str, str]]:
        """Get object metadata from S3 by key.
        
        Args:
            key: Key of the object to get metadata for.
            
        Returns:
            Optional[Dict[str, str]]: Metadata if found, None otherwise.
        """
        full_key = self._get_full_key(key)
        
        try:
            response = self.s3.head_object(Bucket=self.bucket_name, Key=full_key)
            return response.get('Metadata', {})
        except Exception:
            return None
    
    def delete(self, key: str) -> bool:
        """Delete an object from S3 by key.
        
        Args:
            key: Key of the object to delete.
            
        Returns:
            bool: True if successful, False otherwise.
        """
        full_key = self._get_full_key(key)
        
        try:
            self.s3.delete_object(Bucket=self.bucket_name, Key=full_key)
            return True
        except Exception:
            return False
    
    def list(self, prefix: Optional[str] = None) -> List[str]:
        """List objects in S3 with optional prefix.
        
        Args:
            prefix: Optional prefix to filter by.
            
        Returns:
            List[str]: List of object keys.
        """
        # Combine storage prefix with filter prefix
        list_prefix = self.prefix
        if prefix:
            list_prefix += prefix
            
        try:
            result = []
            paginator = self.s3.get_paginator('list_objects_v2')
            
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=list_prefix):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        # Remove storage prefix to get original key
                        key = obj['Key']
                        if key.startswith(self.prefix):
                            key = key[len(self.prefix):]
                        result.append(key)
                        
            return result
        except Exception:
            return []
