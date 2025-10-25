"""
BLE Network Layer for DeezChat

Handles Bluetooth Low Energy communication, peer discovery, and message transport.
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

from bleak import BleakScanner, BleakClient, BLEDevice
from bleak.exc import BleakError

from ..storage.config import Config
from ..utils.compression import compress_if_beneficial
from ..utils.frangmentation import fragment_payload, MAX_FRAGMENT_SIZE
from ..core.message import MessageType

logger = logging.getLogger(__name__)

class BLEConnectionState(Enum):
    """BLE connection states"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"

class BLEConnectionError(Exception):
    """BLE connection related errors"""
    pass

@dataclass
class BLEConnection:
    """Represents a BLE connection to a peer"""
    peer_id: str
    device: BLEDevice
    client: Optional[BleakClient] = None
    state: BLEConnectionState = BLEConnectionState.DISCONNECTED
    last_seen: float = field(default_factory=time.time)
    message_queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    connection_attempts: int = 0
    max_connection_attempts: int = 3
    
    async def connect(self) -> bool:
        """Establish BLE connection"""
        if self.state != BLEConnectionState.DISCONNECTED:
            logger.warning(f"Already connecting/connected to {self.peer_id}")
            return False
        
        self.state = BLEConnectionState.CONNECTING
        self.connection_attempts += 1
        
        try:
            # Create BLE client
            self.client = BleakClient(self.device.address)
            
            # Connect with timeout
            await self.client.connect(timeout=10.0)
            
            # Find BitChat characteristic
            services = await self.client.get_services()
            bitchat_service = None
            
            for service in services:
                if service.uuid.lower() == "6e400001-b5a3-f393-e0a9-e50e24dcca9e" or "6e400001-b5a3-f393-e0a9-e50e24dcca9e":
                    bitchat_service = service
                    break
            
            if not bitchat_service:
                raise BLEConnectionError(f"BitChat service not found on {self.device.name}")
            
            # Find characteristic
            characteristics = bitchat_service.characteristics
            bitchat_characteristic = None
            
            for char in characteristics:
                if char.uuid.lower() == "6e400002-b5a3-f393-e0a9-e50e24dcca9e-12" or "6e400002-b5a3-f393-e0a9-e50e24dcca9e-12":
                    bitchat_characteristic = char
                    break
            
            if not bitchat_characteristic:
                raise BLEConnectionError(f"BitChat characteristic not found on {self.device.name}")
            
            self.state = BLEConnectionState.CONNECTED
            self.last_seen = time.time()
            logger.info(f"Connected to {self.device.name} ({self.peer_id})")
            
            return True
            
        except Exception as e:
            self.state = BLEConnectionState.ERROR
            logger.error(f"Failed to connect to {self.device.name}: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from peer"""
        if self.client and self.state != BLEConnectionState.DISCONNECTED:
            try:
                await self.client.disconnect()
                self.state = BLEConnectionState.DISCONNECTED
                logger.info(f"Disconnected from {self.device.name} ({self.peer_id})")
            except Exception as e:
                logger.error(f"Error disconnecting from {self.device.name}: {e}")
                self.state = BLEConnectionState.ERROR
    
    async def send_packet(self, packet: bytes) -> bool:
        """Send packet over BLE"""
        if self.state != BLEConnectionState.CONNECTED:
            logger.warning(f"Not connected to {self.peer_id}, queuing packet")
            await self.message_queue.put(packet)
            return False
        
        try:
            # Compress packet if beneficial
            compressed, is_compressed = compress_if_beneficial(packet)
            
            # Check if packet needs fragmentation
            if len(compressed) > MAX_FRAGMENT_SIZE:
                # Fragment and send
                return await self._send_fragmented_packet(compressed)
            else:
                # Send directly
                await self.client.write_gatt_char(
                    self.bitchat_characteristic,
                    compressed
                )
                
                logger.debug(f"Sent {len(compressed)} bytes to {self.peer_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to send packet to {self.peer_id}: {e}")
            return False
    
    async def _send_fragmented_packet(self, packet: bytes) -> bool:
        """Send fragmented packet"""
        try:
            # Create fragments
            fragments = fragment_payload(packet, MessageType.MESSAGE.value)
            
            # Send fragments with small delay between them
            for i, fragment in enumerate(fragments):
                # Create fragment packet
                fragment_data = bytearray()
                
                # Fragment header
                fragment_data.extend(fragment.fragment_id)
                fragment_data.extend(struct.pack('>H', fragment.index))
                fragment_data.extend(struct.pack('>H', fragment.total))
                fragment_data.extend(fragment.original_type)
                fragment_data.extend(fragment.data)
                
                # Send fragment
                success = await self.send_packet(bytes(fragment_data))
                
                if not success:
                    logger.error(f"Failed to send fragment {i+1}/{len(fragments)}")
                    return False
                
                # Small delay between fragments
                if i < len(fragments) - 1:
                    await asyncio.sleep(0.01)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send fragmented packet: {e}")
            return False
    
    async def process_message_queue(self):
        """Process outgoing message queue"""
        while self.state == BLEConnectionState.CONNECTED:
            try:
                # Get packet from queue with timeout
                packet = await asyncio.wait_for(
                    self.message_queue.get(),
                    timeout=1.0
                )
                
                # Send packet
                await self.send_packet(packet)
                
            except asyncio.TimeoutError:
                # Queue is empty, wait for next packet
                continue
            except Exception as e:
                logger.error(f"Error processing message queue: {e}")
                await asyncio.sleep(0.1)
    
    def is_stale(self, timeout: float = 300.0) -> bool:
        """Check if connection is stale"""
        return time.time() - self.last_seen > timeout
    
    def get_stats(self) -> Dict[str, Any]:
        """Get connection statistics"""
        return {
            'state': self.state.value,
            'connection_attempts': self.connection_attempts,
            'last_seen': self.last_seen,
            'queue_size': self.message_queue.qsize(),
            'device_name': self.device.name if self.device else 'Unknown',
            'device_address': self.device.address if self.device else 'Unknown',
            'is_connected': self.state == BLEConnectionState.CONNECTED
        }

class BLEConnectionPool:
    """Pool of BLE connections for efficient resource management"""
    
    def __init__(self, max_connections: int = 10):
        self.max_connections = max_connections
        self.active_connections: Dict[str, BLEConnection] = {}
        self.connection_queue: asyncio.Queue = asyncio.Queue()
        self._lock = asyncio.Lock()
    
    async def get_connection(self, peer_id: str, device: BLEDevice) -> BLEConnection:
        """Get or create connection to peer"""
        async with self._lock:
            # Check if connection already exists
            if peer_id in self.active_connections:
                connection = self.active_connections[peer_id]
                
                # Check if device matches
                if connection.device.address == device.address:
                    return connection
                else:
                    # Device changed, disconnect old connection
                    await connection.disconnect()
                    del self.active_connections[peer_id]
            
            # Check if we have too many connections
            if len(self.active_connections) >= self.max_connections:
                # Queue connection request
                await self.connection_queue.put((peer_id, device))
                logger.warning(f"Connection request queued for {peer_id} (max connections reached)")
                
                # Create temporary connection that will be queued
                return BLEConnection(peer_id, device)
            
            # Create new connection
            connection = BLEConnection(peer_id, device)
            self.active_connections[peer_id] = connection
            
            # Start message queue processing
            asyncio.create_task(connection.process_message_queue())
            
            logger.info(f"Created new connection to {peer_id}")
            return connection
    
    async def release_connection(self, peer_id: str):
        """Release connection back to pool"""
        async with self._lock:
            if peer_id in self.active_connections:
                connection = self.active_connections[peer_id]
                
                # Disconnect if still connected
                if connection.state == BLEConnectionState.CONNECTED:
                    await connection.disconnect()
                
                # Remove from active connections
                del self.active_connections[peer_id]
                
                logger.debug(f"Released connection to {peer_id}")
                
                # Process queued connections
                if not self.connection_queue.empty():
                    queued_peer_id, queued_device = await self.connection_queue.get()
                    
                    # Check if we can create the queued connection
                    if len(self.active_connections) < self.max_connections:
                        await self.get_connection(queued_peer_id, queued_device)
    
    async def cleanup_idle_connections(self, idle_timeout: float = 300.0):
        """Clean up idle connections"""
        current_time = time.time()
        
        async with self._lock:
            stale_connections = []
            
            for peer_id, connection in self.active_connections.items():
                if connection.is_stale(idle_timeout):
                    stale_connections.append(peer_id)
            
            # Clean up stale connections
            for peer_id in stale_connections:
                connection = self.active_connections[peer_id]
                await connection.disconnect()
                del self.active_connections[peer_id]
                
            if stale_connections:
                logger.info(f"Cleaned up {len(stale_connections)} idle connections")
    
    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics for all connections"""
        total_connections = len(self.active_connections)
        connected = sum(1 for conn in self.active_connections.values() 
                      if conn.state == BLEConnectionState.CONNECTED)
        connecting = sum(1 for conn in self.active_connections.values() 
                       if conn.state == BLEConnectionState.CONNECTING)
        error = sum(1 for conn in self.active_connections.values() 
                   if conn.state == BLEConnectionState.ERROR)
        queued = self.connection_queue.qsize()
        
        return {
            'total_connections': total_connections,
            'connected': connected,
            'connecting': connecting,
            'error': error,
            'queued': queued,
            'max_connections': self.max_connections
        }

class BLENetworkLayer:
    """BLE network layer for DeezChat"""
    
    def __init__(self, config: Config):
        self.config = config
        self.my_peer_id = self._generate_peer_id()
        
        # BLE components
        self.scanner = None
        self.connection_pool = BLEConnectionPool(config.network.max_peers)
        self.discovered_peers: Dict[str, BLEDevice] = {}
        
        # Event callbacks
        self.event_handlers: Dict[str, List[Callable]] = {}
        
        # Background tasks
        self.scan_task = None
        self.cleanup_task = None
        self.running = False
        
        logger.info("BLE network layer initialized")
    
    def _generate_peer_id(self) -> str:
        """Generate unique peer ID"""
        return hashlib.sha256(os.urandom(16)).hexdigest()[:16]
    
    async def start(self):
        """Start BLE network layer"""
        if self.running:
            logger.warning("BLE network layer already running")
            return False
        
        self.running = True
        
        try:
            # Start scanner
            self.scanner = BleakScanner()
            
            # Start background tasks
            self.scan_task = asyncio.create_task(self._scan_loop())
            self.cleanup_task = asyncio.create_task(self._cleanup_loop())
            
            logger.info("BLE network layer started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start BLE network layer: {e}")
            return False
    
    async def stop(self):
        """Stop BLE network layer"""
        if not self.running:
            logger.warning("BLE network layer not running")
            return False
        
        self.running = False
        
        try:
            # Stop scanner
            if self.scan_task:
                self.scan_task.cancel()
                try:
                    await self.scan_task
                except asyncio.CancelledError:
                    pass
            
            # Stop cleanup task
            if self.cleanup_task:
                self.cleanup_task.cancel()
                try:
                    await self.cleanup_task
                except asyncio.CancelledError:
                    pass
            
            # Disconnect all connections
            for connection in self.connection_pool.active_connections.values():
                await connection.disconnect()
            
            # Clear connection pool
            self.connection_pool.active_connections.clear()
            self.discovered_peers.clear()
            
            logger.info("BLE network layer stopped")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop BLE network layer: {e}")
            return False
    
    async def _scan_loop(self):
        """Background scanning loop"""
        while self.running:
            try:
                # Scan for devices with BitChat service
                devices = await self.scanner.discover(
                    timeout=5.0,
                    return_adv=True
                )
                
                # Filter and process discovered devices
                new_peers = {}
                
                for device in devices:
                    # Check if device has BitChat service
                    if self._has_bitchat_service(device):
                        peer_id = self._get_peer_id_from_device(device)
                        
                        # Add to discovered peers if new
                        if peer_id not in self.discovered_peers:
                            new_peers[peer_id] = device
                            
                            # Trigger peer discovered event
                            self._trigger_event('peer_discovered', {
                                'peer_id': peer_id,
                                'device': device
                            })
                
                # Update discovered peers
                old_peers = set(self.discovered_peers.keys())
                new_peer_ids = set(new_peers.keys())
                
                # Trigger peer left events for disappeared peers
                for peer_id in old_peers - new_peer_ids:
                    device = self.discovered_peers[peer_id]
                    self._trigger_event('peer_left', {
                        'peer_id': peer_id,
                        'device': device
                    })
                
                self.discovered_peers = new_peers
                
                # Sleep between scans
                await asyncio.sleep(self.config.network.scan_interval)
                
            except Exception as e:
                logger.error(f"Error in scan loop: {e}")
                await asyncio.sleep(1)  # Prevent tight error loop
    
    def _has_bitchat_service(self, device: BLEDevice) -> bool:
        """Check if device advertises BitChat service"""
        if not device.metadata:
            return False
        
        for service_uuid in device.metadata.get('uuids', []):
            if service_uuid.lower() in [
                "6e400001-b5a3-f393-e0a9-e50e24dcca9e",  # BitChat service
                "6e400001-b5a3-f393-e0a9-e50e24dcca9e"   # Alternative UUID
            ]:
                return True
        
        return False
    
    def _get_peer_id_from_device(self, device: BLEDevice) -> str:
        """Extract peer ID from device advertisement"""
        # Check device name for peer ID pattern
        if device.name and device.name.startswith('DeezChat-'):
            return device.name[10:]  # Remove 'DeezChat-' prefix
        
        # Check manufacturer data for peer ID
        if device.metadata and 'manufacturer_data' in device.metadata:
            mfg_data = device.metadata['manufacturer_data']
            if len(mfg_data) >= 16:
                return hashlib.sha256(mfg_data[:16]).hexdigest()[:16]
        
        # Generate random ID if not found
        return self._generate_peer_id()
    
    async def _cleanup_loop(self):
        """Background cleanup loop"""
        while self.running:
            try:
                # Clean up idle connections
                await self.connection_pool.cleanup_idle_connections(
                    idle_timeout=self.config.network.connection_timeout
                )
                
                # Clean up stale discovered peers
                current_time = time.time()
                stale_peers = []
                
                for peer_id, device in self.discovered_peers.items():
                    # Check if device hasn't been seen recently
                    if current_time - device.rssi > 60:  # 60 seconds
                        stale_peers.append(peer_id)
                
                # Remove stale peers
                for peer_id in stale_peers:
                    device = self.discovered_peers[peer_id]
                    self._trigger_event('peer_left', {
                        'peer_id': peer_id,
                        'device': device
                    })
                    del self.discovered_peers[peer_id]
                
                # Sleep between cleanup cycles
                await asyncio.sleep(30)  # Every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(5)  # Prevent tight error loop
    
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
    
    async def connect_to_device(self, device: BLEDevice) -> bool:
        """Connect to specific device"""
        peer_id = self._get_peer_id_from_device(device)
        
        # Get connection from pool
        connection = await self.connection_pool.get_connection(peer_id, device)
        
        # Connect to device
        success = await connection.connect()
        
        if success:
            self._trigger_event('connected', {
                'peer_id': peer_id,
                'device': device
            })
        else:
            self._trigger_event('connection_failed', {
                'peer_id': peer_id,
                'device': device,
                'error': 'Connection failed'
            })
        
        return success
    
    async def disconnect_from_device(self, peer_id: str):
        """Disconnect from specific device"""
        await self.connection_pool.release_connection(peer_id)
        
        self._trigger_event('disconnected', {
            'peer_id': peer_id
        })
    
    async def send_packet_to_peer(self, peer_id: str, packet: bytes) -> bool:
        """Send packet to specific peer"""
        if peer_id not in self.connection_pool.active_connections:
            logger.warning(f"No connection to {peer_id}")
            return False
        
        connection = self.connection_pool.active_connections[peer_id]
        return await connection.send_packet(packet)
    
    def get_peer_info(self, peer_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a peer"""
        if peer_id in self.connection_pool.active_connections:
            connection = self.connection_pool.active_connections[peer_id]
            return {
                'peer_id': peer_id,
                'device_name': connection.device.name if connection.device else 'Unknown',
                'device_address': connection.device.address if connection.device else 'Unknown',
                'state': connection.state.value,
                'last_seen': connection.last_seen,
                'stats': connection.get_stats()
            }
        
        return None
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get network layer statistics"""
        pool_stats = self.connection_pool.get_all_stats()
        
        return {
            'my_peer_id': self.my_peer_id,
            'discovered_peers': len(self.discovered_peers),
            'active_connections': pool_stats['total_connections'],
            'connected_peers': pool_stats['connected'],
            'connecting_peers': pool_stats['connecting'],
            'error_peers': pool_stats['error'],
            'queued_connections': pool_stats['queued'],
            'running': self.running,
            'scan_interval': self.config.network.scan_interval,
            'max_connections': self.config.network.max_peers
        }
    
    def create_packet(self, message_type: int, payload: bytes, 
                  recipient_id: Optional[str] = None) -> bytes:
        """Create a BitChat packet"""
        # Packet header
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
        if recipient_id:
            flags |= 0x01  # Has recipient
        
        packet.append(flags)
        
        # Payload length (2 bytes)
        payload_length = len(payload)
        packet.extend(struct.pack('>H', payload_length))
        
        # Sender ID (8 bytes)
        sender_bytes = bytes.fromhex(self.my_peer_id.ljust(16, '0'))
        packet.extend(sender_bytes)
        
        # Recipient ID (8 bytes) if present
        if recipient_id:
            recipient_bytes = bytes.fromhex(recipient_id.ljust(16, '0'))
            packet.extend(recipient_bytes)
        
        # Payload
        packet.extend(payload)
        
        return bytes(packet)
    
    def create_public_message_packet(self, content: bytes) -> bytes:
        """Create public message packet"""
        return self.create_packet(MessageType.MESSAGE.value, content)
    
    def create_private_message_packet(self, recipient_id: str, content: bytes) -> bytes:
        """Create private message packet"""
        return self.create_packet(MessageType.MESSAGE.value, content, recipient_id)
    
    def create_channel_message_packet(self, channel: str, content: bytes) -> bytes:
        """Create channel message packet"""
        # Add channel to payload
        payload = bytearray()
        
        # Flags (1 byte)
        flags = 0x02  # Has channel
        
        # Channel length (1 byte)
        channel_bytes = channel.encode('utf-8')
        payload.append(flags)
        payload.append(len(channel_bytes))
        payload.extend(channel_bytes)
        
        # Content
        payload.extend(content)
        
        return self.create_packet(MessageType.MESSAGE.value, bytes(payload))