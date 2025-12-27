"""
Printing State Detector - Detects active print job
"""

from typing import Dict, Any, Optional
from .base import BaseStateDetector


class PrintingDetector(BaseStateDetector):
    """
    Detects when printer is actively printing.

    Detection logic:
        - print_stats state is "printing" or "paused"
        - At target temperature (within tolerance)
        - Print file is loaded

    Note: Paused prints are considered "printing" state to maintain
    work lights and progress indicators. Future versions may split
    this into separate "paused" state.
    """

    name = "printing"
    description = "Active print job in progress"
    priority = 10  # High priority (after error)

    TEMP_TOLERANCE = 10.0  # Degrees C tolerance for "at temp" - increased from 3.0 to prevent flickering during print

    def detect(
        self,
        status: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Check if actively printing."""

        print_stats = status.get('print_stats', {})
        ps_state = print_stats.get('state', '').lower()

        # Must be in printing or paused state
        if ps_state not in ['printing', 'paused']:
            return False

        # Optional: Verify we're at temperature (prevents false positives during heat-up)
        # If any heater has a target > 0, check if we're within tolerance
        extruder = status.get('extruder', {})
        ext_temp = extruder.get('temperature', 0)
        ext_target = extruder.get('target', 0)

        heater_bed = status.get('heater_bed', {})
        bed_temp = heater_bed.get('temperature', 0)
        bed_target = heater_bed.get('target', 0)

        # If extruder has target and we're not close, still heating
        # Using wider tolerance (10°C) to prevent flicker during normal temp fluctuations
        if ext_target > 0 and abs(ext_temp - ext_target) > self.TEMP_TOLERANCE:
            return False

        # If bed has target and we're not close, still heating
        # Bed temps are more stable, so we can be stricter here
        if bed_target > 0 and abs(bed_temp - bed_target) > 5.0:
            return False

        return True
