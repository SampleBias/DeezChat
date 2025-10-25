"""
DeezChat - BitChat Python Client

A decentralized, encrypted peer-to-peer chat client over Bluetooth Low Energy.
Compatible with BitChat protocol specification.
"""

__version__ = "1.2.0"
__author__ = "DeezChat Team"
__email__ = "contact@deezchat.org"
__license__ = "MIT"

# Import main components
from .core.client import DeezChatClient
from .storage.config import Config, ConfigManager
from .ui.terminal import TerminalInterface

# Export main classes
__all__ = [
    'DeezChatClient',
    'Config',
    'ConfigManager', 
    'TerminalInterface',
    '__version__',
    '__author__',
    '__email__',
    '__license__'
]