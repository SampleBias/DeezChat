"""
Utility modules for DeezChat

Contains compression, fragmentation, metrics, and other utilities.
"""

from .compression import compress_if_beneficial, decompress
from .frangmentation import fragment_payload, Fragment, FragmentType, MAX_FRAGMENT_SIZE
from .metrics import MetricsCollector

__all__ = [
    'compress_if_beneficial',
    'decompress',
    'fragment_payload',
    'Fragment',
    'FragmentType',
    'MAX_FRAGMENT_SIZE',
    'MetricsCollector'
]