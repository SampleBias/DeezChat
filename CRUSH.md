# DeezChat Development Guide

## Commands

### Installation
```bash
pip install -e ".[dev]"  # Development with all dev dependencies
pip install -e ".[test]"  # Test dependencies only
pip install -e .          # Production install
```

### Testing
```bash
pytest                    # Run all tests
pytest --cov=deezchat     # Run with coverage
pytest tests/test_client.py  # Run specific test file
pytest -v                 # Verbose output
```

### Code Quality
```bash
black deezchat/           # Format code
isort deezchat/           # Sort imports
flake8 deezchat/          # Lint code
mypy deezchat/            # Type checking
```

### Running Application
```bash
deezchat                  # Run installed package
python -m deezchat        # Run as module
python bitchat.py         # Run legacy main
```

## Code Style Guidelines

### Structure & Patterns
- Modern Python with type hints for all functions
- Async/await for network operations
- Dataclasses for data structures
- Enum classes for constants
- Comprehensive docstrings

### Import Organization
```python
# Standard library
import os
import asyncio
import logging
from typing import Optional, Dict, List, Any

# Third-party imports  
from bleak import BleakScanner
from dataclasses import dataclass, field

# Local imports with relative imports
from ..storage.config import Config
from .utils.compression import compress_if_beneficial
```

### Error Handling
- Custom exception classes (e.g., `BLEConnectionError`)
- Try/catch blocks with specific exception handling
- Logging at appropriate levels (debug, info, error)

### Naming Conventions
- `snake_case` for variables and functions
- `PascalCase` for classes
- `UPPER_SNAKE_CASE` for constants
- Descriptive method names like `_setup_logging()`, `_register_event_handlers()`

### Code Organization
- Layered architecture (client → network → transport)
- Event-driven design with callback registration
- Background tasks with asyncio.create_task()
- State management in dataclasses