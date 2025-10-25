"""
Database layer for DeezChat

Handles message persistence, search, and data management.
"""

import os
import sqlite3
import json
import time
import threading
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
import asyncio
import aiosqlite
import hashlib
import uuid

from .config import Config, ConfigManager

logger = logging.getLogger(__name__)

@dataclass
class Message:
    """Message data model"""
    id: str
    sender_id: str
    sender_nickname: str
    content: str
    recipient_id: Optional[str] = None
    recipient_nickname: Optional[str] = None
    channel: Optional[str] = None
    is_private: bool = False
    is_encrypted: bool = False
    encrypted_content: Optional[bytes] = None
    timestamp: float = field(default_factory=time.time)
    hop_count: int = 0
    mentions: List[str] = field(default_factory=list)
    file_attachments: List['FileAttachment'] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class FileAttachment:
    """File attachment data model"""
    id: str
    filename: str
    file_path: str
    file_size: int
    mime_type: str
    checksum: str
    transfer_id: Optional[str] = None
    download_count: int = 0

@dataclass
class MessageFilters:
    """Message query filters"""
    sender_id: Optional[str] = None
    recipient_id: Optional[str] = None
    channel: Optional[str] = None
    is_private: Optional[bool] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    content_search: Optional[str] = None
    limit: int = 100
    offset: int = 0
    include_files: bool = False

@dataclass
class ConversationStats:
    """Conversation statistics"""
    message_count: int
    last_message_time: float
    participants: List[str]
    file_count: int

class DatabaseError(Exception):
    """Database related errors"""
    pass

