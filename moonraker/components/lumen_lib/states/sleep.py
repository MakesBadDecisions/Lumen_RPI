"""
Sleep State Detector - Detects very extended idle time
"""

from typing import Dict, Any, Optional
from .base import BaseStateDetector


class SleepDetector(BaseStateDetector):
    """
    Detects when printer has been idle/bored for a very extended period.

    Detection logic:
        - Currently in "bored" state
        - Bored duration exceeds sleep_timeout
        - Deep idle with no activity

    This state is time-based and requires context tracking of how long
    the printer has been bored.

    Common use:
        - Turn off LEDs to save power
        - Dim lights for nighttime operation
        - Deep idle state until next print
    """

    name = "sleep"
    description = "Very extended idle period (deep sleep)"
    priority = 90  # Very low priority, checked after bored

    def detect(
        self,
        status: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Check if printer has been bored long enough to 'sleep'."""

        if not context:
            return False

        # First check: printer must be truly idle (no active states)
        # Check no heaters active
        extruder = status.get('extruder', {})
        heater_bed = status.get('heater_bed', {})
        if extruder.get('target', 0) > 0 or heater_bed.get('target', 0) > 0:
            return False

        # Check not printing
        print_stats = status.get('print_stats', {})
        if print_stats.get('state', '').lower() in ['printing', 'paused']:
            return False

        # Check not error
        if status.get('idle_timeout', {}).get('state', '').lower() == 'error':
            return False

        # Get sleep timeout from context
        sleep_timeout = context.get('sleep_timeout', 300.0)

        # Get current state info
        last_state = context.get('last_state', '')
        state_enter_time = context.get('state_enter_time', 0.0)
        current_time = context.get('current_time', 0.0)

        # If we were already asleep, stay asleep
        if last_state == 'sleep':
            return True

        # Must currently be in bored state to transition to sleep
        if last_state != 'bored':
            return False

        # Check if we've been bored long enough
        bored_duration = current_time - state_enter_time

        if bored_duration >= sleep_timeout:
            return True

        return False
