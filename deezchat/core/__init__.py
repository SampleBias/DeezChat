"""
Core module for DeezChat

Contains the main client, message routing, and session management.
"""

from .client import DeezChatClient
from .message import MessageRouter, MessageHandler
from .session import SessionManager, PeerSession

__all__ = [
    'DeezChatClient',
    'MessageRouter',
    'MessageHandler',
    'SessionManager',
    'PeerSession'
]