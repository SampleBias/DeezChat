"""
Utility modules for DeezChat

Contains compression, fragmentation, metrics, and other utilities.
"""

from .compression import compress_if_beneficial, decompress
from .fragmentation import fragment_payload, Fragment, FragmentType
from .metrics import MetricsCollector

__all__ = [
    'compress_if_beneficial',
    'decompress',
    'fragment_payload',
    'Fragment',
    'FragmentType',
    'MetricsCollector'
]