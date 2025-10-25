"""
Compression utilities for DeezChat
"""

import lz4.frame
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)

def compress_if_beneficial(data: bytes, min_size: int = 100) -> Tuple[bool, bytes]:
    """
    Compress data if it's beneficial
    
    Args:
        data: Data to compress
        min_size: Minimum size to attempt compression
        
    Returns:
        Tuple of (was_compressed, compressed_data)
    """
    if len(data) < min_size:
        return False, data
        
    try:
        compressed = lz4.frame.compress(data)
        # Only use compression if it actually reduces size
        if len(compressed) < len(data):
            return True, compressed
        else:
            return False, data
    except Exception as e:
        logger.error(f"Compression failed: {e}")
        return False, data

def decompress(data: bytes) -> Optional[bytes]:
    """
    Decompress data
    
    Args:
        data: Compressed data
        
    Returns:
        Decompressed data or None if failed
    """
    try:
        return lz4.frame.decompress(data)
    except Exception as e:
        logger.error(f"Decompression failed: {e}")
        return None