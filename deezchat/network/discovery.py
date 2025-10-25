"""
Peer discovery module for DeezChat

Handles Bluetooth Low Energy device discovery and peer management.
"""

import os
import asyncio
import logging
import time
import hashlib
from typing import Dict, List, Optional, Callable, Set
from dataclasses import dataclass, field
from enum import Enum

from bleak import BleakScanner, BLEDevice
from bleak.exc import BleakError

from ..storage.config import Config
from ..utils.metrics import MetricsCollector

logger = logging.getLogger(__name__)

class DiscoveryState(Enum):
    """Discovery states"""
    IDLE = "idle"
    SCANNING = "scanning"
    PROCESSING = "processing"
    ERROR = "error"

@dataclass
class PeerInfo:
    """Information about a discovered peer"""
    peer_id: str
    device: BLEDevice
    name: str
    first_seen: float
    last_seen: float
    rssi: int
    services: List[str]
    is_bitchat: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)
    
    def update_seen(self):
        """Update last seen time"""
        self.last_seen = time.time()

class PeerDiscoveryError(Exception):
    """Peer discovery related errors"""
    pass

class PeerDiscovery:
    """Peer discovery service for DeezChat"""
    
    def __init__(self, config: Config):
        self.config = config
        self.scanner = None
        self.discovered_peers: Dict[str, PeerInfo] = {}
        self.active_peers: Set[str] = set()
        self.state = DiscoveryState.IDLE
        
        # Event callbacks
        self.event_handlers: Dict[str, List[Callable]] = {}
        
        # Background tasks
        self.scan_task = None
        self.cleanup_task = None
        self.running = False
        
        # Metrics
        self.metrics = MetricsCollector() if config.performance.enable_metrics else None
        
        logger.info("Peer discovery initialized")
    
    async def start(self):
        """Start peer discovery"""
        if self.running:
            logger.warning("Peer discovery already running")
            return False
        
        self.running = True
        self.state = DiscoveryState.SCANNING
        
        try:
            # Initialize scanner
            self.scanner = BleakScanner()
            
            # Start background tasks
            self.scan_task = asyncio.create_task(self._scan_loop())
            self.cleanup_task = asyncio.create_task(self._cleanup_loop())
            
            logger.info("Peer discovery started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start peer discovery: {e}")
            self.state = DiscoveryState.ERROR
            return False
    
    async def stop(self):
        """Stop peer discovery"""
        if not self.running:
            logger.warning("Peer discovery not running")
            return False
        
        self.running = False
        self.state = DiscoveryState.IDLE
        
        try:
            # Stop scanner
            if self.scanner:
                await self.scanner.stop()
                self.scanner = None
            
            # Stop background tasks
            if self.scan_task:
                self.scan_task.cancel()
                try:
                    await self.scan_task
                except asyncio.CancelledError:
                    pass
            
            if self.cleanup_task:
                self.cleanup_task.cancel()
                try:
                    await self.cleanup_task
                except asyncio.CancelledError:
                    pass
            
            logger.info("Peer discovery stopped")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop peer discovery: {e}")
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
    
    def _trigger_event(self, event: str, data: Dict[str, any]):
        """Trigger event handlers"""
        if event in self.event_handlers:
            for handler in self.event_handlers[event]:
                try:
                    # Create a task for each handler to avoid blocking
                    asyncio.create_task(handler(data))
                except Exception as e:
                    logger.error(f"Event handler error for {event}: {e}")
    
    async def _scan_loop(self):
        """Background scanning loop"""
        while self.running:
            try:
                self.state = DiscoveryState.SCANNING
                
                # Scan for devices with timeout
                devices = await self.scanner.discover(
                    timeout=5.0,
                    return_adv=True
                )
                
                self.state = DiscoveryState.PROCESSING
                
                # Process discovered devices
                new_peers = await self._process_discovered_devices(devices)
                
                # Update discovered peers
                old_peer_ids = set(self.discovered_peers.keys())
                new_peer_ids = set(new_peers.keys())
                
                # Trigger peer left events
                for peer_id in old_peer_ids - new_peer_ids:
                    peer_info = self.discovered_peers[peer_id]
                    self._trigger_event('peer_left', {
                        'peer_id': peer_id,
                        'peer_info': peer_info
                    })
                
                # Trigger peer discovered events
                for peer_id, peer_info in new_peers.items():
                    if peer_id not in old_peer_ids:
                        self._trigger_event('peer_discovered', {
                            'peer_id': peer_id,
                            'peer_info': peer_info
                        })
                
                # Update discovered peers
                self.discovered_peers = new_peers
                
                # Update metrics
                if self.metrics:
                    self.metrics.increment_counter('peers.discovered', len(new_peers))
                    self.metrics.set_gauge('peers.total', len(self.discovered_peers))
                
                # Sleep between scans
                await asyncio.sleep(self.config.network.scan_interval)
                
            except Exception as e:
                logger.error(f"Error in scan loop: {e}")
                self.state = DiscoveryState.ERROR
                await asyncio.sleep(1)  # Prevent tight error loop
    
    async def _process_discovered_devices(self, devices: List[BLEDevice]) -> Dict[str, PeerInfo]:
        """Process discovered devices and extract peer information"""
        peers = {}
        
        for device in devices:
            # Check if device is a BitChat peer
            peer_info = await self._extract_peer_info(device)
            
            if peer_info:
                peers[peer_info.peer_id] = peer_info
                
                # Update metrics
                if self.metrics:
                    if peer_info.is_bitchat:
                        self.metrics.increment_counter('peers.bitchat_discovered', 1)
                    else:
                        self.metrics.increment_counter('peers.non_bitchat_discovered', 1)
        
        return peers
    
    async def _extract_peer_info(self, device: BLEDevice) -> Optional[PeerInfo]:
        """Extract peer information from device"""
        try:
            # Check if device has BitChat service
            is_bitchat = await self._has_bitchat_service(device)
            
            if not is_bitchat:
                return None
            
            # Generate peer ID
            peer_id = self._generate_peer_id(device)
            
            # Get device name
            name = device.name or f"Device-{device.address[:8]}"
            
            # Get RSSI
            rssi = device.rssi if device.rssi else 0
            
            # Get services
            services = []
            if device.metadata and 'uuids' in device.metadata:
                services = [str(uuid) for uuid in device.metadata['uuids']]
            
            # Get metadata
            metadata = {}
            if device.metadata:
                if 'manufacturer_data' in device.metadata:
                    metadata['manufacturer'] = str(device.metadata['manufacturer_data'])
                
                if 'service_data' in device.metadata:
                    metadata['services'] = str(device.metadata['service_data'])
            
            # Create peer info
            peer_info = PeerInfo(
                peer_id=peer_id,
                device=device,
                name=name,
                first_seen=time.time(),
                last_seen=time.time(),
                rssi=rssi,
                services=services,
                is_bitchat=is_bitchat,
                metadata=metadata
            )
            
            return peer_info
            
        except Exception as e:
            logger.error(f"Error extracting peer info from {device.name}: {e}")
            return None
    
    async def _has_bitchat_service(self, device: BLEDevice) -> bool:
        """Check if device has BitChat service"""
        if not device.metadata:
            return False
        
        # Check for BitChat service UUID
        service_uuids = device.metadata.get('uuids', [])
        
        for uuid in service_uuids:
            if str(uuid).lower() in [
                "6e400001-b5a3-f393-e0a9-e50e24dcca9e",  # BitChat service
                "6e400001-b5a3-f393-e0a9-e50e24dcca9e-12"  # Alternative UUID
            ]:
                return True
        
        return False
    
    def _generate_peer_id(self, device: BLEDevice) -> str:
        """Generate peer ID from device"""
        # Try to extract from device name
        if device.name and device.name.startswith('DeezChat-'):
            return device.name[10:]  # Remove 'DeezChat-' prefix
        
        # Try to extract from manufacturer data
        if device.metadata and 'manufacturer_data' in device.metadata:
            mfg_data = device.metadata['manufacturer_data']
            if len(mfg_data) >= 16:
                return hashlib.sha256(mfg_data[:16]).hexdigest()[:16]
        
        # Try to extract from device address
        if device.address:
            return hashlib.sha256(device.address.encode()).hexdigest()[:16]
        
        # Generate random ID as fallback
        import os
        return hashlib.sha256(os.urandom(16)).hexdigest()[:16]
    
    async def _cleanup_loop(self):
        """Background cleanup loop"""
        while self.running:
            try:
                # Clean up stale peers
                await self._cleanup_stale_peers()
                
                # Sleep between cleanup cycles
                await asyncio.sleep(60)  # Every minute
                
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(5)  # Prevent tight error loop
    
    async def _cleanup_stale_peers(self):
        """Clean up stale peers"""
        current_time = time.time()
        stale_peers = []
        
        for peer_id, peer_info in self.discovered_peers.items():
            # Remove peers not seen for 5 minutes
            if current_time - peer_info.last_seen > 300:
                stale_peers.append(peer_id)
                
                # Trigger peer left event
                self._trigger_event('peer_left', {
                    'peer_id': peer_id,
                    'peer_info': peer_info
                })
        
        # Remove stale peers
        for peer_id in stale_peers:
            del self.discovered_peers[peer_id]
            if peer_id in self.active_peers:
                self.active_peers.remove(peer_id)
        
        if stale_peers:
            logger.info(f"Cleaned up {len(stale_peers)} stale peers")
            
            # Update metrics
            if self.metrics:
                self.metrics.increment_counter('peers.cleaned_up', len(stale_peers))
    
    async def connect_to_peer(self, peer_id: str) -> bool:
        """Connect to a specific peer"""
        if peer_id not in self.discovered_peers:
            logger.warning(f"Peer {peer_id} not discovered")
            return False
        
        peer_info = self.discovered_peers[peer_id]
        
        try:
            # Add to active peers
            self.active_peers.add(peer_id)
            peer_info.update_seen()
            
            # Trigger peer connected event
            self._trigger_event('peer_connected', {
                'peer_id': peer_id,
                'peer_info': peer_info
            })
            
            logger.info(f"Connected to peer {peer_id} ({peer_info.name})")
            
            # Update metrics
            if self.metrics:
                self.metrics.increment_counter('peers.connected', 1)
                self.metrics.set_gauge('peers.active', len(self.active_peers))
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to peer {peer_id}: {e}")
            return False
    
    async def disconnect_from_peer(self, peer_id: str) -> bool:
        """Disconnect from a specific peer"""
        if peer_id not in self.active_peers:
            logger.warning(f"Not connected to peer {peer_id}")
            return False
        
        try:
            # Remove from active peers
            self.active_peers.remove(peer_id)
            
            # Trigger peer disconnected event
            if peer_id in self.discovered_peers:
                peer_info = self.discovered_peers[peer_id]
                self._trigger_event('peer_disconnected', {
                    'peer_id': peer_id,
                    'peer_info': peer_info
                })
            
            logger.info(f"Disconnected from peer {peer_id}")
            
            # Update metrics
            if self.metrics:
                self.metrics.set_gauge('peers.active', len(self.active_peers))
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to disconnect from peer {peer_id}: {e}")
            return False
    
    def get_peer_info(self, peer_id: str) -> Optional[PeerInfo]:
        """Get information about a peer"""
        return self.discovered_peers.get(peer_id)
    
    def get_active_peers(self) -> List[str]:
        """Get list of active peer IDs"""
        return list(self.active_peers)
    
    def get_discovered_peers(self) -> List[str]:
        """Get list of discovered peer IDs"""
        return list(self.discovered_peers.keys())
    
    def is_peer_active(self, peer_id: str) -> bool:
        """Check if peer is active"""
        return peer_id in self.active_peers
    
    def is_peer_discovered(self, peer_id: str) -> bool:
        """Check if peer is discovered"""
        return peer_id in self.discovered_peers
    
    def get_peer_count(self) -> Dict[str, int]:
        """Get peer count statistics"""
        return {
            'discovered': len(self.discovered_peers),
            'active': len(self.active_peers),
            'bitchat': sum(1 for peer in self.discovered_peers.values() if peer.is_bitchat)
        }
    
    def get_state(self) -> DiscoveryState:
        """Get current discovery state"""
        return self.state
    
    async def get_stats(self) -> Dict[str, any]:
        """Get discovery statistics"""
        stats = {
            'state': self.state.value,
            'running': self.running,
            'discovered_peers': len(self.discovered_peers),
            'active_peers': len(self.active_peers),
            'scan_interval': self.config.network.scan_interval
        }
        
        # Add metrics if available
        if self.metrics:
            metrics = self.metrics.get_metrics_summary()
            stats.update(metrics)
        
        return stats
    
    def force_scan(self) -> bool:
        """Force immediate scan"""
        if not self.running:
            logger.warning("Peer discovery not running")
            return False
        
        try:
            # Trigger immediate scan
            if self.scan_task:
                self.scan_task.cancel()
                try:
                    await self.scan_task
                except asyncio.CancelledError:
                    pass
                
                # Restart scan task
                self.scan_task = asyncio.create_task(self._scan_loop())
                
                logger.info("Forced immediate scan")
                return True
                
        except Exception as e:
            logger.error(f"Failed to force scan: {e}")
            return False
    
    def set_scan_interval(self, interval: int) -> bool:
        """Set scan interval"""
        if interval < 1:
            logger.warning("Scan interval must be >= 1 second")
            return False
        
        self.config.network.scan_interval = interval
        logger.info(f"Scan interval set to {interval} seconds")
        return True
    
    def get_peer_by_device_address(self, address: str) -> Optional[PeerInfo]:
        """Get peer by device address"""
        for peer_id, peer_info in self.discovered_peers.items():
            if peer_info.device.address == address:
                return peer_info
        
        return None
    
    def get_peer_by_device_name(self, name: str) -> Optional[PeerInfo]:
        """Get peer by device name"""
        for peer_id, peer_info in self.discovered_peers.items():
            if peer_info.name == name:
                return peer_info
        
        return None
    
    def search_peers(self, query: str) -> List[PeerInfo]:
        """Search for peers by name or ID"""
        query = query.lower()
        results = []
        
        for peer_info in self.discovered_peers.values():
            # Search by peer ID
            if query in peer_info.peer_id.lower():
                results.append(peer_info)
                continue
            
            # Search by name
            if query in peer_info.name.lower():
                results.append(peer_info)
                continue
            
            # Search by services
            for service in peer_info.services:
                if query in service.lower():
                    results.append(peer_info)
                    break
        
        return results
    
    def get_bitchat_peers(self) -> List[PeerInfo]:
        """Get list of BitChat peers only"""
        return [peer for peer in self.discovered_peers.values() if peer.is_bitchat]
    
    def get_nearby_peers(self, max_distance: int = -50) -> List[PeerInfo]:
        """Get list of nearby peers based on RSSI"""
        nearby_peers = []
        
        for peer_info in self.discovered_peers.values():
            if peer_info.rssi >= max_distance:
                nearby_peers.append(peer_info)
        
        # Sort by signal strength (strongest first)
        nearby_peers.sort(key=lambda p: p.rssi, reverse=True)
        
        return nearby_peers
    
    def get_peer_statistics(self, peer_id: str) -> Optional[Dict[str, any]]:
        """Get statistics for a specific peer"""
        peer_info = self.discovered_peers.get(peer_id)
        if not peer_info:
            return None
        
        return {
            'peer_id': peer_id,
            'name': peer_info.name,
            'first_seen': peer_info.first_seen,
            'last_seen': peer_info.last_seen,
            'rssi': peer_info.rssi,
            'services': peer_info.services,
            'is_bitchat': peer_info.is_bitchat,
            'is_active': peer_id in self.active_peers,
            'uptime': peer_info.last_seen - peer_info.first_seen,
            'metadata': peer_info.metadata
        }