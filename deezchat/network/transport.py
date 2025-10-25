"""
Message transport module for DeezChat

Handles message routing, fragmentation, and delivery.
"""

import os
import asyncio
import logging
import time
import random
from typing import Dict, List, Optional, Callable, Any, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
import struct
import uuid
import hashlib

from ..storage.config import Config
from ..storage.database import Message, MessageFilters
from ..utils.fragmentation import fragment_payload, Fragment, FragmentType
from ..utils.compression import compress_if_beneficial
from ..core.message import MessageType
from ..utils.metrics import MetricsCollector

logger = logging.getLogger(__name__)

class MessagePriority(Enum):
    """Message priority levels"""
    CRITICAL = 1    # System messages, errors
    HIGH = 2       # Private messages
    NORMAL = 3     # Public messages
    LOW = 4         # File transfers, bulk data

class TransportError(Exception):
    """Transport related errors"""
    pass

@dataclass
class QueuedMessage:
    """Message queued for delivery"""
    message: Message
    priority: MessagePriority
    recipient_id: Optional[str] = None
    channel: Optional[str] = None
    attempts: int = 0
    max_attempts: int = 3
    created_at: float = field(default_factory=time.time)
    next_retry: float = field(default_factory=time.time)

@dataclass
class FragmentReassembly:
    """Fragment reassembly state"""
    fragment_id: str
    total_fragments: int
    received_fragments: Dict[int, Fragment] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    timeout: float = 30.0  # 30 seconds timeout

@dataclass
class DeliveryStats:
    """Message delivery statistics"""
    messages_sent: int = 0
    messages_delivered: int = 0
    messages_failed: int = 0
    fragments_sent: int = 0
    fragments_reassembled: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0

