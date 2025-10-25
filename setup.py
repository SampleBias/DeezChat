"""
Setup script for DeezChat package

This script handles installation, packaging, and distribution of DeezChat.
"""

import os
import sys
from pathlib import Path
from setuptools import setup, find_packages
from setuptools.command.install import install
from setuptools.command.develop import develop
from setuptools.command.egg_info import egg_info

# Read version from __init__.py
def get_version():
    version_file = Path(__file__).parent / "deezchat" / "__init__.py"
    with open(version_file, 'r') as f:
        for line in f:
            if line.startswith('__version__'):
                return line.split('=')[1].strip().strip('"')
    return "1.0.0"  # Fallback

# Read long description from README
def get_long_description():
    readme_file = Path(__file__).parent / "README.md"
    try:
        with open(readme_file, 'r', encoding='utf-8') as f:
            # Extract description from first paragraph
            lines = f.readlines()
            if lines:
                # Skip title and badges
                start_idx = 0
                for i, line in enumerate(lines):
                    if line.startswith('# DeezChat'):
                        start_idx = i + 1
                        break
                
                # Find first empty line after description
                for i in range(start_idx, len(lines)):
                    if not lines[i].strip():
                        return '\n'.join(lines[start_idx:i]).strip()
    except Exception:
        return "DeezChat - BitChat Python Client\n\nA decentralized, encrypted peer-to-peer chat client over Bluetooth Low Energy."
    
    return "DeezChat - BitChat Python Client"

# Read requirements
def get_requirements():
    """Get requirements from requirements.txt or return default"""
    requirements_file = Path(__file__).parent / "requirements.txt"
    
    if requirements_file.exists():
        with open(requirements_file, 'r') as f:
            return [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    # Default requirements
    return [
        'bleak>=0.20.0',
        'cryptography>=3.4.8',
        'pybloom-live>=4.0.0',
        'aioconsole>=0.6.0',
        'lz4>=3.1.0',
        'PyYAML>=6.0',
        'aiosqlite>=0.17.0',
        'pytest>=7.0.0',
        'pytest-asyncio>=0.21.0',
        'pytest-cov>=4.0.0',
        'black>=22.0.0',
        'isort>=5.10.0',
        'flake8>=5.0.0',
        'mypy>=1.0.0',
        'setuptools>=60.0.0',
        'wheel>=0.37.0',
        'twine>=4.0.0'
    ]

class CustomInstallCommand(install):
    """Custom install command that handles additional setup"""
    
    def run(self):
        # Run standard install
        install.run(self)
        
        # Create default config directory
        config_dir = Path.home() / ".config" / "deezchat"
        config_dir.mkdir(parents=True, exist_ok=True)
        
        # Create default data directory
        data_dir = Path.home() / ".local" / "share" / "deezchat"
        data_dir.mkdir(parents=True, exist_ok=True)
        
        # Create default log directory
        log_dir = data_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"\n✅ Created default directories:")
        print(f"   Config: {config_dir}")
        print(f"   Data: {data_dir}")
        print(f"   Logs: {log_dir}")
        print(f"\n📝 Configuration file: {config_dir / 'config.yaml'}")
        print(f"📝 Data directory: {data_dir}")
        print(f"\n🚀 To run DeezChat:")
        print(f"   deezchat")
        print(f"   or")
        print(f"   python -m deezchat")

class CustomDevelopCommand(develop):
    """Custom develop command that handles additional setup"""
    
    def run(self):
        # Run standard develop
        develop.run(self)
        
        # Install in development mode
        print("\n🔧 Development mode installed")
        print("   Run with: deezchat --debug")

# Package metadata
NAME = "deezchat"
DESCRIPTION = "DeezChat - BitChat Python Client"
LONG_DESCRIPTION = get_long_description()
VERSION = get_version()
AUTHOR = "DeezChat Team"
AUTHOR_EMAIL = "contact@deezchat.org"
URL = "https://github.com/deezchat/deezchat"
PROJECT_URLS = {
    "Bug Reports": "https://github.com/deezchat/deezchat/issues",
    "Source": "https://github.com/deezchat/deezchat",
    "Documentation": "https://github.com/deezchat/deezchat/wiki"
}
LICENSE = "MIT"
CLASSIFIERS = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: End Users/Desktop",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.8",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Topic :: Communications :: Chat",
    "Topic :: Security :: Cryptography",
    "Topic :: System :: Networking"
]
KEYWORDS = [
    "bitchat",
    "chat",
    "bluetooth",
    "ble",
    "decentralized",
    "encrypted",
    "p2p",
    "peer-to-peer",
    "privacy",
    "security",
    "noise-protocol",
    "cryptography"
]
PYTHON_REQUIRES = ">=3.8"
INSTALL_REQUIRES = get_requirements()
EXTRAS_REQUIREMENTS = {
    "dev": [
        "pytest>=7.0.0",
        "pytest-asyncio>=0.21.0",
        "pytest-cov>=4.0.0",
        "black>=22.0.0",
        "isort>=5.10.0",
        "flake8>=5.0.0",
        "mypy>=1.0.0",
        "twine>=4.0.0"
    ],
    "test": [
        "pytest>=7.0.0",
        "pytest-asyncio>=0.21.0",
        "pytest-cov>=4.0.0"
    ]
}
EXTRAS = {
    "dev": EXTRAS_REQUIREMENTS["dev"],
    "test": EXTRAS_REQUIREMENTS["test"]
}
PACKAGES = find_packages(exclude=["tests", "tests.*"])
PACKAGE_DATA = {
    "deezchat": [
        "config.yaml",
        "config.yml",
        "config.json"
    ]
}
DATA_FILES = [
    ("config", ["config.yaml", "config.yml", "config.json"]),
    ("share/deezchat", []),
    ("share/doc", ["README.md", "LICENSE", "CHANGELOG.md"])
]
ENTRY_POINTS = {
    "console_scripts": [
        "deezchat=deezchat.__main__:run"
    ]
}
INCLUDE_PACKAGE_DATA = True
ZIP_SAFE = False

# Additional metadata for PyPI
PLATFORMS = ["any"]

# Setup configuration
setup(
    name=NAME,
    version=VERSION,
    description=DESCRIPTION,
    long_description=LONG_DESCRIPTION,
    long_description_content_type="text/plain",
    author=AUTHOR,
    author_email=AUTHOR_EMAIL,
    url=URL,
    project_urls=PROJECT_URLS,
    license=LICENSE,
    classifiers=CLASSIFIERS,
    keywords=KEYWORDS,
    python_requires=PYTHON_REQUIRES,
    install_requires=INSTALL_REQUIRES,
    extras_require=EXTRAS_REQUIREMENTS,
    packages=PACKAGES,
    package_data=PACKAGE_DATA,
    data_files=DATA_FILES,
    entry_points=ENTRY_POINTS,
    include_package_data=INCLUDE_PACKAGE_DATA,
    zip_safe=ZIP_SAFE,
    platforms=PLATFORMS,
    cmdclass={
        'install': CustomInstallCommand,
        'develop': CustomDevelopCommand
    }
)