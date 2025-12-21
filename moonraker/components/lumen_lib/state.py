"""
LUMEN State - Printer state detection

Monitors Klipper objects and detects printer events using modular state detectors.
"""

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class PrinterEvent(Enum):
    """Printer state events that trigger LED changes."""
    IDLE = "idle"
    HEATING = "heating"
    PRINTING = "printing"
    COOLDOWN = "cooldown"
    ERROR = "error"
    BORED = "bored"
    SLEEP = "sleep"


@dataclass
class PrinterState:
    """Current printer state from Klipper objects."""
    klipper_state: str = "startup"
    print_state: str = "standby"
    progress: float = 0.0
    filename: str = ""
    
    bed_temp: float = 0.0
    bed_target: float = 0.0
    extruder_temp: float = 0.0
    extruder_target: float = 0.0
    
    position_x: float = 0.0
    position_y: float = 0.0
    position_z: float = 0.0
    
    idle_state: str = "Ready"
    
    def update_from_status(self, status: Dict[str, Any]) -> None:
        """Update state from Moonraker status update."""
        if "webhooks" in status:
            wh = status["webhooks"]
            if "state" in wh:
                self.klipper_state = wh["state"]
        
        if "print_stats" in status:
            ps = status["print_stats"]
            if "state" in ps:
                self.print_state = ps["state"]
            if "filename" in ps:
                self.filename = ps.get("filename", "")
        
        if "display_status" in status:
            ds = status["display_status"]
            if "progress" in ds:
                self.progress = ds.get("progress", 0.0) or 0.0
        
        if "heater_bed" in status:
            hb = status["heater_bed"]
            if "temperature" in hb:
                self.bed_temp = hb.get("temperature", 0.0) or 0.0
            if "target" in hb:
                self.bed_target = hb.get("target", 0.0) or 0.0
        
        if "extruder" in status:
            ex = status["extruder"]
            if "temperature" in ex:
                self.extruder_temp = ex.get("temperature", 0.0) or 0.0
            if "target" in ex:
                self.extruder_target = ex.get("target", 0.0) or 0.0
        
        if "toolhead" in status:
            th = status["toolhead"]
            if "position" in th:
                pos = th["position"]
                if len(pos) >= 3:
                    self.position_x = pos[0] or 0.0
                    self.position_y = pos[1] or 0.0
                    self.position_z = pos[2] or 0.0
        
        if "idle_timeout" in status:
            it = status["idle_timeout"]
            if "state" in it:
                self.idle_state = it["state"]
    
    @property
    def is_heating(self) -> bool:
        """True if any heater has a target set."""
        return self.bed_target > 0 or self.extruder_target > 0
    
    @property
    def is_hot(self) -> bool:
        """True if any heater is above ambient (40°C threshold)."""
        return self.bed_temp > 40 or self.extruder_temp > 40
    
    def at_temp(self, tolerance: float = 2.0) -> bool:
        """True if heaters are at target temperature."""
        bed_ok = (self.bed_target == 0 or 
                  abs(self.bed_temp - self.bed_target) <= tolerance)
        ext_ok = (self.extruder_target == 0 or 
                  abs(self.extruder_temp - self.extruder_target) <= tolerance)
        return bed_ok and ext_ok
    
    def clearly_heating(self, threshold: float = 10.0) -> bool:
        """True if heaters are significantly below target (hysteresis for state changes)."""
        if self.bed_target > 0 and (self.bed_target - self.bed_temp) > threshold:
            return True
        if self.extruder_target > 0 and (self.extruder_target - self.extruder_temp) > threshold:
            return True
        return False


EventCallback = Callable[[PrinterEvent], None]


