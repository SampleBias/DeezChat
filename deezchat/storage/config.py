"""
Configuration management for DeezChat

Handles loading, validation, and watching of configuration settings.
"""

import os
import yaml
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
import logging
import asyncio

logger = logging.getLogger(__name__)

class ConfigFormat(Enum):
    """Supported configuration file formats"""
    YAML = "yaml"
    JSON = "json"

@dataclass
class NetworkConfig:
    """Network configuration settings"""
    scan_interval: int = 5  # Seconds between scans
    max_peers: int = 50  # Maximum concurrent peers
    ttl: int = 7  # Message time-to-live
    connection_timeout: int = 10  # Connection timeout in seconds
    retry_attempts: int = 3  # Connection retry attempts
    fragment_size: int = 500  # Maximum fragment size
    max_message_size: int = 10000  # Maximum message size

@dataclass
class SecurityConfig:
    """Security configuration settings"""
    encryption_algorithm: str = "ChaCha20-Poly1305"
    key_rotation_interval: int = 3600  # Seconds
    handshake_timeout: int = 5  # Handshake timeout in seconds
    session_timeout: int = 7200  # Session timeout in seconds
    identity_key_path: Optional[str] = None  # Path to identity key file
    require_identity_verification: bool = True  # Require identity verification

@dataclass
class UIConfig:
    """User interface configuration settings"""
    theme: str = "default"  # Color theme
    timestamp_format: str = "%H:%M"  # Timestamp format
    show_fingerprints: bool = False  # Show peer fingerprints
    max_history_lines: int = 1000  # Maximum history lines to show
    auto_scroll: bool = True  # Auto-scroll to new messages
    color_scheme: str = "default"  # Color scheme
    show_connection_status: bool = True  # Show connection status
    enable_tab_completion: bool = True  # Enable tab completion

@dataclass
class StorageConfig:
    """Storage configuration settings"""
    data_dir: str = "~/.local/share/deezchat"  # Data directory
    max_history: int = 10000  # Messages to keep
    compress_history: bool = True  # Compress message history
    database_type: str = "sqlite"  # Database type
    backup_enabled: bool = True  # Enable automatic backups
    backup_interval: int = 3600  # Backup interval in seconds
    max_backup_size: int = 100  # Maximum number of backups

@dataclass
class LoggingConfig:
    """Logging configuration settings"""
    level: str = "INFO"  # Log level
    file: Optional[str] = None  # Log file path
    max_size: str = "10MB"  # Maximum log file size
    backup_count: int = 5  # Number of backup log files
    console_output: bool = True  # Output to console
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"  # Log format

@dataclass
class PerformanceConfig:
    """Performance configuration settings"""
    memory_pool_size: int = 1024 * 1024  # Memory pool size in bytes
    max_concurrent_operations: int = 100  # Maximum concurrent operations
    enable_metrics: bool = True  # Enable performance metrics
    metrics_interval: int = 60  # Metrics collection interval in seconds
    enable_profiling: bool = False  # Enable performance profiling

@dataclass
class FileTransferConfig:
    """File transfer configuration settings"""
    max_file_size: int = 100 * 1024 * 1024  # Maximum file size (100MB)
    max_concurrent_transfers: int = 5  # Maximum concurrent transfers
    chunk_size: int = 64 * 1024  # File transfer chunk size (64KB)
    temp_dir: Optional[str] = None  # Temporary directory for transfers
    auto_accept_transfers: bool = False  # Automatically accept file transfers
    verify_checksums: bool = True  # Verify file checksums

