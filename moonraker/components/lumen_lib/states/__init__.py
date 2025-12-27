"""
State Detection System - Modular printer state detectors

This module provides a registry of state detector classes that analyze printer
status to determine the current operational state.

Usage:
    from .states import STATE_REGISTRY

    detector = STATE_REGISTRY['heating']()
    if detector.detect(printer_status):
        # Heating state detected
        ...

Available States:
    - idle: Printer ready, all temps nominal, not printing
    - heating: Heaters active, warming up to target
    - printing: Active print job, at temperature
    - cooldown: Print finished, still above ambient temp
    - error: Klipper shutdown or error condition
    - bored: Idle for extended period (timeout-based)
    - sleep: Bored for extended period (timeout-based)
"""

from typing import Dict, Type
from .base import BaseStateDetector

# Import all state detector implementations
from .idle import IdleDetector
from .heating import HeatingDetector
from .printing import PrintingDetector
from .cooldown import CooldownDetector
from .error import ErrorDetector
from .bored import BoredDetector
from .sleep import SleepDetector


# State registry: maps state names to detector classes
STATE_REGISTRY: Dict[str, Type[BaseStateDetector]] = {
    'idle': IdleDetector,
    'heating': HeatingDetector,
    'printing': PrintingDetector,
    'cooldown': CooldownDetector,
    'error': ErrorDetector,
    'bored': BoredDetector,
    'sleep': SleepDetector,
}


# Evaluation order (most specific to least specific)
# Error and printing should be checked first, idle last
STATE_PRIORITY = [
    'error',      # Highest priority - always check errors first
    'printing',   # Active print job
    'heating',    # Warming up
    'cooldown',   # Cooling down after print
    'sleep',      # Timeout-based deep idle
    'bored',      # Timeout-based idle
    'idle',       # Default fallback state
]


__all__ = [
    'STATE_REGISTRY',
    'STATE_PRIORITY',
    'BaseStateDetector',
    'IdleDetector',
    'HeatingDetector',
    'PrintingDetector',
    'CooldownDetector',
    'ErrorDetector',
    'BoredDetector',
    'SleepDetector',
]
