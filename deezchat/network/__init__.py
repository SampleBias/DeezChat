"""
Network layer for DeezChat

Handles BLE communication, peer discovery, and message transport.
"""

from .ble import BLENetworkLayer
from .discovery import PeerDiscovery
from .transport import MessageTransport

__all__ = [
    'BLENetworkLayer',
    'PeerDiscovery',
    'MessageTransport'
]