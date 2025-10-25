"""
Main DeezChat client implementation
"""

import asyncio
import logging
from typing import Optional
from dataclasses import dataclass, field
import time

from .storage.config import ConfigManager
from .security.noise import NoiseSecurityLayer
from .ui.terminal import TerminalInterface
from .network.discovery import PeerDiscovery
from .network.ble import BLENetworkLayer

logger = logging.getLogger(__name__)

@dataclass
class ClientState:
    """Client state tracking"""
    running: bool = False
    connected: bool = False
    peer_count: int = 0
    last_error: Optional[str] = None
    uptime: float = field(default_factory=time.time)

class DeezChatClient:
    """Simplified DeezChat client"""
    
    def __init__(self, config_path: Optional[str] = None, data_dir: Optional[str] = None):
        self.config_manager = ConfigManager(config_path)
        self.config = self.config_manager.config
        self.state = ClientState()
        
        # Initialize core components
        self.security_layer = NoiseSecurityLayer(self.config)
        self.ui_layer = TerminalInterface(self.config)
        self.peer_discovery = PeerDiscovery(self.config)
        self.ble_network = BLENetworkLayer(self.config)
        
        # Setup event handlers
        self.peer_discovery.register_event_handler('peer_discovered', self._on_peer_discovered)
        self.peer_discovery.register_event_handler('peer_left', self._on_peer_left)
        
        logger.info(f"DeezChat client initialized with fingerprint: {self.security_layer.fingerprint}")
        
    async def start(self) -> bool:
        """Start the client"""
        try:
            self.state.running = True
            logger.info("Starting DeezChat client...")
            
            # Start BLE network discovery
            await self.peer_discovery.start()
            
            # Start UI
            await self.ui_layer.start()
            await self.ui_layer.display_status(f"Client started (fingerprint: {self.security_layer.fingerprint})")
            await self.ui_layer.display_status("Scanning for BitChat peers...")
            
            # Main event loop
            while self.state.running:
                # Update peer count
                bitchat_peers = self.peer_discovery.get_bitchat_peers()
                self.state.peer_count = len(bitchat_peers)
                
                if self.state.peer_count > 0:
                    await self.ui_layer.display_status(f"Found {self.state.peer_count} BitChat peer(s)")
                
                await asyncio.sleep(1)  # Check every second
                
            return True
            
        except Exception as e:
            logger.error(f"Failed to start client: {e}")
            self.state.last_error = str(e)
            return False
            
    async def stop(self):
        """Stop the client"""
        logger.info("Stopping DeezChat client...")
        self.state.running = False
        
        await self.ui_layer.stop()
        await self.peer_discovery.stop()
        logger.info("Client stopped")
    
    async def _on_peer_discovered(self, data):
        """Handle peer discovery event"""
        peer_info = data.get('peer_info')
        if peer_info and peer_info.is_bitchat:
            await self.ui_layer.display_status(f"📱 BitChat peer found: {peer_info.name}")
    
    async def _on_peer_left(self, data):
        """Handle peer left event"""
        peer_info = data.get('peer_info')
        if peer_info:
            await self.ui_layer.display_status(f"👋 Peer left: {peer_info.name}")