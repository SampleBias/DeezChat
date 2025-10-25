"""
Session management for DeezChat
"""

import logging
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
import time
import asyncio

logger = logging.getLogger(__name__)

@dataclass
class PeerSession:
    """Peer session information"""
    peer_id: str
    address: str
    connected: bool = False
    last_seen: float = field(default_factory=time.time)
    messages_sent: int = 0
    messages_received: int = 0
    
    def update_last_seen(self):
        """Update last seen timestamp"""
        self.last_seen = time.time()

class SessionManager:
    """Manages peer sessions"""
    
    def __init__(self, config):
        self.config = config
        self.sessions: Dict[str, PeerSession] = {}
        self.active_connections: Set[str] = set()
        
    def add_session(self, peer_id: str, address: str) -> PeerSession:
        """Add new peer session"""
        session = PeerSession(peer_id=peer_id, address=address)
        self.sessions[peer_id] = session
        logger.info(f"Added session for {peer_id}")
        return session
        
    def get_session(self, peer_id: str) -> Optional[PeerSession]:
        """Get peer session"""
        return self.sessions.get(peer_id)
        
    def remove_session(self, peer_id: str) -> bool:
        """Remove peer session"""
        if peer_id in self.sessions:
            del self.sessions[peer_id]
            self.active_connections.discard(peer_id)
            logger.info(f"Removed session for {peer_id}")
            return True
        return False
        
    def set_connected(self, peer_id: str, connected: bool):
        """Set connection status"""
        session = self.get_session(peer_id)
        if session:
            session.connected = connected
            session.update_last_seen()
            if connected:
                self.active_connections.add(peer_id)
            else:
                self.active_connections.discard(peer_id)
                
    def get_active_peers(self) -> List[str]:
        """Get list of active peers"""
        return list(self.active_connections)
        
    def cleanup_inactive(self, timeout: float = 300):
        """Clean up inactive sessions"""
        current_time = time.time()
        inactive = [
            peer_id for peer_id, session in self.sessions.items()
            if current_time - session.last_seen > timeout
        ]
        for peer_id in inactive:
            self.remove_session(peer_id)
        return len(inactive)