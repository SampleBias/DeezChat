"""
Main entry point for DeezChat

This module provides the command-line interface for the DeezChat client.
"""

import sys
import os
import argparse
import asyncio
import signal
import logging
from pathlib import Path

from .client import DeezChatClient
from .storage.config import ConfigManager

logger = logging.getLogger(__name__)

def setup_signal_handlers(client: DeezChatClient):
    """Setup signal handlers for graceful shutdown"""
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        asyncio.create_task(client.stop())
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # On Windows, handle CTRL+C
    if os.name == 'nt':
        signal.signal(signal.SIGBREAK, signal_handler)

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="DeezChat - Decentralized Encrypted Chat Client",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Configuration options
    parser.add_argument(
        '-c', '--config',
        type=str,
        help='Path to configuration file'
    )
    
    parser.add_argument(
        '-d', '--data-dir',
        type=str,
        help='Path to data directory'
    )
    
    # Debug options
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    
    parser.add_argument(
        '-vv', '--debug',
        action='store_true',
        help='Enable debug output'
    )
    
    # Version
    parser.add_argument(
        '--version',
        action='version',
        version='DeezChat 1.2.0'
    )
    
    return parser.parse_args()

async def main():
    """Main entry point"""
    # Parse arguments
    args = parse_arguments()
    
    # Initialize configuration
    config_path = None
    data_dir = None
    
    if args.config:
        config_path = os.path.abspath(args.config)
    
    if args.data_dir:
        data_dir = os.path.abspath(args.data_dir)
    
    # Create client
    try:
        client = DeezChatClient(config_path=config_path, data_dir=data_dir)
        
        # Override debug settings if specified
        if args.debug:
            client.config_manager.set('logging.level', 'DEBUG', notify=False)
            client.config_manager.set('logging.console_output', True, notify=False)
        elif args.verbose:
            client.config_manager.set('logging.level', 'INFO', notify=False)
            client.config_manager.set('logging.console_output', True, notify=False)
        
        # Setup signal handlers
        setup_signal_handlers(client)
        
        # Start client
        success = await client.start()
        
        if not success:
            logger.error("Failed to start DeezChat client")
            return 1
            
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
        if 'client' in locals():
            await client.stop()
        return 0
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1

def run():
    """Synchronous entry point for setuptools"""
    try:
        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Run the async main function
        return_code = loop.run_until_complete(main())
        
        # Clean up
        loop.close()
        return return_code
        
    except Exception as e:
        logger.error(f"Failed to run DeezChat: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(run())