class MessageTransport:
    """Message transport and routing system"""
    
    def __init__(self, config: Config):
        self.config = config
        self.message_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.fragment_reassembly: Dict[str, FragmentReassembly] = {}
        self.delivery_stats = DeliveryStats()
        
        # Duplicate detection
        self.seen_messages: Set[str] = set()
        self.duplicate_window: Dict[str, float] = {}
        self.duplicate_timeout = 300.0  # 5 minutes
        
        # Event callbacks
        self.event_handlers: Dict[str, List[Callable]] = {}
        
        # Metrics
        self.metrics = MetricsCollector() if config.performance.enable_metrics else None
        
        # Background tasks
        self.processing_task = None
        self.cleanup_task = None
        self.running = False
        
        logger.info("Message transport initialized")
    
    async def start(self):
        """Start message transport"""
        if self.running:
            logger.warning("Message transport already running")
            return False
        
        self.running = True
        
        try:
            # Start background tasks
            self.processing_task = asyncio.create_task(self._processing_loop())
            self.cleanup_task = asyncio.create_task(self._cleanup_loop())
            
            logger.info("Message transport started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start message transport: {e}")
            return False
    
    async def stop(self):
        """Stop message transport"""
        if not self.running:
            logger.warning("Message transport not running")
            return False
        
        self.running = False
        
        try:
            # Stop background tasks
            if self.processing_task:
                self.processing_task.cancel()
                try:
                    await self.processing_task
                except asyncio.CancelledError:
                    pass
            
            if self.cleanup_task:
                self.cleanup_task.cancel()
                try:
                    await self.cleanup_task
                except asyncio.CancelledError:
                    pass
            
            # Clear queues
            while not self.message_queue.empty():
                self.message_queue.get_nowait()
            
            logger.info("Message transport stopped")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop message transport: {e}")
            return False
    
    def register_event_handler(self, event: str, handler: Callable):
        """Register event handler"""
        if event not in self.event_handlers:
            self.event_handlers[event] = []
        
        self.event_handlers[event].append(handler)
        logger.debug(f"Registered handler for event: {event}")
        return True
    
    def unregister_event_handler(self, event: str, handler: Callable):
        """Unregister event handler"""
        if event in self.event_handlers and handler in self.event_handlers[event]:
            self.event_handlers[event].remove(handler)
            logger.debug(f"Unregistered handler for event: {event}")
            return True
        return False
    
    def _trigger_event(self, event: str, data: Dict[str, Any]):
        """Trigger event handlers"""
        if event in self.event_handlers:
            for handler in self.event_handlers[event]:
                try:
                    # Create a task for each handler to avoid blocking
                    asyncio.create_task(handler(data))
                except Exception as e:
                    logger.error(f"Event handler error for {event}: {e}")
    
    async def queue_message(self, message: Message, priority: MessagePriority = MessagePriority.NORMAL,
                          recipient_id: Optional[str] = None, channel: Optional[str] = None) -> bool:
        """Queue message for delivery"""
        try:
            # Check for duplicates
            if self._is_duplicate(message):
                logger.debug(f"Duplicate message detected: {message.id}")
                return False
            
            # Create queued message
            queued_msg = QueuedMessage(
                message=message,
                priority=priority,
                recipient_id=recipient_id,
                channel=channel,
                created_at=time.time()
            )
            
            # Add to priority queue
            await self.message_queue.put((priority.value, queued_msg))
            
            # Update stats
            self.delivery_stats.messages_sent += 1
            
            # Trigger event
            self._trigger_event('message_queued', {
                'message': message,
                'priority': priority,
                'recipient_id': recipient_id,
                'channel': channel
            })
            
            logger.debug(f"Queued message {message.id} with priority {priority.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to queue message {message.id}: {e}")
            return False
    
    async def _processing_loop(self):
        """Background message processing loop"""
        while self.running:
            try:
                # Get message from queue with timeout
                try:
                    priority, queued_msg = await asyncio.wait_for(
                        self.message_queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    # Queue is empty, continue
                    continue
                
                # Process message
                success = await self._process_message(queued_msg)
                
                if success:
                    self.delivery_stats.messages_delivered += 1
                else:
                    self.delivery_stats.messages_failed += 1
                    # Retry if max attempts not reached
                    if queued_msg.attempts < queued_msg.max_attempts:
                        queued_msg.attempts += 1
                        queued_msg.next_retry = time.time() + (2 ** queued_msg.attempts)  # Exponential backoff
                        
                        # Re-queue with same priority
                        await self.message_queue.put((priority.value, queued_msg))
                    else:
                        # Max attempts reached, give up
                        self._trigger_event('message_failed', {
                            'message': queued_msg.message,
                            'attempts': queued_msg.attempts,
                            'reason': 'Max attempts reached'
                        })
                
            except Exception as e:
                logger.error(f"Error in processing loop: {e}")
                await asyncio.sleep(0.1)  # Prevent tight error loop
    
    async def _process_message(self, queued_msg: QueuedMessage) -> bool:
        """Process a queued message"""
        message = queued_msg.message
        
        try:
            # Check if message needs fragmentation
            message_data = self._serialize_message(message)
            
            if len(message_data) > MAX_FRAGMENT_SIZE:
                # Fragment and send
                return await self._send_fragmented_message(queued_msg)
            else:
                # Send directly
                return await self._send_direct_message(queued_msg)
                
        except Exception as e:
            logger.error(f"Failed to process message {message.id}: {e}")
            return False
    
    def _serialize_message(self, message: Message) -> bytes:
        """Serialize message to bytes"""
        # Create message payload
        payload = bytearray()
        
        # Flags
        flags = 0
        if message.is_private:
            flags |= 0x01  # Is private
        if message.channel:
            flags |= 0x02  # Has channel
        if message.is_encrypted:
            flags |= 0x04  # Is encrypted
        
        payload.append(flags)
        
        # Timestamp (8 bytes)
        timestamp_ms = int(message.timestamp * 1000)
        payload.extend(struct.pack('>Q', timestamp_ms))
        
        # Message ID (variable length)
        message_id_bytes = message.id.encode('utf-8')
        payload.append(len(message_id_bytes))
        payload.extend(message_id_bytes)
        
        # Sender (variable length)
        sender_bytes = message.sender_nickname.encode('utf-8')
        payload.append(len(sender_bytes))
        payload.extend(sender_bytes)
        
        # Content (variable length)
        content_bytes = message.content.encode('utf-8')
        payload.extend(struct.pack('>H', len(content_bytes)))
        payload.extend(content_bytes)
        
        # Recipient (optional)
        if message.recipient_id:
            recipient_bytes = message.recipient_id.encode('utf-8')
            payload.append(len(recipient_bytes))
            payload.extend(recipient_bytes)
        else:
            payload.append(0)
        
        # Channel (optional)
        if message.channel:
            channel_bytes = message.channel.encode('utf-8')
            payload.append(len(channel_bytes))
            payload.extend(channel_bytes)
        else:
            payload.append(0)
        
        # Encrypted content (optional)
        if message.encrypted_content:
            payload.append(len(message.encrypted_content))
            payload.extend(message.encrypted_content)
        else:
            payload.append(0)
        
        # Mentions (optional)
        if message.mentions:
            mentions_json = str(message.mentions).encode('utf-8')
            payload.append(len(mentions_json))
            payload.extend(mentions_json)
        else:
            payload.append(0)
        
        return bytes(payload)
    
    async def _send_fragmented_message(self, queued_msg: QueuedMessage) -> bool:
        """Send fragmented message"""
        message = queued_msg.message
        message_data = self._serialize_message(message)
        
        # Create fragments
        fragments = fragment_payload(message_data, MessageType.MESSAGE.value)
        
        # Send fragments with small delay between them
        for i, fragment in enumerate(fragments):
            # Create fragment packet
            fragment_packet = self._create_fragment_packet(fragment)
            
            # Send fragment
            success = await self._send_packet(fragment_packet, queued_msg.recipient_id, queued_msg.channel)
            
            if not success:
                logger.error(f"Failed to send fragment {i+1}/{len(fragments)}")
                return False
            
            # Small delay between fragments
            if i < len(fragments) - 1:
                await asyncio.sleep(0.01)
            
            # Update stats
            self.delivery_stats.fragments_sent += 1
        
        # Update reassembly state
        self.fragment_reassembly[message.id] = FragmentReassembly(
            fragment_id=fragments[0].fragment_id.hex(),
            total_fragments=len(fragments),
            created_at=time.time()
        )
        
        logger.debug(f"Sent {len(fragments)} fragments for message {message.id}")
        return True
    
    async def _send_direct_message(self, queued_msg: QueuedMessage) -> bool:
        """Send direct message"""
        message = queued_msg.message
        message_data = self._serialize_message(message)
        
        # Compress if beneficial
        compressed, is_compressed = compress_if_beneficial(message_data)
        
        # Create packet
        packet = self._create_message_packet(compressed, is_compressed, MessageType.MESSAGE)
        
        # Send packet
        success = await self._send_packet(packet, queued_msg.recipient_id, queued_msg.channel)
        
        if success:
            self.delivery_stats.bytes_sent += len(packet)
        
        return success
    
    def _create_fragment_packet(self, fragment: Fragment) -> bytes:
        """Create fragment packet"""
        packet = bytearray()
        
        # Version (1 byte)
        packet.append(1)
        
        # Type (1 byte)
        packet.append(fragment.fragment_type.value)
        
        # TTL (1 byte)
        packet.append(self.config.network.ttl)
        
        # Timestamp (8 bytes)
        timestamp_ms = int(time.time() * 1000)
        packet.extend(struct.pack('>Q', timestamp_ms))
        
        # Flags (1 byte)
        flags = 0
        packet.append(flags)
        
        # Payload length (2 bytes)
        payload_length = len(fragment.data)
        packet.extend(struct.pack('>H', payload_length))
        
        # Fragment ID (8 bytes)
        packet.extend(bytes.fromhex(fragment.fragment_id))
        
        # Fragment index (2 bytes)
        packet.extend(struct.pack('>H', fragment.index))
        
        # Fragment total (2 bytes)
        packet.extend(struct.pack('>H', fragment.total))
        
        # Original type (1 byte)
        packet.append(fragment.original_type)
        
        # Fragment data
        packet.extend(fragment.data)
        
        return bytes(packet)
    
    def _create_message_packet(self, payload: bytes, is_compressed: bool, message_type: int) -> bytes:
        """Create message packet"""
        packet = bytearray()
        
        # Version (1 byte)
        packet.append(1)
        
        # Type (1 byte)
        packet.append(message_type)
        
        # TTL (1 byte)
        packet.append(self.config.network.ttl)
        
        # Timestamp (8 bytes)
        timestamp_ms = int(time.time() * 1000)
        packet.extend(struct.pack('>Q', timestamp_ms))
        
        # Flags (1 byte)
        flags = 0
        if is_compressed:
            flags |= 0x01  # Is compressed
        
        packet.append(flags)
        
        # Payload length (2 bytes)
        payload_length = len(payload)
        packet.extend(struct.pack('>H', payload_length))
        
        # Payload
        packet.extend(payload)
        
        return bytes(packet)
    
    async def _send_packet(self, packet: bytes, recipient_id: Optional[str] = None, 
                       channel: Optional[str] = None) -> bool:
        """Send packet to network layer"""
        try:
            # Trigger packet sent event
            self._trigger_event('packet_sent', {
                'packet': packet,
                'recipient_id': recipient_id,
                'channel': channel,
                'size': len(packet)
            })
            
            # This would be handled by the network layer
            # In a real implementation, this would call the network layer
            # For now, we'll just log it
            logger.debug(f"Packet sent: {len(packet)} bytes")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send packet: {e}")
            return False
    
    async def process_received_packet(self, packet: bytes, sender_id: str) -> bool:
        """Process received packet"""
        try:
            # Parse packet header
            if len(packet) < 13:  # Minimum header size
                logger.warning("Received packet too small")
                return False
            
            version = packet[0]
            message_type = packet[1]
            ttl = packet[2]
            timestamp_ms = struct.unpack('>Q', packet[3:11])[0]
            flags = packet[11]
            payload_length = struct.unpack('>H', packet[12:14])[0]
            
            if len(packet) < 13 + payload_length:
                logger.warning("Received packet truncated")
                return False
            
            payload = packet[13:13+payload_length]
            
            # Process based on message type
            if message_type == MessageType.MESSAGE.value:
                return await self._process_message_packet(payload, sender_id, ttl, flags)
            elif message_type == MessageType.FRAGMENT_START.value:
                return await self._process_fragment_start_packet(payload, sender_id)
            elif message_type == MessageType.FRAGMENT_CONTINUE.value:
                return await self._process_fragment_continue_packet(payload, sender_id)
            elif message_type == MessageType.FRAGMENT_END.value:
                return await self._process_fragment_end_packet(payload, sender_id)
            else:
                logger.warning(f"Unknown message type: {message_type}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to process received packet: {e}")
            return False
    
    async def _process_message_packet(self, payload: bytes, sender_id: str, ttl: int, flags: int) -> bool:
        """Process message packet"""
        try:
            # Parse message payload
            message = await self._parse_message_payload(payload, flags)
            
            if not message:
                logger.warning("Failed to parse message payload")
                return False
            
            # Set sender information
            message.sender_id = sender_id
            
            # Check for duplicates
            if self._is_duplicate(message):
                logger.debug(f"Duplicate message received: {message.id}")
                return False
            
            # Mark message as seen
            self._mark_message_seen(message, ttl)
            
            # Update stats
            self.delivery_stats.messages_delivered += 1
            self.delivery_stats.bytes_received += len(payload)
            
            # Trigger event
            self._trigger_event('message_received', {
                'message': message,
                'sender_id': sender_id
            })
            
            logger.debug(f"Received message {message.id} from {sender_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to process message packet: {e}")
            return False
    
    async def _process_fragment_start_packet(self, payload: bytes, sender_id: str) -> bool:
        """Process fragment start packet"""
        try:
            # Parse fragment start packet
            fragment = await self._parse_fragment_packet(payload, FragmentType.START)
            
            if not fragment:
                logger.warning("Failed to parse fragment start packet")
                return False
            
            # Initialize reassembly
            self.fragment_reassembly[fragment.fragment_id] = FragmentReassembly(
                fragment_id=fragment.fragment_id,
                total_fragments=fragment.total,
                created_at=time.time()
            )
            
            # Add first fragment
            self.fragment_reassembly[fragment.fragment_id].received_fragments[fragment.index] = fragment
            
            # Update stats
            self.delivery_stats.fragments_reassembled += 1
            
            logger.debug(f"Received fragment start {fragment.fragment_id} ({fragment.index}/{fragment.total})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to process fragment start packet: {e}")
            return False
    
    async def _process_fragment_continue_packet(self, payload: bytes, sender_id: str) -> bool:
        """Process fragment continue packet"""
        try:
            # Parse fragment continue packet
            fragment = await self._parse_fragment_packet(payload, FragmentType.CONTINUE)
            
            if not fragment:
                logger.warning("Failed to parse fragment continue packet")
                return False
            
            # Add fragment to reassembly
            if fragment.fragment_id in self.fragment_reassembly:
                self.fragment_reassembly[fragment.fragment_id].received_fragments[fragment.index] = fragment
            else:
                logger.warning(f"Received fragment for unknown ID: {fragment.fragment_id}")
                return False
            
            # Update stats
            self.delivery_stats.fragments_reassembled += 1
            
            logger.debug(f"Received fragment continue {fragment.fragment_id} ({fragment.index}/{fragment.total})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to process fragment continue packet: {e}")
            return False
    
    async def _process_fragment_end_packet(self, payload: bytes, sender_id: str) -> bool:
        """Process fragment end packet"""
        try:
            # Parse fragment end packet
            fragment = await self._parse_fragment_packet(payload, FragmentType.END)
            
            if not fragment:
                logger.warning("Failed to parse fragment end packet")
                return False
            
            # Add final fragment to reassembly
            if fragment.fragment_id in self.fragment_reassembly:
                self.fragment_reassembly[fragment.fragment_id].received_fragments[fragment.index] = fragment
            else:
                logger.warning(f"Received fragment end for unknown ID: {fragment.fragment_id}")
                return False
            
            # Check if all fragments received
            reassembly = self.fragment_reassembly[fragment.fragment_id]
            if len(reassembly.received_fragments) == reassembly.total_fragments:
                # Reassemble message
                message_data = bytearray()
                
                # Sort fragments by index and concatenate
                for i in range(reassembly.total_fragments):
                    if i in reassembly.received_fragments:
                        message_data.extend(reassembly.received_fragments[i].data)
                
                # Parse and process reassembled message
                success = await self._process_message_packet(message_data, sender_id, 0, 0)
                
                # Clean up reassembly
                del self.fragment_reassembly[fragment.fragment_id]
                
                # Update stats
                self.delivery_stats.fragments_reassembled += 1
                
                logger.debug(f"Reassembled message from {reassembly.total_fragments} fragments")
                return success
            else:
                logger.debug(f"Waiting for more fragments ({len(reassembly.received_fragments)}/{reassembly.total_fragments})")
                return True
            
        except Exception as e:
            logger.error(f"Failed to process fragment end packet: {e}")
            return False
    
    async def _parse_message_payload(self, payload: bytes, flags: int) -> Optional[Message]:
        """Parse message payload"""
        try:
            offset = 0
            
            # Check if compressed
            is_compressed = (flags & 0x01) != 0
            
            # Decompress if needed
            if is_compressed:
                from ..utils.compression import decompress
                payload = decompress(payload)
            else:
                payload = payload
            
            # Parse flags
            is_private = (flags & 0x01) != 0
            has_channel = (flags & 0x02) != 0
            is_encrypted = (flags & 0x04) != 0
            
            # Message ID
            id_len = payload[offset]
            offset += 1
            id_str = payload[offset:offset+id_len].decode('utf-8')
            offset += id_len
            
            # Timestamp (skip)
            offset += 8
            
            # Sender
            sender_len = payload[offset]
            offset += 1
            sender_str = payload[offset:offset+sender_len].decode('utf-8')
            offset += sender_len
            
            # Content
            content_len = struct.unpack('>H', payload[offset:offset+2])[0]
            offset += 2
            content_bytes = payload[offset:offset+content_len]
            offset += content_len
            
            # Recipient (optional)
            if offset < len(payload):
                recipient_len = payload[offset]
                offset += 1
                recipient_str = payload[offset:offset+recipient_len].decode('utf-8')
                offset += recipient_len
            else:
                recipient_str = None
                offset += 1
            
            # Channel (optional)
            if offset < len(payload):
                channel_len = payload[offset]
                offset += 1
                channel_str = payload[offset:offset+channel_len].decode('utf-8')
                offset += channel_len
            else:
                channel_str = None
                offset += 1
            
            # Encrypted content (optional)
            if offset < len(payload):
                encrypted_len = struct.unpack('>H', payload[offset:offset+2])[0]
                offset += 2
                encrypted_bytes = payload[offset:offset+encrypted_len]
                offset += encrypted_len
            else:
                encrypted_bytes = None
                offset += 1
            
            # Mentions (optional)
            if offset < len(payload):
                mentions_len = struct.unpack('>H', payload[offset:offset+2])[0]
                offset += 2
                mentions_bytes = payload[offset:offset+mentions_len]
                offset += mentions_len
                
                try:
                    import json
                    mentions = json.loads(mentions_bytes.decode('utf-8'))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    mentions = []
            else:
                mentions = []
            
            # Create message
            return Message(
                id=id_str,
                sender_id='',  # Will be set by caller
                sender_nickname=sender_str,
                recipient_id=recipient_str,
                content=content_bytes.decode('utf-8'),
                channel=channel_str,
                is_private=is_private,
                is_encrypted=is_encrypted,
                encrypted_content=encrypted_bytes,
                mentions=mentions,
                timestamp=time.time()
            )
            
        except Exception as e:
            logger.error(f"Failed to parse message payload: {e}")
            return None
    
    async def _parse_fragment_packet(self, payload: bytes, fragment_type: FragmentType) -> Optional[Fragment]:
        """Parse fragment packet"""
        try:
            offset = 0
            
            # Fragment ID (8 bytes)
            fragment_id = payload[offset:offset+8].hex()
            offset += 8
            
            # Fragment index (2 bytes)
            index = struct.unpack('>H', payload[offset:offset+2])[0]
            offset += 2
            
            # Fragment total (2 bytes)
            total = struct.unpack('>H', payload[offset:offset+2])[0]
            offset += 2
            
            # Original type (1 byte)
            original_type = payload[offset]
            offset += 1
            
            # Fragment data
            data = payload[offset:]
            
            return Fragment(
                fragment_id=fragment_id,
                fragment_type=fragment_type,
                index=index,
                total=total,
                original_type=original_type,
                data=data
            )
            
        except Exception as e:
            logger.error(f"Failed to parse fragment packet: {e}")
            return None
    
    def _is_duplicate(self, message: Message) -> bool:
        """Check if message is a duplicate"""
        # Check if recently seen
        if message.id in self.seen_messages:
            return True
        
        # Check duplicate window
        current_time = time.time()
        if message.id in self.duplicate_window:
            if current_time - self.duplicate_window[message.id] < self.duplicate_timeout:
                return True
        
        return False
    
    def _mark_message_seen(self, message: Message, ttl: int):
        """Mark message as seen for duplicate detection"""
        current_time = time.time()
        
        # Add to seen messages
        self.seen_messages.add(message.id)
        
        # Add to duplicate window
        self.duplicate_window[message.id] = current_time
        
        # Clean up old entries
        expired_messages = []
        for msg_id, timestamp in self.duplicate_window.items():
            if current_time - timestamp > ttl:
                expired_messages.append(msg_id)
        
        for msg_id in expired_messages:
            del self.duplicate_window[msg_id]
    
    async def _cleanup_loop(self):
        """Background cleanup loop"""
        while self.running:
            try:
                # Clean up old fragment reassemblies
                current_time = time.time()
                expired_fragments = []
                
                for fragment_id, reassembly in self.fragment_reassembly.items():
                    if current_time - reassembly.created_at > reassembly.timeout:
                        expired_fragments.append(fragment_id)
                
                for fragment_id in expired_fragments:
                    del self.fragment_reassembly[fragment_id]
                
                if expired_fragments:
                    logger.debug(f"Cleaned up {len(expired_fragments)} expired fragment reassemblies")
                
                # Clean up duplicate window
                expired_messages = []
                for msg_id, timestamp in self.duplicate_window.items():
                    if current_time - timestamp > self.duplicate_timeout:
                        expired_messages.append(msg_id)
                
                for msg_id in expired_messages:
                    del self.duplicate_window[msg_id]
                    if msg_id in self.seen_messages:
                        self.seen_messages.remove(msg_id)
                
                if expired_messages:
                    logger.debug(f"Cleaned up {len(expired_messages)} expired message IDs")
                
                # Sleep between cleanup cycles
                await asyncio.sleep(10)  # Every 10 seconds
                
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(1)  # Prevent tight error loop
    
    def get_stats(self) -> Dict[str, Any]:
        """Get transport statistics"""
        stats = {
            'messages_sent': self.delivery_stats.messages_sent,
            'messages_delivered': self.delivery_stats.messages_delivered,
            'messages_failed': self.delivery_stats.messages_failed,
            'fragments_sent': self.delivery_stats.fragments_sent,
            'fragments_reassembled': self.delivery_stats.fragments_reassembled,
            'bytes_sent': self.delivery_stats.bytes_sent,
            'bytes_received': self.delivery_stats.bytes_received,
            'queue_size': self.message_queue.qsize(),
            'seen_messages': len(self.seen_messages),
            'duplicate_window_size': len(self.duplicate_window),
            'fragment_reassemblies': len(self.fragment_reassembly),
            'running': self.running
        }
        
        # Add metrics if available
        if self.metrics:
            metrics = self.metrics.get_metrics_summary()
            stats.update(metrics)
        
        return stats
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get message queue status"""
        # Count messages by priority
        priority_counts = {
            MessagePriority.CRITICAL.value: 0,
            MessagePriority.HIGH.value: 0,
            MessagePriority.NORMAL.value: 0,
            MessagePriority.LOW.value: 0
        }
        
        # Count messages in queue
        temp_queue = []
        while not self.message_queue.empty():
            priority, _ = self.message_queue.get_nowait()
            priority_counts[priority] += 1
            temp_queue.append((priority, _))
        
        # Put messages back
        for item in temp_queue:
            self.message_queue.put_nowait(item)
        
        return {
            'total_messages': sum(priority_counts.values()),
            'critical': priority_counts[MessagePriority.CRITICAL.value],
            'high': priority_counts[MessagePriority.HIGH.value],
            'normal': priority_counts[MessagePriority.NORMAL.value],
            'low': priority_counts[MessagePriority.LOW.value],
            'queue_size': self.message_queue.qsize()
        }