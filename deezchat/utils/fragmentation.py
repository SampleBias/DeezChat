"""
Message fragmentation utilities for DeezChat
"""

import struct
import logging
from typing import List, Optional, Union
from dataclasses import dataclass
from enum import IntEnum

logger = logging.getLogger(__name__)

class FragmentType(IntEnum):
    """Fragment types"""
    DATA = 1
    CONTROL = 2
    ACK = 3

@dataclass
class Fragment:
    """Message fragment"""
    message_id: str
    fragment_index: int
    total_fragments: int
    fragment_type: FragmentType
    payload: bytes
    checksum: Optional[bytes] = None

def fragment_payload(data: bytes, message_id: str, max_fragment_size: int = 1000) -> List[Fragment]:
    """
    Split payload into fragments
    
    Args:
        data: Data to fragment
        message_id: Unique message identifier
        max_fragment_size: Maximum size per fragment
        
    Returns:
        List of fragments
    """
    if len(data) <= max_fragment_size:
        return [Fragment(
            message_id=message_id,
            fragment_index=0,
            total_fragments=1,
            fragment_type=FragmentType.DATA,
            payload=data
        )]
    
    fragments = []
    total_fragments = (len(data) + max_fragment_size - 1) // max_fragment_size
    
    for i in range(total_fragments):
        start = i * max_fragment_size
        end = min(start + max_fragment_size, len(data))
        fragment_data = data[start:end]
        
        fragment = Fragment(
            message_id=message_id,
            fragment_index=i,
            total_fragments=total_fragments,
            fragment_type=FragmentType.DATA,
            payload=fragment_data
        )
        fragments.append(fragment)
    
    return fragments

def reassemble_fragments(fragments: List[Fragment]) -> Optional[bytes]:
    """
    Reassemble fragments into original data
    
    Args:
        fragments: List of fragments
        
    Returns:
        Reassembled data or None if failed
    """
    if not fragments:
        return None
    
    # Group by message_id
    messages = {}
    for fragment in fragments:
        if fragment.message_id not in messages:
            messages[fragment.message_id] = []
        messages[fragment.message_id].append(fragment)
    
    # For now, just handle the first message
    message_fragments = list(messages.values())[0]
    
    # Check if we have all fragments
    if not message_fragments:
        return None
    
    total_fragments = message_fragments[0].total_fragments
    if len(message_fragments) != total_fragments:
        return None
    
    # Sort by fragment index
    message_fragments.sort(key=lambda f: f.fragment_index)
    
    # Reassemble
    try:
        data = b''
        for fragment in message_fragments:
            data += fragment.payload
        return data
    except Exception as e:
        logger.error(f"Fragment reassembly failed: {e}")
        return None