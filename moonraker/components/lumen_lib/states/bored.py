"""
Bored State Detector - Detects extended idle time
"""

from typing import Dict, Any, Optional
from .base import BaseStateDetector


class BoredDetector(BaseStateDetector):
    """
    Detects when printer has been idle for an extended period.

    Detection logic:
        - Currently in "idle" state
        - Idle duration exceeds bored_timeout
        - Not yet in "sleep" state

    This state is time-based and requires context tracking of how long
    the printer has been idle.

    Common use:
        - Transition from static "idle" lights to animated "bored" effects
        - Show disco/rainbow patterns during long idle periods
        - Attract attention when printer is available
    """

    name = "bored"
    description = "Extended idle period (timeout-based)"
    priority = 80  # Low priority, checked after active states

    def detect(
        self,
        status: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Check if printer has been idle long enough to be 'bored'."""

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

        # Get bored timeout from context
        bored_timeout = context.get('bored_timeout', 60.0)

        # Get current state info - track how long we've been in idle/bored
        last_state = context.get('last_state', '')
        state_enter_time = context.get('state_enter_time', 0.0)
        current_time = context.get('current_time', 0.0)

        # If we were already bored, stay bored (until sleep timeout)
        if last_state == 'bored':
            return True

        # If we were idle, check if enough time has passed
        if last_state == 'idle':
            idle_duration = current_time - state_enter_time
            return idle_duration >= bored_timeout

        return False