class DatabaseLayer:
    """Database abstraction layer for DeezChat"""
    
    def __init__(self, config: Config):
        self.config = config
        self.db_path = self._get_db_path()
        self.connection_pool = aiosqlite.ConnectionPool(max_size=5)
        self._db_lock = asyncio.Lock()
        self._init_db()
        
    def _get_db_path(self) -> str:
        """Get database file path"""
        db_dir = os.path.expanduser(self.config.storage.data_dir)
        os.makedirs(db_dir, exist_ok=True)
        return os.path.join(db_dir, "deezchat.db")
    
    def _init_db(self):
        """Initialize database with required tables"""
        try:
            # Create tables if they don't exist
            asyncio.create_task(self._create_tables())
            logger.info(f"Database initialized at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise DatabaseError(f"Database initialization failed: {e}")
    
    async def _create_tables(self):
        """Create database tables"""
        async with aiosqlite.connect(self.db_path) as db:
            # Messages table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    sender_id TEXT NOT NULL,
                    sender_nickname TEXT NOT NULL,
                    recipient_id TEXT,
                    recipient_nickname TEXT,
                    content TEXT NOT NULL,
                    channel TEXT,
                    is_private INTEGER NOT NULL DEFAULT 0,
                    is_encrypted INTEGER NOT NULL DEFAULT 0,
                    encrypted_content BLOB,
                    timestamp REAL NOT NULL,
                    hop_count INTEGER NOT NULL DEFAULT 0,
                    mentions TEXT,
                    file_attachments TEXT,
                    metadata TEXT
                )
            """)
            
            # File attachments table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS file_attachments (
                    id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    mime_type TEXT NOT NULL,
                    checksum TEXT NOT NULL,
                    transfer_id TEXT,
                    download_count INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL
                )
            """)
            
            # Create indexes for performance
            await db.execute("CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages(sender_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_messages_recipient ON messages(recipient_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_messages_channel ON messages(channel)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_messages_private ON messages(is_private)")
            
            # Create settings table for metadata
            await db.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            
            logger.debug("Database tables created/verified")
    
    async def store_message(self, message: Message) -> bool:
        """Store message in database"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Serialize complex fields
                mentions_json = json.dumps(message.mentions)
                attachments_json = json.dumps([
                    {
                        'id': att.id,
                        'filename': att.filename,
                        'file_path': att.file_path,
                        'file_size': att.file_size,
                        'mime_type': att.mime_type,
                        'checksum': att.checksum,
                        'transfer_id': att.transfer_id,
                        'download_count': att.download_count
                    }
                    for att in message.file_attachments
                ])
                metadata_json = json.dumps(message.metadata)
                
                await db.execute("""
                    INSERT INTO messages (
                        id, sender_id, sender_nickname, recipient_id, recipient_nickname,
                        content, channel, is_private, is_encrypted, encrypted_content,
                        timestamp, hop_count, mentions, file_attachments, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    message.id,
                    message.sender_id,
                    message.sender_nickname,
                    message.recipient_id,
                    message.recipient_nickname,
                    message.content,
                    message.channel,
                    1 if message.is_private else 0,
                    1 if message.is_encrypted else 0,
                    message.encrypted_content,
                    message.timestamp,
                    message.hop_count,
                    mentions_json,
                    attachments_json,
                    metadata_json
                ))
                
            logger.debug(f"Stored message {message.id} from {message.sender_nickname}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store message {message.id}: {e}")
            return False
    
    async def get_messages(self, filters: MessageFilters) -> List[Message]:
        """Get messages with filters"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Build query based on filters
                query_parts = ["SELECT * FROM messages WHERE 1=1"]
                params = []
                
                # Add filter conditions
                if filters.sender_id:
                    query_parts.append("sender_id = ?")
                    params.append(filters.sender_id)
                
                if filters.recipient_id:
                    query_parts.append("recipient_id = ?")
                    params.append(filters.recipient_id)
                
                if filters.channel:
                    query_parts.append("channel = ?")
                    params.append(filters.channel)
                
                if filters.is_private is not None:
                    query_parts.append("is_private = ?")
                    params.append(1 if filters.is_private else 0)
                
                if filters.start_time:
                    query_parts.append("timestamp >= ?")
                    params.append(filters.start_time)
                
                if filters.end_time:
                    query_parts.append("timestamp <= ?")
                    params.append(filters.end_time)
                
                if filters.content_search:
                    query_parts.append("content LIKE ?")
                    params.append(f"%{filters.content_search}%")
                
                # Combine all conditions
                query = " AND ".join(query_parts)
                
                # Add ordering and pagination
                query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
                params.extend([filters.limit, filters.offset])
                
                # Execute query
                cursor = await db.execute(query, params)
                rows = await cursor.fetchall()
                
                # Convert rows to Message objects
                messages = []
                for row in rows:
                    # Deserialize complex fields
                    mentions = json.loads(row[10]) if row[10] else []
                    attachments = []
                    if row[11]:
                        for att_data in json.loads(row[11]):
                            attachments.append(FileAttachment(
                                id=att_data['id'],
                                filename=att_data['filename'],
                                file_path=att_data['file_path'],
                                file_size=att_data['file_size'],
                                mime_type=att_data['mime_type'],
                                checksum=att_data['checksum'],
                                transfer_id=att_data.get('transfer_id'),
                                download_count=att_data.get('download_count', 0)
                            ))
                    
                    metadata = json.loads(row[12]) if row[12] else {}
                    
                    messages.append(Message(
                        id=row[0],
                        sender_id=row[1],
                        sender_nickname=row[2],
                        recipient_id=row[3],
                        recipient_nickname=row[4],
                        content=row[5],
                        channel=row[6],
                        is_private=bool(row[7]),
                        is_encrypted=bool(row[8]),
                        encrypted_content=row[9],
                        timestamp=row[10],
                        hop_count=row[11],
                        mentions=mentions,
                        file_attachments=attachments,
                        metadata=metadata
                    ))
                
                logger.debug(f"Retrieved {len(messages)} messages with filters")
                return messages
                
        except Exception as e:
            logger.error(f"Failed to get messages: {e}")
            return []
    
    async def search_messages(self, query: str, limit: int = 50) -> List[Message]:
        """Search messages by content"""
        try:
            search_filters = MessageFilters(
                content_search=query,
                limit=limit
            )
            return await self.get_messages(search_filters)
            
        except Exception as e:
            logger.error(f"Failed to search messages: {e}")
            return []
    
    async def get_message_by_id(self, message_id: str) -> Optional[Message]:
        """Get specific message by ID"""
        try:
            filters = MessageFilters(limit=1)
            filters.content_search = f"id:{message_id}"
            
            messages = await self.get_messages(filters)
            return messages[0] if messages else None
            
        except Exception as e:
            logger.error(f"Failed to get message {message_id}: {e}")
            return None
    
    async def update_message(self, message_id: str, updates: Dict[str, Any]) -> bool:
        """Update message fields"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Build update query
                set_parts = []
                params = []
                
                for field, value in updates.items():
                    if field in ['content', 'channel', 'recipient_id', 'hop_count']:
                        set_parts.append(f"{field} = ?")
                        params.append(value)
                    elif field in ['is_private', 'is_encrypted']:
                        set_parts.append(f"{field} = ?")
                        params.append(1 if value else 0)
                
                if not set_parts:
                    return False
                
                query = f"UPDATE messages SET {', '.join(set_parts)} WHERE id = ?"
                params.append(message_id)
                
                await db.execute(query, params)
                
            logger.debug(f"Updated message {message_id} with {list(updates.keys())}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update message {message_id}: {e}")
            return False
    
    async def delete_message(self, message_id: str) -> bool:
        """Delete message from database"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("DELETE FROM messages WHERE id = ?", (message_id,))
                
            logger.debug(f"Deleted message {message_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete message {message_id}: {e}")
            return False
    
    async def store_file_attachment(self, attachment: FileAttachment) -> bool:
        """Store file attachment in database"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO file_attachments (
                        id, filename, file_path, file_size, mime_type,
                        checksum, transfer_id, download_count, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    attachment.id,
                    attachment.filename,
                    attachment.file_path,
                    attachment.file_size,
                    attachment.mime_type,
                    attachment.checksum,
                    attachment.transfer_id,
                    attachment.download_count,
                    time.time()
                ))
                
            logger.debug(f"Stored file attachment {attachment.id} ({attachment.filename})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store file attachment {attachment.id}: {e}")
            return False
    
    async def get_file_attachment(self, attachment_id: str) -> Optional[FileAttachment]:
        """Get file attachment by ID"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "SELECT * FROM file_attachments WHERE id = ?", 
                    (attachment_id,)
                )
                row = await cursor.fetchone()
                
                if row:
                    return FileAttachment(
                        id=row[0],
                        filename=row[1],
                        file_path=row[2],
                        file_size=row[3],
                        mime_type=row[4],
                        checksum=row[5],
                        transfer_id=row[6],
                        download_count=row[7]
                    )
                
                return None
            
        except Exception as e:
            logger.error(f"Failed to get file attachment {attachment_id}: {e}")
            return None
    
    async def increment_download_count(self, attachment_id: str) -> bool:
        """Increment download count for file attachment"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE file_attachments SET download_count = download_count + 1 WHERE id = ?", 
                    (attachment_id,)
                )
                
            logger.debug(f"Incremented download count for attachment {attachment_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to increment download count for {attachment_id}: {e}")
            return False
    
    async def get_conversation_stats(self, peer_id: Optional[str] = None, 
                                channel: Optional[str] = None) -> Optional[ConversationStats]:
        """Get statistics for a conversation"""
        try:
            filters = MessageFilters(limit=1)
            
            if peer_id:
                # Get conversation with specific peer (sent or received)
                filters.content_search = f"sender_id:{peer_id} OR recipient_id:{peer_id}"
            elif channel:
                # Get channel statistics
                filters.channel = channel
            
            messages = await self.get_messages(filters)
            
            if not messages:
                return None
                
            # Calculate statistics
            message_count = len(messages)
            last_message_time = messages[0].timestamp if messages else 0
            
            # Get unique participants
            participants = set()
            for msg in messages:
                participants.add(msg.sender_nickname)
                if msg.recipient_nickname:
                    participants.add(msg.recipient_nickname)
            
            # Count files
            file_count = sum(len(msg.file_attachments) for msg in messages)
            
            return ConversationStats(
                message_count=message_count,
                last_message_time=last_message_time,
                participants=list(participants),
                file_count=file_count
            )
            
        except Exception as e:
            logger.error(f"Failed to get conversation stats: {e}")
            return None
    
    async def cleanup_old_messages(self, max_age: timedelta = timedelta(days=30)) -> int:
        """Clean up old messages based on age"""
        try:
            cutoff_time = time.time() - max_age.total_seconds()
            
            async with aiosqlite.connect(self.db_path) as db:
                result = await db.execute(
                    "DELETE FROM messages WHERE timestamp < ?", 
                    (cutoff_time,)
                )
                
                deleted_count = result.rowcount if hasattr(result, 'rowcount') else 0
                logger.info(f"Cleaned up {deleted_count} old messages")
                return deleted_count
                
        except Exception as e:
            logger.error(f"Failed to cleanup old messages: {e}")
            return 0
    
    async def get_setting(self, key: str, default: Any = None) -> Any:
        """Get setting value"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "SELECT value FROM settings WHERE key = ?", 
                    (key,)
                )
                row = await cursor.fetchone()
                
                if row:
                    # Try to parse as JSON
                    try:
                        return json.loads(row[0])
                    except (json.JSONDecodeError, TypeError):
                        return row[0]
                
                return default
            
        except Exception as e:
            logger.error(f"Failed to get setting {key}: {e}")
            return default
    
    async def set_setting(self, key: str, value: Any) -> bool:
        """Set setting value"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Store as JSON string for complex values
                value_json = json.dumps(value) if not isinstance(value, str) else value
                
                await db.execute("""
                    INSERT OR REPLACE INTO settings (key, value, updated_at) 
                    VALUES (?, ?, ?)
                """, (key, value_json, time.time()))
                
            logger.debug(f"Set setting {key} = {value}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set setting {key}: {e}")
            return False
    
    async def get_message_history(self, peer_id: Optional[str] = None, 
                                limit: int = 100) -> List[Message]:
        """Get message history for a peer or all messages"""
        filters = MessageFilters(limit=limit)
        
        if peer_id:
            filters.content_search = f"sender_id:{peer_id} OR recipient_id:{peer_id}"
        
        return await self.get_messages(filters)
    
    async def backup_database(self, backup_path: Optional[str] = None) -> bool:
        """Create backup of database"""
        try:
            if not backup_path:
                # Generate backup filename with timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_dir = os.path.dirname(self.db_path)
                backup_path = os.path.join(backup_dir, f"backup_{timestamp}.db")
            
            # Copy database file
            import shutil
            shutil.copy2(self.db_path, backup_path)
            
            logger.info(f"Created database backup at {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to backup database: {e}")
            return False
    
    async def restore_database(self, backup_path: str) -> bool:
        """Restore database from backup"""
        try:
            # Verify backup exists
            if not os.path.exists(backup_path):
                logger.error(f"Backup file not found: {backup_path}")
                return False
            
            # Close current connections
            await self.connection_pool.close_all()
            
            # Replace current database with backup
            import shutil
            shutil.copy2(backup_path, self.db_path)
            
            logger.info(f"Restored database from {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to restore database: {e}")
            return False
    
    async def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        try:
            stats = {}
            
            async with aiosqlite.connect(self.db_path) as db:
                # Get message count
                cursor = await db.execute("SELECT COUNT(*) FROM messages")
                result = await cursor.fetchone()
                stats['message_count'] = result[0] if result else 0
                
                # Get file count
                cursor = await db.execute("SELECT COUNT(*) FROM file_attachments")
                result = await cursor.fetchone()
                stats['file_count'] = result[0] if result else 0
                
                # Get database size
                db_size = os.path.getsize(self.db_path)
                stats['database_size_bytes'] = db_size
                stats['database_size_mb'] = round(db_size / (1024 * 1024), 2)
                
                # Get oldest and newest message timestamps
                cursor = await db.execute("SELECT MIN(timestamp), MAX(timestamp) FROM messages")
                result = await cursor.fetchone()
                if result:
                    stats['oldest_message'] = result[0]
                    stats['newest_message'] = result[1]
                
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
            return {}
    
    async def optimize_database(self) -> bool:
        """Optimize database (VACUUM, ANALYZE)"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("VACUUM")
                await db.execute("ANALYZE")
                
            logger.info("Database optimized")
            return True
            
        except Exception as e:
            logger.error(f"Failed to optimize database: {e}")
            return False
    
    async def close(self):
        """Close database connections"""
        try:
            await self.connection_pool.close_all()
            logger.debug("Database connections closed")
        except Exception as e:
            logger.error(f"Failed to close database connections: {e}")

# Utility functions
def generate_message_id() -> str:
    """Generate unique message ID"""
    return str(uuid.uuid4())

def calculate_file_checksum(file_path: str) -> str:
    """Calculate SHA-256 checksum for file"""
    hash_sha256 = hashlib.sha256()
    
    with open(file_path, 'rb') as f:
        # Read file in chunks to handle large files
        for chunk in iter(lambda: f.read(4096), b''):
            hash_sha256.update(chunk)
    
    return hash_sha256.hexdigest()

def validate_message(message: Message) -> List[str]:
    """Validate message and return list of errors"""
    errors = []
    
    if not message.id:
        errors.append("Message ID is required")
    
    if not message.sender_id:
        errors.append("Sender ID is required")
    
    if not message.sender_nickname:
        errors.append("Sender nickname is required")
    
    if not message.content:
        errors.append("Message content is required")
    
    if len(message.content) > 10000:
        errors.append("Message content too long (max 10000 characters)")
    
    return errors