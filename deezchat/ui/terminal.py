"""
Terminal UI for DeezChat
"""

import asyncio
import logging
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
import aioconsole
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class ChatMessage:
    """Chat message representation"""
    sender: str
    content: str
    timestamp: datetime
    is_private: bool = False
    channel: Optional[str] = None

class TerminalInterface:
    """Minimal terminal interface for DeezChat"""
    
    def __init__(self, config):
        self.config = config
        self.running = False
        self.current_channel = "public"
        self.input_task = None
        
    async def start(self):
        """Start the terminal interface"""
        self.running = True
        self.input_task = asyncio.create_task(self._input_loop())
        await self._display_welcome()
        
    async def stop(self):
        """Stop the terminal interface"""
        self.running = False
        if self.input_task:
            self.input_task.cancel()
            
    async def _display_welcome(self):
        """Display welcome message"""
        print("\\n" + "="*50)
        print("Welcome to DeezChat - BitChat Python Client")
        print("="*50)
        print("Commands: /help, /join <channel>, /dm <peer>, /quit")
        print(f"Current channel: {self.current_channel}")
        print("="*50 + "\\n")
        
    async def _input_loop(self):
        """Handle user input"""
        while self.running:
            try:
                line = await aioconsole.ainput(f"[{self.current_channel}]> ")
                if line.strip():
                    await self._handle_command(line)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Input error: {e}")
                
    async def _handle_command(self, line: str):
        """Handle user command"""
        parts = line.strip().split()
        if not parts:
            return
            
        command = parts[0].lower()
        
        if command == '/help':
            await self._show_help()
        elif command == '/join' and len(parts) > 1:
            self.current_channel = parts[1]
            print(f"Joined channel: {self.current_channel}")
        elif command == '/dm' and len(parts) > 1:
            peer = parts[1]
            message = ' '.join(parts[2:]) if len(parts) > 2 else ""
            if message:
                await self._send_private_message(peer, message)
            else:
                print(f"Starting DM with {peer}")
                self.current_channel = f"@{peer}"
        elif command == '/quit':
            print("Goodbye!")
            self.running = False
        elif command.startswith('/'):
            print("Unknown command. Type /help for available commands.")
        else:
            await self._send_message(line)
            
    async def _show_help(self):
        """Show help information"""
        print("\\nAvailable commands:")
        print("  /help              - Show this help")
        print("  /join <channel>    - Join channel")
        print("  /dm <peer> <msg>   - Send private message")
        print("  /quit              - Exit application")
        print("\\n")
        
    async def _send_message(self, content: str):
        """Send message to current channel"""
        message = ChatMessage(
            sender="you",
            content=content,
            timestamp=datetime.now(),
            channel=self.current_channel
        )
        # This would be handled by the client layer
        print(f"[{self.current_channel}] you: {content}")
        
    async def _send_private_message(self, peer: str, content: str):
        """Send private message"""
        message = ChatMessage(
            sender="you",
            content=content,
            timestamp=datetime.now(),
            is_private=True
        )
        print(f"[DM to {peer}] you: {content}")
        
    async def display_message(self, message: ChatMessage):
        """Display incoming message"""
        if message.is_private:
            print(f"[DM from {message.sender}] {message.content}")
        else:
            channel = message.channel or "public"
            print(f"[{channel}] {message.sender}: {message.content}")
            
    async def display_status(self, status: str):
        """Display status message"""
        print(f"* {status}")
        
    async def display_error(self, error: str):
        """Display error message"""
        print(f"[ERROR] {error}")