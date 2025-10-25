"""
Main DeezChat client implementation

Orchestrates all components and provides the main application interface.
"""

import os
import sys
import time
import asyncio
import logging
from typing import Optional, Dict, List, Any, Callable
from pathlib import Path
from dataclasses import dataclass, field

from ..storage.config import ConfigManager, Config
from ..storage.database import DatabaseLayer, Message, MessageFilters
from ..ui.terminal import TerminalInterface
from ..network.ble import BLENetworkLayer
from ..security.noise import NoiseSecurityLayer

logger = logging.getLogger(__name__)

@dataclass
class ClientState:
    """Client state tracking"""
    running: bool = False
    connected: bool = False
    peer_count: int = 0
    active_channels: List[str] = field(default_factory=list)
    active_dms: List[str] = field(default_factory=list)
    last_error: Optional[str] = None
    uptime: float = field(default_factory=time.time)

class DeezChatClient:
    """Main DeezChat client orchestrator"""
    
    def __init__(self, config_path: Optional[str] = None):
        # Initialize configuration
        self.config_manager = ConfigManager(config_path)
        self.config = self.config_manager.config
        
        # Initialize state
        self.state = ClientState()
        
        # Initialize components
        self.db_layer = DatabaseLayer(self.config)
        self.network_layer = BLENetworkLayer(self.config)
        self.security_layer = NoiseSecurityLayer(self.config)
        self.ui_layer = TerminalInterface(self.config)
        
        # Event callbacks
        self.event_handlers: Dict[str, List[Callable]] = {}
        
        # Performance tracking
        self.metrics = {
            'messages_sent': 0,
            'messages_received': 0,
            'files_sent': 0,
            'files_received': 0,
            'connections_established': 0,
            'handshakes_completed': 0,
            'errors': 0
        }
        
        # Setup logging
        self._setup_logging()
        
        # Register event handlers
        self._register_event_handlers()
        
        logger.info("DeezChat client initialized")
    
    def _setup_logging(self):
        """Setup logging based on configuration"""
        log_level = getattr(logging, self.config.logging.level.upper(), logging.INFO)
        
        # Configure root logger
        logging.basicConfig(
            level=log_level,
            format=self.config.logging.format,
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Add file handler if configured
        if self.config.logging.file:
            log_file = self.config_manager.get_effective_log_file()
            log_dir = os.path.dirname(log_file)
            os.makedirs(log_dir, exist_ok=True)
            
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(log_level)
            
            # Add rotation if configured
            if self.config.logging.backup_count > 0:
                from logging.handlers import RotatingFileHandler
                file_handler = RotatingFileHandler(
                    log_file,
                    maxBytes=self._parse_size(self.config.logging.max_size),
                    backupCount=self.config.logging.backup_count
                )
            
            file_handler.setFormatter(logging.Formatter(self.config.logging.format))
            logging.getLogger().addHandler(file_handler)
        
        # Disable console output if configured
        if not self.config.logging.console_output:
            logging.getLogger().handlers = [
                h for h in logging.getLogger().handlers
                if not isinstance(h, logging.FileHandler)
            ]
        
        logger.debug(f"Logging configured at level {self.config.logging.level}")
    
    def _parse_size(self, size_str: str) -> int:
        """Parse size string (e.g., '10MB') to bytes"""
        size_str = size_str.upper().strip()
        
        if size_str.endswith('KB'):
            return int(size_str[:-2]) * 1024
        elif size_str.endswith('MB'):
            return int(size_str[:-2]) * 1024 * 1024
        elif size_str.endswith('GB'):
            return int(size_str[:-2]) * 1024 * 1024 * 1024
        else:
            return int(size_str)
    
    def _register_event_handlers(self):
        """Register event handlers"""
        self.event_handlers = {
            'connected': [],
            'disconnected': [],
            'message_received': [],
            'message_sent': [],
            'file_received': [],
            'file_sent': [],
            'error': [],
            'peer_joined': [],
            'peer_left': [],
            'channel_joined': [],
            'channel_left': []
        }
    
    async def start(self):
        """Start the DeezChat client"""
        if self.state.running:
            logger.warning("Client is already running")
            return False
        
        logger.info("Starting DeezChat client")
        self.state.running = True
        self.state.uptime = time.time()
        
        try:
            # Start database layer
            await self.db_layer.start()
            
            # Start network layer
            await self.network_layer.start()
            
            # Start UI layer
            await self.ui_layer.start(self)
            
            # Start background tasks
            asyncio.create_task(self._metrics_loop())
            asyncio.create_task(self._cleanup_loop())
            
            logger.info("DeezChat client started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start client: {e}")
            self.state.last_error = str(e)
            self._trigger_event('error', {'error': e})
            return False
    
    async def stop(self):
        """Stop the DeezChat client"""
        if not self.state.running:
            logger.warning("Client is not running")
            return False
        
        logger.info("Stopping DeezChat client")
        self.state.running = False
        
        try:
            # Stop UI layer
            await self.ui_layer.stop()
            
            # Stop network layer
            await self.network_layer.stop()
            
            # Stop database layer
            await self.db_layer.stop()
            
            logger.info("DeezChat client stopped successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop client: {e}")
            self.state.last_error = str(e)
            self._trigger_event('error', {'error': e})
            return False
    
    def register_event_handler(self, event: str, handler: Callable):
        """Register event handler"""
        if event in self.event_handlers:
            self.event_handlers[event].append(handler)
            logger.debug(f"Registered handler for event: {event}")
            return True
        else:
            logger.warning(f"Unknown event: {event}")
            return False
    
    def unregister_event_handler(self, event: str, handler: Callable):
        """Unregister event handler"""
        if event in self.event_handlers and handler in self.event_handlers[event]:
            self.event_handlers[event].remove(handler)
            logger.debug(f"Unregistered handler for event: {event}")
            return True
        else:
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
    
    async def send_message(self, content: str, channel: Optional[str] = None, 
                       recipient_id: Optional[str] = None) -> bool:
        """Send a message"""
        try:
            # Create message object
            message = Message(
                id=self._generate_message_id(),
                sender_id=self.network_layer.my_peer_id,
                sender_nickname=self.config.ui.nickname,
                recipient_id=recipient_id,
                content=content,
                channel=channel,
                is_private=bool(recipient_id),
                timestamp=time.time()
            )
            
            # Store in database
            await self.db_layer.store_message(message)
            
            # Route message
            success = await self._route_message(message)
            
            if success:
                self.metrics['messages_sent'] += 1
                self._trigger_event('message_sent', {'message': message})
            else:
                self.metrics['errors'] += 1
                self._trigger_event('error', {'error': 'Failed to send message'})
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            self.metrics['errors'] += 1
            self._trigger_event('error', {'error': e})
            return False
    
    async def _route_message(self, message: Message) -> bool:
        """Route message to appropriate handler"""
        try:
            # Get network status
            if not self.state.connected:
                logger.warning("Not connected, message queued")
                return False
            
            # Handle private messages
            if message.is_private:
                return await self._send_private_message(message)
            
            # Handle channel messages
            if message.channel:
                return await self._send_channel_message(message)
            
            # Handle public messages
            return await self._send_public_message(message)
            
        except Exception as e:
            logger.error(f"Failed to route message: {e}")
            return False
    
    async def _send_private_message(self, message: Message) -> bool:
        """Send private message"""
        try:
            # Check if we have a secure session with recipient
            if not self.security_layer.is_session_established(message.recipient_id):
                # Initiate handshake
                await self.security_layer.initiate_handshake(message.recipient_id)
                logger.info(f"Initiated handshake with {message.recipient_id}")
                # Message will be sent after handshake completes
                return True
            
            # Encrypt message
            encrypted_content = self.security_layer.encrypt_for_peer(
                message.recipient_id,
                message.content.encode('utf-8')
            )
            
            # Create packet
            packet = self.network_layer.create_private_message_packet(
                message.recipient_id,
                encrypted_content
            )
            
            # Send packet
            success = await self.network_layer.send_packet(packet)
            
            if success:
                logger.debug(f"Sent private message to {message.recipient_id}")
            else:
                logger.error(f"Failed to send private message to {message.recipient_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to send private message: {e}")
            return False
    
    async def _send_channel_message(self, message: Message) -> bool:
        """Send channel message"""
        try:
            # Check if channel is password protected
            if message.channel in self.security_layer.password_protected_channels:
                # Encrypt with channel key
                channel_key = self.security_layer.get_channel_key(message.channel)
                if channel_key:
                    encrypted_content = self.security_layer.encrypt_for_channel(
                        message.content,
                        message.channel,
                        channel_key
                    )
                    
                    # Create encrypted packet
                    packet = self.network_layer.create_channel_message_packet(
                        message.channel,
                        encrypted_content
                    )
                else:
                    logger.warning(f"No key for password-protected channel: {message.channel}")
                    return False
            else:
                # Create regular packet
                packet = self.network_layer.create_channel_message_packet(
                    message.channel,
                    message.content.encode('utf-8')
                )
            
            # Send packet
            success = await self.network_layer.send_packet(packet)
            
            if success:
                logger.debug(f"Sent channel message to {message.channel}")
            else:
                logger.error(f"Failed to send channel message to {message.channel}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to send channel message: {e}")
            return False
    
    async def _send_public_message(self, message: Message) -> bool:
        """Send public message"""
        try:
            # Create public packet
            packet = self.network_layer.create_public_message_packet(
                message.content.encode('utf-8')
            )
            
            # Send packet
            success = await self.network_layer.send_packet(packet)
            
            if success:
                logger.debug("Sent public message")
            else:
                logger.error("Failed to send public message")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to send public message: {e}")
            return False
    
    def _generate_message_id(self) -> str:
        """Generate unique message ID"""
        import uuid
        return str(uuid.uuid4())
    
    async def join_channel(self, channel: str, password: Optional[str] = None) -> bool:
        """Join a channel"""
        try:
            # Check if already joined
            if channel in self.state.active_channels:
                logger.warning(f"Already joined channel: {channel}")
                return True
            
            # Handle password-protected channels
            if password:
                # Derive channel key
                channel_key = self.security_layer.derive_channel_key(password, channel)
                self.security_layer.set_channel_key(channel, channel_key)
                
                # Join as password-protected
                success = await self.network_layer.join_channel(channel, password_protected=True)
            else:
                # Join as regular channel
                success = await self.network_layer.join_channel(channel, password_protected=False)
            
            if success:
                self.state.active_channels.append(channel)
                logger.info(f"Joined channel: {channel}")
                self._trigger_event('channel_joined', {'channel': channel})
            else:
                logger.error(f"Failed to join channel: {channel}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to join channel: {e}")
            return False
    
    async def leave_channel(self, channel: str) -> bool:
        """Leave a channel"""
        try:
            # Check if in channel
            if channel not in self.state.active_channels:
                logger.warning(f"Not in channel: {channel}")
                return True
            
            # Leave channel
            success = await self.network_layer.leave_channel(channel)
            
            if success:
                self.state.active_channels.remove(channel)
                logger.info(f"Left channel: {channel}")
                self._trigger_event('channel_left', {'channel': channel})
                
                # Clean up channel key
                self.security_layer.remove_channel_key(channel)
            else:
                logger.error(f"Failed to leave channel: {channel}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to leave channel: {e}")
            return False
    
    async def start_private_dm(self, peer_id: str, peer_nickname: str) -> bool:
        """Start private DM with peer"""
        try:
            # Add to active DMs
            if peer_nickname not in self.state.active_dms:
                self.state.active_dms.append(peer_nickname)
                
            # Check if we have a secure session
            if not self.security_layer.is_session_established(peer_id):
                # Initiate handshake
                await self.security_layer.initiate_handshake(peer_id)
                logger.info(f"Initiated handshake with {peer_nickname}")
            
            # Switch UI to DM mode
            await self.ui_layer.switch_to_dm(peer_nickname, peer_id)
            
            logger.info(f"Started private DM with {peer_nickname}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start private DM: {e}")
            return False
    
    async def get_status(self) -> Dict[str, Any]:
        """Get current client status"""
        return {
            'running': self.state.running,
            'connected': self.state.connected,
            'peer_count': self.state.peer_count,
            'active_channels': self.state.active_channels.copy(),
            'active_dms': self.state.active_dms.copy(),
            'uptime': time.time() - self.state.uptime,
            'last_error': self.state.last_error,
            'metrics': self.metrics.copy(),
            'network_stats': await self.network_layer.get_stats(),
            'security_stats': await self.security_layer.get_stats(),
            'database_stats': await self.db_layer.get_database_stats()
        }
    
    async def _metrics_loop(self):
        """Background metrics collection loop"""
        while self.state.running:
            try:
                # Collect metrics from components
                network_stats = await self.network_layer.get_stats()
                security_stats = await self.security_layer.get_stats()
                db_stats = await self.db_layer.get_database_stats()
                
                # Update internal metrics
                self.metrics.update(network_stats)
                self.metrics.update(security_stats)
                self.metrics.update(db_stats)
                
                # Log metrics if enabled
                if self.config.performance.enable_metrics:
                    logger.debug(f"Metrics: {self.metrics}")
                
                # Sleep for configured interval
                await asyncio.sleep(self.config.performance.metrics_interval)
                
            except Exception as e:
                logger.error(f"Error in metrics loop: {e}")
                await asyncio.sleep(5)  # Prevent tight error loop
    
    async def _cleanup_loop(self):
        """Background cleanup loop"""
        while self.state.running:
            try:
                # Cleanup old messages
                if self.config.storage.max_history > 0:
                    max_age = time.time() - (30 * 24 * 60 * 60)  # 30 days
                    deleted = await self.db_layer.cleanup_old_messages(
                        max_age=max_age
                    )
                    if deleted > 0:
                        logger.debug(f"Cleaned up {deleted} old messages")
                
                # Cleanup old sessions
                await self.security_layer.cleanup_old_sessions()
                
                # Optimize database
                if time.time() % 3600 == 0:  # Every hour
                    await self.db_layer.optimize_database()
                
                # Sleep for cleanup interval
                await asyncio.sleep(300)  # 5 minutes
                
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(60)  # Prevent tight error loop
    
    async def handle_network_event(self, event: str, data: Dict[str, Any]):
        """Handle network layer events"""
        if event == 'connected':
            self.state.connected = True
            self.state.peer_count = data.get('peer_count', 0)
            self.metrics['connections_established'] += 1
            self._trigger_event('connected', data)
            
        elif event == 'disconnected':
            self.state.connected = False
            self.state.peer_count = 0
            self._trigger_event('disconnected', data)
            
        elif event == 'peer_joined':
            self.state.peer_count = data.get('peer_count', self.state.peer_count + 1)
            self._trigger_event('peer_joined', data)
            
        elif event == 'peer_left':
            self.state.peer_count = max(0, self.state.peer_count - 1)
            self._trigger_event('peer_left', data)
            
        elif event == 'message_received':
            self.metrics['messages_received'] += 1
            
            # Store message in database
            message = data.get('message')
            if message:
                await self.db_layer.store_message(message)
                
                # Display message
                await self.ui_layer.display_message(message)
                
                self._trigger_event('message_received', {'message': message})
            
        elif event == 'error':
            self.metrics['errors'] += 1
            self.state.last_error = data.get('error', 'Unknown error')
            self._trigger_event('error', data)
    
    async def handle_ui_event(self, event: str, data: Dict[str, Any]):
        """Handle UI layer events"""
        if event == 'send_message':
            content = data.get('content', '')
            channel = data.get('channel')
            recipient = data.get('recipient')
            
            await self.send_message(content, channel, recipient)
            
        elif event == 'join_channel':
            channel = data.get('channel', '')
            password = data.get('password')
            
            await self.join_channel(channel, password)
            
        elif event == 'leave_channel':
            channel = data.get('channel', '')
            
            await self.leave_channel(channel)
            
        elif event == 'start_dm':
            peer_id = data.get('peer_id', '')
            peer_nickname = data.get('peer_nickname', '')
            
            await self.start_private_dm(peer_id, peer_nickname)
            
        elif event == 'get_status':
            status = await self.get_status()
            await self.ui_layer.display_status(status)
            
        elif event == 'exit':
            await self.stop()
    
    def get_peer_info(self, peer_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a peer"""
        return self.network_layer.get_peer_info(peer_id)
    
    def get_channel_info(self, channel: str) -> Optional[Dict[str, Any]]:
        """Get information about a channel"""
        return self.network_layer.get_channel_info(channel)
    
    def get_message_history(self, filters: Optional[MessageFilters] = None) -> List[Message]:
        """Get message history"""
        if not filters:
            filters = MessageFilters(limit=100)
            
        return asyncio.run(self.db_layer.get_messages(filters))
    
    async def reload_config(self):
        """Reload configuration"""
        try:
            await self.config_manager._load_config()
            logger.info("Configuration reloaded")
            return True
        except Exception as e:
            logger.error(f"Failed to reload configuration: {e}")
            return False
    
    async def save_config(self):
        """Save configuration"""
        try:
            success = await self.config_manager.save()
            if success:
                logger.info("Configuration saved")
            return success
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            return False