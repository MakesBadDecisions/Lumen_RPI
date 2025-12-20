"""
LUMEN State - Printer state detection

Monitors Klipper objects and detects printer events.
"""

import time
from dataclasses import dataclass, field
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
    Detects printer events from state changes.
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
        
        self._idle_start: Optional[float] = time.time()
        self._bored_start: Optional[float] = None
    
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
        """Determine current event from printer state."""
        
        # Error state takes priority
        if state.klipper_state in ("shutdown", "error"):
            return PrinterEvent.ERROR
        
        # Printing - with hysteresis to prevent flapping
        if state.print_state == "printing":
            # If already printing, stay printing unless we're clearly heating
            # (more than 10°C below target = genuinely heating up)
            if self._current_event == PrinterEvent.PRINTING:
                if state.clearly_heating(threshold=10.0):
                    return PrinterEvent.HEATING
                return PrinterEvent.PRINTING
            
            # Not yet in printing state - enter printing once at temp
            if state.is_heating and not state.at_temp():
                return PrinterEvent.HEATING
            return PrinterEvent.PRINTING
        
        # Heating (not printing)
        if state.is_heating:
            return PrinterEvent.HEATING
        
        # Cooldown
        if state.is_hot and not state.is_heating:
            return PrinterEvent.COOLDOWN
        
        # Idle timers
        if self._idle_start:
            idle_seconds = now - self._idle_start
            
            if self._bored_start:
                bored_seconds = now - self._bored_start
                if bored_seconds >= self.sleep_timeout:
                    return PrinterEvent.SLEEP
            
            if idle_seconds >= self.bored_timeout:
                if not self._bored_start:
                    self._bored_start = now
                return PrinterEvent.BORED
        
        return PrinterEvent.IDLE
    
    def _transition(self, new_event: PrinterEvent, now: float) -> None:
        """Handle event transition."""
        self._previous_event = self._current_event
        self._current_event = new_event
        
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
            except Exception:
                pass
    
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
            "idle_seconds": (now - self._idle_start) if self._idle_start else 0,
            "bored_seconds": (now - self._bored_start) if self._bored_start else 0,
            "bored_timeout": self.bored_timeout,
            "sleep_timeout": self.sleep_timeout,
        }