class StateDetector:
    """
    Modular state detector using pluggable state detector modules.

    Each state is a separate module in lumen_lib/states/ directory.

    Adding new states:
        1. Create detector in lumen_lib/states/my_state.py
        2. Add to STATE_REGISTRY in lumen_lib/states/__init__.py
        3. Add to STATE_PRIORITY list
    """

    def __init__(
        self,
        temp_floor: float = 25.0,
        bored_timeout: float = 300.0,
        sleep_timeout: float = 600.0,
    ):
        self.temp_floor = temp_floor
        self.bored_timeout = bored_timeout
        self.sleep_timeout = sleep_timeout

        self._current_event = PrinterEvent.IDLE
        self._previous_event = PrinterEvent.IDLE
        self._listeners: List[EventCallback] = []

        # State timing tracking
        self._state_enter_time: float = time.time()
        self._idle_start: Optional[float] = time.time()
        self._bored_start: Optional[float] = None

        # Load modular state detectors
        from .states import STATE_REGISTRY, STATE_PRIORITY
        self._detector_registry = STATE_REGISTRY
        self._detector_priority = STATE_PRIORITY
        self._detectors = {
            name: detector_class()
            for name, detector_class in STATE_REGISTRY.items()
        }

    def add_listener(self, callback: EventCallback) -> None:
        """Register a callback for event changes."""
        self._listeners.append(callback)

    def update(self, state: PrinterState) -> Optional[PrinterEvent]:
        """
        Evaluate state and detect event changes.
        Returns the new event if changed, None otherwise.
        """
        now = time.time()
        new_event = self._detect_event(state, now)

        if new_event != self._current_event:
            self._transition(new_event, now)
            return new_event

        return None

    def _detect_event(self, state: PrinterState, now: float) -> PrinterEvent:
        """Detect event using modular detector system."""

        # Build status dict from PrinterState for modular detectors
        status = {
            'webhooks': {'state': state.klipper_state},
            'print_stats': {
                'state': state.print_state,
                'filename': state.filename,
            },
            'display_status': {'progress': state.progress},
            'heater_bed': {
                'temperature': state.bed_temp,
                'target': state.bed_target,
            },
            'extruder': {
                'temperature': state.extruder_temp,
                'target': state.extruder_target,
            },
            'toolhead': {
                'position': [state.position_x, state.position_y, state.position_z],
            },
            'idle_timeout': {'state': state.idle_state},
        }

        # Build context for time-based detectors
        context = {
            'temp_floor': self.temp_floor,
            'bored_timeout': self.bored_timeout,
            'sleep_timeout': self.sleep_timeout,
            'last_state': self._current_event.value,
            'state_enter_time': self._state_enter_time,
            'current_time': now,
        }

        # Check detectors in priority order (error first, idle last)
        for state_name in self._detector_priority:
            detector = self._detectors.get(state_name)
            if detector and detector.detect(status, context):
                return PrinterEvent(state_name)

        # Fallback to idle if no detector matched
        return PrinterEvent.IDLE

    def _transition(self, new_event: PrinterEvent, now: float) -> None:
        """Handle event transition."""
        self._previous_event = self._current_event
        self._current_event = new_event
        self._state_enter_time = now

        # Reset timers based on new state
        if new_event in (PrinterEvent.HEATING, PrinterEvent.PRINTING,
                         PrinterEvent.COOLDOWN, PrinterEvent.ERROR):
            self._idle_start = None
            self._bored_start = None
        elif new_event == PrinterEvent.IDLE:
            self._idle_start = now
            self._bored_start = None
        elif new_event == PrinterEvent.BORED:
            self._bored_start = now

        # Notify listeners
        for callback in self._listeners:
            try:
                callback(new_event)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"State listener callback failed: {e}")

    @property
    def current_event(self) -> PrinterEvent:
        return self._current_event

    def force_event(self, event: PrinterEvent) -> None:
        """Force a specific event (for testing)."""
        self._transition(event, time.time())

    def status(self) -> Dict[str, Any]:
        """Return current detector status."""
        now = time.time()
        return {
            "current_event": self._current_event.value,
            "previous_event": self._previous_event.value,
            "detectors_loaded": list(self._detectors.keys()),
            "idle_seconds": (now - self._idle_start) if self._idle_start else 0,
            "bored_seconds": (now - self._bored_start) if self._bored_start else 0,
            "bored_timeout": self.bored_timeout,
            "sleep_timeout": self.sleep_timeout,
        }