@dataclass
class Config:
    """Main configuration class"""
    network: NetworkConfig = field(default_factory=NetworkConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    file_transfer: FileTransferConfig = field(default_factory=FileTransferConfig)

class ConfigError(Exception):
    """Configuration related errors"""
    pass

class ConfigChangeCallback:
    """Callback for configuration changes"""
    def __init__(self, key: str, callback: Callable[[Any, Any], None]):
        self.key = key
        self.callback = callback
        
    def __call__(self, old_value: Any, new_value: Any):
        """Call the callback with old and new values"""
        try:
            self.callback(old_value, new_value)
        except Exception as e:
            logger.error(f"Config callback error for {self.key}: {e}")

class ConfigManager:
    """Centralized configuration management"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or self._get_default_config_path()
        self.config = Config()
        self.watchers: Dict[str, List[ConfigChangeCallback]] = {}
        self._config_lock = asyncio.Lock()
        self._load_config()
        
    def _get_default_config_path(self) -> str:
        """Get default configuration file path"""
        # Check multiple locations in order of preference
        paths = [
            os.path.expanduser("~/.config/deezchat/config.yaml"),
            os.path.expanduser("~/.deezchat/config.yaml"),
            "./deezchat.yaml",
            "./config.yaml"
        ]
        
        for path in paths:
            if os.path.exists(path):
                return path
                
        # Return default path if none exists
        return os.path.expanduser("~/.config/deezchat/config.yaml")
    
    def _load_config(self):
        """Load configuration from file"""
        if not os.path.exists(self.config_path):
            logger.info(f"Config file not found at {self.config_path}, using defaults")
            self._apply_env_overrides()
            return
            
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                if self.config_path.endswith('.yaml') or self.config_path.endswith('.yml'):
                    data = yaml.safe_load(f)
                elif self.config_path.endswith('.json'):
                    data = json.load(f)
                else:
                    raise ConfigError(f"Unsupported config format: {self.config_path}")
                    
            self._update_config_from_dict(data)
            self._apply_env_overrides()
            logger.info(f"Loaded configuration from {self.config_path}")
            
        except Exception as e:
            logger.error(f"Failed to load config from {self.config_path}: {e}")
            logger.info("Using default configuration")
            self.config = Config()
            self._apply_env_overrides()
    
    def _update_config_from_dict(self, data: Dict[str, Any]):
        """Update configuration from dictionary"""
        if not data:
            return
            
        # Update network config
        if 'network' in data:
            network_data = data['network']
            for key, value in network_data.items():
                if hasattr(self.config.network, key):
                    setattr(self.config.network, key, value)
                    
        # Update security config
        if 'security' in data:
            security_data = data['security']
            for key, value in security_data.items():
                if hasattr(self.config.security, key):
                    setattr(self.config.security, key, value)
                    
        # Update UI config
        if 'ui' in data:
            ui_data = data['ui']
            for key, value in ui_data.items():
                if hasattr(self.config.ui, key):
                    setattr(self.config.ui, key, value)
                    
        # Update storage config
        if 'storage' in data:
            storage_data = data['storage']
            for key, value in storage_data.items():
                if hasattr(self.config.storage, key):
                    setattr(self.config.storage, key, value)
                    
        # Update logging config
        if 'logging' in data:
            logging_data = data['logging']
            for key, value in logging_data.items():
                if hasattr(self.config.logging, key):
                    setattr(self.config.logging, key, value)
                    
        # Update performance config
        if 'performance' in data:
            perf_data = data['performance']
            for key, value in perf_data.items():
                if hasattr(self.config.performance, key):
                    setattr(self.config.performance, key, value)
                    
        # Update file transfer config
        if 'file_transfer' in data:
            ft_data = data['file_transfer']
            for key, value in ft_data.items():
                if hasattr(self.config.file_transfer, key):
                    setattr(self.config.file_transfer, key, value)
    
    def _apply_env_overrides(self):
        """Apply environment variable overrides"""
        env_mappings = {
            # Network overrides
            'DEEZCHAT_SCAN_INTERVAL': ('network.scan_interval', int),
            'DEEZCHAT_MAX_PEERS': ('network.max_peers', int),
            'DEEZCHAT_TTL': ('network.ttl', int),
            
            # Security overrides
            'DEEZCHAT_KEY_ROTATION_INTERVAL': ('security.key_rotation_interval', int),
            'DEEZCHAT_HANDSHAKE_TIMEOUT': ('security.handshake_timeout', int),
            
            # UI overrides
            'DEEZCHAT_THEME': ('ui.theme', str),
            'DEEZCHAT_TIMESTAMP_FORMAT': ('ui.timestamp_format', str),
            
            # Storage overrides
            'DEEZCHAT_DATA_DIR': ('storage.data_dir', str),
            'DEEZCHAT_MAX_HISTORY': ('storage.max_history', int),
            
            # Logging overrides
            'DEEZCHAT_LOG_LEVEL': ('logging.level', str),
            'DEEZCHAT_LOG_FILE': ('logging.file', str),
            
            # Performance overrides
            'DEEZCHAT_ENABLE_METRICS': ('performance.enable_metrics', bool),
            'DEEZCHAT_MEMORY_POOL_SIZE': ('performance.memory_pool_size', int),
        }
        
        for env_var, (config_path, converter) in env_mappings.items():
            if env_var in os.environ:
                try:
                    value = converter(os.environ[env_var])
                    self._set_nested_attr(config_path, value)
                    logger.debug(f"Applied env override: {config_path} = {value}")
                except (ValueError, AttributeError) as e:
                    logger.warning(f"Invalid env override {env_var}: {e}")
    
    def _set_nested_attr(self, path: str, value: Any):
        """Set nested attribute using dot notation"""
        parts = path.split('.')
        obj = self.config
        
        for part in parts[:-1]:
            obj = getattr(obj, part)
            
        setattr(obj, parts[-1], value)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation"""
        try:
            parts = key.split('.')
            obj = self.config
            
            for part in parts:
                obj = getattr(obj, part)
                
            return obj
        except AttributeError:
            return default
    
    def set(self, key: str, value: Any, notify: bool = True) -> bool:
        """Set configuration value using dot notation"""
        old_value = self.get(key)
        success = self._set_nested_attr(key, value)
        
        if success and notify and old_value != value:
            # Note: This is synchronous, so we can't await here
            # In a full async implementation, this would need to be handled differently
            try:
                asyncio.create_task(self._notify_watchers(key, old_value, value))
            except RuntimeError:
                # Event loop not running, store for later
                pass
                
        return success
    
    def _notify_watchers(self, key: str, old_value: Any, new_value: Any):
        """Notify watchers of configuration change"""
        if key in self.watchers:
            for callback in self.watchers[key]:
                try:
                    callback(old_value, new_value)
                except Exception as e:
                    logger.error(f"Config watcher callback error for {key}: {e}")
    
    def watch(self, key: str, callback: Callable[[Any, Any], None]) -> bool:
        """Watch for configuration changes"""
        if key not in self.watchers:
            self.watchers[key] = []
            
        self.watchers[key].append(ConfigChangeCallback(key, callback))
        return True
    
    def unwatch(self, key: str, callback: Callable[[Any, Any], None]) -> bool:
        """Stop watching configuration changes"""
        if key not in self.watchers:
            return False
            
        for i, cb in enumerate(self.watchers[key]):
            if cb.callback == callback:
                del self.watchers[key][i]
                return True
                
        return False
    
    def save(self) -> bool:
        """Save configuration to file"""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            
            # Convert config to dictionary
            config_dict = {
                'network': self.config.network.__dict__,
                'security': self.config.security.__dict__,
                'ui': self.config.ui.__dict__,
                'storage': self.config.storage.__dict__,
                'logging': self.config.logging.__dict__,
                'performance': self.config.performance.__dict__,
                'file_transfer': self.config.file_transfer.__dict__
            }
            
            # Save to file
            with open(self.config_path, 'w', encoding='utf-8') as f:
                if self.config_path.endswith('.yaml') or self.config_path.endswith('.yml'):
                    yaml.dump(config_dict, f, default_flow_style=False, indent=2)
                elif self.config_path.endswith('.json'):
                    json.dump(config_dict, f, indent=2)
                    
            logger.info(f"Saved configuration to {self.config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            return False
    
    def validate(self) -> List[str]:
        """Validate configuration and return list of errors"""
        errors = []
        
        # Validate network config
        if self.config.network.scan_interval < 1:
            errors.append("network.scan_interval must be >= 1")
        if self.config.network.max_peers < 1:
            errors.append("network.max_peers must be >= 1")
        if self.config.network.ttl < 1 or self.config.network.ttl > 255:
            errors.append("network.ttl must be between 1 and 255")
            
        # Validate security config
        if self.config.security.key_rotation_interval < 60:
            errors.append("security.key_rotation_interval must be >= 60 seconds")
        if self.config.security.handshake_timeout < 1:
            errors.append("security.handshake_timeout must be >= 1 second")
            
        # Validate storage config
        if self.config.storage.max_history < 0:
            errors.append("storage.max_history must be >= 0")
            
        # Validate performance config
        if self.config.performance.memory_pool_size < 1024:
            errors.append("performance.memory_pool_size must be >= 1024 bytes")
            
        return errors
    
    def get_effective_data_dir(self) -> str:
        """Get the effective data directory path"""
        path = os.path.expanduser(self.config.storage.data_dir)
        os.makedirs(path, exist_ok=True)
        return path
    
    def get_effective_log_file(self) -> Optional[str]:
        """Get the effective log file path"""
        if self.config.logging.file:
            return os.path.expanduser(self.config.logging.file)
        
        # Default log file path
        data_dir = self.get_effective_data_dir()
        return os.path.join(data_dir, "logs", "deezchat.log")
    
    def reset_to_defaults(self, section: Optional[str] = None):
        """Reset configuration to defaults"""
        if section:
            if hasattr(self.config, section):
                setattr(self.config, section, getattr(Config(), section)())
        else:
            logger.warning(f"Unknown configuration section: {section}")
    
    def export_to_dict(self) -> Dict[str, Any]:
        """Export configuration to dictionary"""
        return {
            'network': self.config.network.__dict__,
            'security': self.config.security.__dict__,
            'ui': self.config.ui.__dict__,
            'storage': self.config.storage.__dict__,
            'logging': self.config.logging.__dict__,
            'performance': self.config.performance.__dict__,
            'file_transfer': self.config.file_transfer.__dict__
        }
    
    def import_from_dict(self, data: Dict[str, Any], merge: bool = True):
        """Import configuration from dictionary"""
        if merge:
            self._update_config_from_dict(data)
        else:
            # Replace entire config
            self.config = Config()
            self._update_config_from_dict(data)

# Utility functions
def create_default_config_file(path: str) -> bool:
    """Create a default configuration file"""
    try:
        default_config = Config()
        config_dict = {
            'network': default_config.network.__dict__,
            'security': default_config.security.__dict__,
            'ui': default_config.ui.__dict__,
            'storage': default_config.storage.__dict__,
            'logging': default_config.logging.__dict__,
            'performance': default_config.performance.__dict__,
            'file_transfer': default_config.file_transfer.__dict__
        }
        
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            if path.endswith('.yaml') or path.endswith('.yml'):
                yaml.dump(config_dict, f, default_flow_style=False, indent=2)
            elif path.endswith('.json'):
                json.dump(config_dict, f, indent=2)
                
        return True
        
    except Exception as e:
        logger.error(f"Failed to create default config file: {e}")
        return False

def get_config_schema() -> Dict[str, Any]:
    """Get configuration schema for validation"""
    return {
        'type': 'object',
        'properties': {
            'network': {
                'type': 'object',
                'properties': {
                    'scan_interval': {'type': 'integer', 'minimum': 1},
                    'max_peers': {'type': 'integer', 'minimum': 1},
                    'ttl': {'type': 'integer', 'minimum': 1, 'maximum': 255},
                    'connection_timeout': {'type': 'integer', 'minimum': 1},
                    'retry_attempts': {'type': 'integer', 'minimum': 1},
                    'fragment_size': {'type': 'integer', 'minimum': 100},
                    'max_message_size': {'type': 'integer', 'minimum': 1000}
                }
            },
            'security': {
                'type': 'object',
                'properties': {
                    'encryption_algorithm': {'type': 'string'},
                    'key_rotation_interval': {'type': 'integer', 'minimum': 60},
                    'handshake_timeout': {'type': 'integer', 'minimum': 1},
                    'session_timeout': {'type': 'integer', 'minimum': 60},
                    'identity_key_path': {'type': 'string'},
                    'require_identity_verification': {'type': 'boolean'}
                }
            },
            'ui': {
                'type': 'object',
                'properties': {
                    'theme': {'type': 'string'},
                    'timestamp_format': {'type': 'string'},
                    'show_fingerprints': {'type': 'boolean'},
                    'max_history_lines': {'type': 'integer', 'minimum': 0},
                    'auto_scroll': {'type': 'boolean'},
                    'color_scheme': {'type': 'string'},
                    'show_connection_status': {'type': 'boolean'},
                    'enable_tab_completion': {'type': 'boolean'}
                }
            },
            'storage': {
                'type': 'object',
                'properties': {
                    'data_dir': {'type': 'string'},
                    'max_history': {'type': 'integer', 'minimum': 0},
                    'compress_history': {'type': 'boolean'},
                    'database_type': {'type': 'string'},
                    'backup_enabled': {'type': 'boolean'},
                    'backup_interval': {'type': 'integer', 'minimum': 60},
                    'max_backup_size': {'type': 'integer', 'minimum': 1}
                }
            },
            'logging': {
                'type': 'object',
                'properties': {
                    'level': {'type': 'string', 'enum': ['DEBUG', 'INFO', 'WARNING', 'ERROR']},
                    'file': {'type': 'string'},
                    'max_size': {'type': 'string'},
                    'backup_count': {'type': 'integer', 'minimum': 1},
                    'console_output': {'type': 'boolean'},
                    'format': {'type': 'string'}
                }
            },
            'performance': {
                'type': 'object',
                'properties': {
                    'memory_pool_size': {'type': 'integer', 'minimum': 1024},
                    'max_concurrent_operations': {'type': 'integer', 'minimum': 1},
                    'enable_metrics': {'type': 'boolean'},
                    'metrics_interval': {'type': 'integer', 'minimum': 1},
                    'enable_profiling': {'type': 'boolean'}
                }
            },
            'file_transfer': {
                'type': 'object',
                'properties': {
                    'max_file_size': {'type': 'integer', 'minimum': 1024},
                    'max_concurrent_transfers': {'type': 'integer', 'minimum': 1},
                    'chunk_size': {'type': 'integer', 'minimum': 1024},
                    'temp_dir': {'type': 'string'},
                    'auto_accept_transfers': {'type': 'boolean'},
                    'verify_checksums': {'type': 'boolean'}
                }
            }
        }
    }