"""
Heating State Detector - Detects heaters warming up
"""

from typing import Dict, Any, Optional
from .base import BaseStateDetector


class HeatingDetector(BaseStateDetector):
    """
    Detects when heaters are actively warming up to target temperature.

    Detection logic:
        - Any heater (bed, extruder, chamber) has target > 0
        - Current temp is below target (not yet reached) OR heater power active
        - Hysteresis: stays in heating for STABLE_TIME seconds after conditions met
          to prevent flickering from brief power drops

    Common scenarios:
        - Preheat bed before print
        - Heat soak chamber
        - Nozzle warm-up during PRINT_START
    """

    name = "heating"
    description = "Heaters warming up to target temperature"
    priority = 20

    TEMP_TOLERANCE = 2.0  # Degrees C - stay in heating until within 2°C of target
    POWER_THRESHOLD = 0.01  # 1% - only when power drops to ~0% do we start the stability timer
    STABLE_TIME = 10.0  # Seconds - heater must be at temp AND low power for this long before exiting

    def __init__(self):
        super().__init__()
        self._stable_since: Optional[float] = None  # Track when we first became stable

    def detect(
        self,
        status: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Check if any heater is actively heating."""

        current_time = context.get('current_time', 0.0) if context else 0.0

        # Check all heaters for active heating
        heating_active = self._is_heating_active(status)

        if heating_active:
            # Actively heating - reset stability timer
            self._stable_since = None
            return True

        # Not actively heating - check if we should stay in heating due to other conditions

        # CRITICAL: If we're in PRINT_START phase (temps reached but still doing probing/meshing/purge),
        # STAY in heating state until actual print begins
        if self._is_print_starting(status):
            # Reset stability timer - we want to stay in heating throughout PRINT_START
            self._stable_since = None
            return True

        # If we have no targets set at all, definitely exit heating immediately
        if not self._any_targets_set(status):
            self._stable_since = None
            return False

        # Targets are set but heaters are stable (at temp and low power)
        # Start/continue stability timer
        if self._stable_since is None:
            self._stable_since = current_time

        # Check if we've been stable long enough to exit heating
        stable_duration = current_time - self._stable_since
        if stable_duration >= self.STABLE_TIME:
            # Been stable long enough - exit heating
            self._stable_since = None
            return False

        # Still within stability grace period - stay in heating
        return True

    def _any_targets_set(self, status: Dict[str, Any]) -> bool:
        """Check if any heater has a target > 0."""
        extruder = status.get('extruder', {})
        heater_bed = status.get('heater_bed', {})
        chamber = status.get('heater_generic chamber', {})

        return (extruder.get('target', 0) > 0 or
                heater_bed.get('target', 0) > 0 or
                chamber.get('target', 0) > 0)

    def _is_print_starting(self, status: Dict[str, Any]) -> bool:
        """Check if we're in PRINT_START phase (printing state but not actually printing yet)."""
        print_stats = status.get('print_stats', {})
        ps_state = print_stats.get('state', '').lower()

        # If print_stats shows 'printing', we're in PRINT_START or actively printing
        if ps_state != 'printing':
            return False

        # Check if we've actually started printing by looking at progress
        display_status = status.get('display_status', {})
        progress = display_status.get('progress', 0.0)

        # If progress is 0 or very low (<1%), we're still in PRINT_START phase
        return progress < 0.01

    def _is_heating_active(self, status: Dict[str, Any]) -> bool:
        """Check if any heater is actively heating (below target or power active)."""

        # Check extruder
        extruder = status.get('extruder', {})
        ext_temp = extruder.get('temperature', 0)
        ext_target = extruder.get('target', 0)
        ext_power = extruder.get('power', 0)

        if ext_target > 0:
            # Not at temp yet - still actively heating up
            if (ext_temp + self.TEMP_TOLERANCE) < ext_target:
                return True
            # At temp - check if power is above 1% (maintaining temperature)
            if ext_power > self.POWER_THRESHOLD:
                return True

        # Check bed
        heater_bed = status.get('heater_bed', {})
        bed_temp = heater_bed.get('temperature', 0)
        bed_target = heater_bed.get('target', 0)
        bed_power = heater_bed.get('power', 0)

        if bed_target > 0:
            # Not at temp yet - still actively heating up
            if (bed_temp + self.TEMP_TOLERANCE) < bed_target:
                return True
            # At temp - check if power is above 1% (maintaining temperature)
            if bed_power > self.POWER_THRESHOLD:
                return True

        # Check chamber (if available)
        chamber = status.get('temperature_sensor chamber', {})
        if not chamber:
            # Try alternate chamber heater name
            chamber = status.get('heater_generic chamber', {})

        chamber_temp = chamber.get('temperature', 0)
        chamber_target = chamber.get('target', 0)
        chamber_power = chamber.get('power', 0)

        # Chamber heater check (if it has power field)
        if chamber_target > 0:
            # Not at temp yet - still actively heating up
            if (chamber_temp + self.TEMP_TOLERANCE) < chamber_target:
                return True
            # At temp - check if power is above 1% (heater_generic has power, temperature_sensor doesn't)
            if chamber_power > self.POWER_THRESHOLD:
                return True

        return False
