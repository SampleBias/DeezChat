"""
Message handling for DeezChat
"""

import logging
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from enum import IntEnum
import asyncio
import time
import uuid

from ..storage.database import Message, MessageFilters

logger = logging.getLogger(__name__)

class MessageType(IntEnum):
    """Message types"""
    PUBLIC = 1
    PRIVATE = 2
    CHANNEL = 3
    CONTROL = 4
    ACK = 5

@dataclass
class NetworkMessage:
    """Network message representation"""
    message_id: str
    message_type: MessageType
    sender_id: str
    recipient_id: Optional[str] = None
    channel: Optional[str] = None
    payload: bytes = b""
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()

class MessageRouter:
    """Message routing and handling"""
    
    def __init__(self, config):
        self.config = config
        self.handlers: Dict[MessageType, List[Callable]] = {}
        self.message_cache: Dict[str, NetworkMessage] = {}
        self.cache_ttl = 300  # 5 minutes
        
    def register_handler(self, message_type: MessageType, handler: Callable):
        """Register message handler"""
        if message_type not in self.handlers:
            self.handlers[message_type] = []
        self.handlers[message_type].append(handler)
        logger.debug(f"Registered handler for {message_type}")
        
    async def route_message(self, message: NetworkMessage) -> bool:
        """Route message to appropriate handlers"""
        try:
            # Check if already seen
            if self._is_duplicate(message):
                logger.debug(f"Duplicate message ignored: {message.message_id}")
                return False
                
            # Cache message
            self._cache_message(message)
            
            # Route to handlers
            handlers = self.handlers.get(message.message_type, [])
            for handler in handlers:
                try:
                    await handler(message)
                except Exception as e:
                    logger.error(f"Handler failed: {e}")
                    
            return True
            
        except Exception as e:
            logger.error(f"Message routing failed: {e}")
            return False
            
    def _is_duplicate(self, message: NetworkMessage) -> bool:
        """Check if message is duplicate"""
        return message.message_id in self.message_cache
        
    def _cache_message(self, message: NetworkMessage):
        """Cache message"""
        self.message_cache[message.message_id] = message
        # Clean old messages
        current_time = time.time()
        expired = [
            msg_id for msg_id, msg in self.message_cache.items()
            if current_time - msg.timestamp > self.cache_ttl
        ]
        for msg_id in expired:
            del self.message_cache[msg_id]

class MessageHandler:
    """Base message handler"""
    
    def __init__(self, config):
        self.config = config
        
    async def handle_message(self, message: NetworkMessage) -> bool:
        """Handle incoming message"""
        raise NotImplementedError("Subclasses must implement handle_message")