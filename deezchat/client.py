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
        
        logger.info(f"DeezChat client initialized with fingerprint: {self.security_layer.fingerprint}")
        
    async def start(self) -> bool:
        """Start the client"""
        try:
            self.state.running = True
            logger.info("Starting DeezChat client...")
            
            # Start UI
            await self.ui_layer.start()
            await self.ui_layer.display_status(f"Client started (fingerprint: {self.security_layer.fingerprint})")
            
            # Main loop
            while self.state.running:
                await asyncio.sleep(0.1)
                
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
        logger.info("Client stopped")