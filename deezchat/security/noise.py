"""
Noise Protocol layer for BitChat compatibility
"""

import logging
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass

from .encryption import EncryptionService, NoiseError

logger = logging.getLogger(__name__)

@dataclass
class PeerIdentity:
    """Peer identity information"""
    peer_id: str
    public_key: bytes
    fingerprint: str
    nickname: Optional[str] = None

class NoiseSecurityLayer:
    """
    BitChat-compatible Noise Protocol wrapper
    Uses the existing EncryptionService for compatibility
    """
    
    def __init__(self, config):
        self.config = config
        self.encryption_service = EncryptionService()
        self.peers: Dict[str, PeerIdentity] = {}
        
    @property
    def public_key(self) -> bytes:
        """Get public key bytes"""
        return self.encryption_service.get_public_key_bytes()
    
    @property
    def fingerprint(self) -> str:
        """Get key fingerprint for verification"""
        return self.encryption_service.get_identity_fingerprint()
    
    def initiate_handshake(self, peer_id: str, peer_public_key: bytes) -> Optional[bytes]:
        """Initiate handshake with peer"""
        try:
            handshake = self.encryption_service.initiate_handshake(peer_id, peer_public_key)
            return handshake
        except Exception as e:
            logger.error(f"Handshake initiation failed: {e}")
            return None
    
    def respond_to_handshake(self, peer_id: str, message: bytes) -> Optional[bytes]:
        """Respond to handshake initiation"""
        try:
            response = self.encryption_service.respond_to_handshake(peer_id, message)
            return response
        except Exception as e:
            logger.error(f"Handshake response failed: {e}")
            return None
    
    def complete_handshake(self, peer_id: str, message: bytes) -> bool:
        """Complete handshake and establish secure channel"""
        try:
            success = self.encryption_service.complete_handshake(peer_id, message)
            return success
        except Exception as e:
            logger.error(f"Handshake completion failed: {e}")
            return False
    
    def encrypt_message(self, peer_id: str, plaintext: bytes) -> Optional[bytes]:
        """Encrypt message for peer"""
        try:
            ciphertext = self.encryption_service.encrypt_message(peer_id, plaintext)
            return ciphertext
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            return None
    
    def decrypt_message(self, peer_id: str, ciphertext: bytes) -> Optional[bytes]:
        """Decrypt message from peer"""
        try:
            plaintext = self.encryption_service.decrypt_message(peer_id, ciphertext)
            return plaintext
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            return None
    
    def add_peer(self, peer_id: str, public_key: bytes, nickname: Optional[str] = None):
        """Add trusted peer"""
        try:
            self.encryption_service.add_peer(peer_id, public_key)
            
            # Calculate fingerprint for display
            import hashlib
            import base64
            digest = hashlib.sha256(public_key)
            fingerprint = base64.b32encode(digest.digest()).decode('ascii')[:8]
            
            self.peers[peer_id] = PeerIdentity(
                peer_id=peer_id,
                public_key=public_key,
                fingerprint=fingerprint,
                nickname=nickname
            )
            
            logger.info(f"Added peer {peer_id} with fingerprint {fingerprint}")
            
        except Exception as e:
            logger.error(f"Failed to add peer: {e}")
    
    def verify_peer(self, peer_id: str, public_key: bytes) -> bool:
        """Verify peer identity"""
        peer = self.peers.get(peer_id)
        if not peer:
            return False
            
        return peer.public_key == public_key