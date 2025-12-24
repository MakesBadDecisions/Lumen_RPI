"""
LUMEN - Moonraker Component

The conductor - imports from lumen_lib and orchestrates LED effects.

Installation:
    ln -sf ~/lumen/moonraker/components/lumen.py ~/moonraker/moonraker/components/
    ln -sf ~/lumen/moonraker/components/lumen_lib ~/moonraker/moonraker/components/
"""

from __future__ import annotations

__version__ = "1.0.0"

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

# Add our directory to path so we can import lumen_lib
_component_dir = Path(__file__).parent
if str(_component_dir) not in sys.path:
    sys.path.insert(0, str(_component_dir))

from lumen_lib import (
    RGB, get_color, list_colors,
    EffectState,
    LEDDriver, KlipperDriver, PWMDriver, create_driver,
    PrinterState, PrinterEvent, StateDetector,
)
from lumen_lib.effects import EFFECT_REGISTRY

if TYPE_CHECKING:
    from confighelper import ConfigHelper
    from websockets import WebRequest

_logger = logging.getLogger(__name__)


class Lumen:
    """
    LUMEN Moonraker Component - The Conductor
    
    Monitors printer state and triggers LED effects.
    """
    
    def __init__(self, config: ConfigHelper) -> None:
        self.server = config.get_server()
        self.config = config
        
        # Config from moonraker.conf
        self.config_path = config.get("config_path", "~/printer_data/config/lumen.cfg")
        # debug: False, True (journal only), or "console" (journal + Mainsail)
        debug_val = config.get("debug", "false").lower()
        self.debug = debug_val in ("true", "console")
        self.debug_console = debug_val == "console"
        
        # Settings (loaded from lumen.cfg)
        self.temp_floor = 25.0
        self.bored_timeout = 300.0
        self.sleep_timeout = 600.0
        self.max_brightness = 0.4
        self.update_rate = 0.1
        self.update_rate_printing = 1.0
        self.gpio_fps = 60
        # Bed dimensions for KITT tracking
        self.bed_x_min = 0.0
        self.bed_x_max = 300.0
        self.bed_y_min = 0.0
        self.bed_y_max = 300.0
        
        # LED groups, drivers, effects
        self.led_groups: Dict[str, Dict[str, Any]] = {}
        self.event_mappings: Dict[str, List[Dict[str, str]]] = {}
        self.effect_settings: Dict[str, Dict[str, str]] = {}
        self.drivers: Dict[str, LEDDriver] = {}
        self.effect_states: Dict[str, EffectState] = {}
        self.effect_instances: Dict[str, Any] = {}  # Cache effect instances (one per effect type)
        
        # Config validation warnings (collected during load)
        self.config_warnings: List[str] = []
        
        # Animation loop
        self._animation_task: Optional[asyncio.Task] = None
        self._animation_running = False
        
        # Telemetry (position tracking for debugging/PONG development)
        self.telemetry_enabled = False
        self.telemetry_path: Optional[Path] = None
        self._telemetry_file = None
        self._last_position: Tuple[float, float, float] = (0.0, 0.0, 0.0)
        self._position_count = 0
        self._last_thermal_log: Dict[str, Tuple[float, float, float]] = {}  # group_name -> (time, current_temp, target_temp)
        
        # Load config and create drivers
        self._load_config()
        self._create_drivers()
        for name in self.drivers:
            self.effect_states[name] = EffectState()
        
        # State detection
        self.printer_state = PrinterState()
        self.state_detector = StateDetector(
            temp_floor=self.temp_floor,
            bored_timeout=self.bored_timeout,
            sleep_timeout=self.sleep_timeout,
        )
        self.klippy_ready = False
        
        # Register handlers
        self.server.register_event_handler("server:klippy_ready", self._on_klippy_ready)
        self.server.register_event_handler("server:klippy_shutdown", self._on_klippy_shutdown)
        self.server.register_event_handler("server:klippy_disconnected", self._on_klippy_disconnected)
        self.server.register_event_handler("server:status_update", self._on_status_update)
        self.server.register_event_handler("server:exit", self._on_server_shutdown)
        self.state_detector.add_listener(self._on_event_change)
        
        # Register API endpoints
        self.server.register_endpoint("/server/lumen/status", ["GET"], self._handle_status)
        self.server.register_endpoint("/server/lumen/colors", ["GET"], self._handle_colors)
        self.server.register_endpoint("/server/lumen/test_event", ["POST"], self._handle_test_event)
        self.server.register_endpoint("/server/lumen/reload", ["POST"], self._handle_reload)
        
        # Log initialization
        self._log_info(f"Initialized with {len(self.led_groups)} groups")
        if self.config_warnings:
            for warn in self.config_warnings:
                self._log_warning(warn)

    # ─────────────────────────────────────────────────────────────
    # Task Exception Handling
    # ─────────────────────────────────────────────────────────────

    def _task_exception_handler(self, task: asyncio.Task) -> None:
        """Handle exceptions from fire-and-forget tasks."""
        try:
            task.result()  # This will raise if task failed
        except asyncio.CancelledError:
            pass  # Expected during shutdown
        except Exception as e:
            self._log_error(f"Unhandled exception in background task: {e}")
            import traceback
            traceback.print_exc()

    # ─────────────────────────────────────────────────────────────
    # Logging Helpers (respects debug setting)
    # ─────────────────────────────────────────────────────────────
    
    def _log_debug(self, msg: str, to_console: bool = True) -> None:
        """Log debug message (only if debug enabled).

        Args:
            msg: Message to log
            to_console: If True and debug_console enabled, also send to Mainsail

        Behavior:
            debug: False   → No logging
            debug: True    → Journal only (systemd/journalctl)
            debug: console → Journal + Mainsail console
        """
        if not self.debug:
            return  # Debug disabled, no logging

        # Always log to journal when debug enabled
        _logger.info(f"[LUMEN] {msg}")

        # Additionally send to Mainsail console if debug: console
        if to_console and self.debug_console:
            task = asyncio.create_task(self._console_log(msg))
            task.add_done_callback(self._task_exception_handler)
    
    async def _console_log(self, msg: str) -> None:
        """Send message to Mainsail console via Klipper RESPOND."""
        if not self.klippy_ready:
            return
        try:
            klippy = self.server.lookup_component("klippy_apis")
            # Escape quotes in message
            safe_msg = msg.replace('"', "'")
            await klippy.run_gcode(f'RESPOND PREFIX="LUMEN" MSG="{safe_msg}"')
        except Exception:
            pass  # Silently fail if Klipper busy or not ready
    
    def _log_info(self, msg: str) -> None:
        """Log info message (always)."""
        _logger.info(f"[LUMEN] {msg}")
    
    def _log_warning(self, msg: str) -> None:
        """Log warning message (always)."""
        _logger.warning(f"[LUMEN] {msg}")
    
    def _log_error(self, msg: str) -> None:
        """Log error message (always)."""
        _logger.error(f"[LUMEN] {msg}")
    
    # ─────────────────────────────────────────────────────────────
    # Config Loading
    # ─────────────────────────────────────────────────────────────
    
    def _load_config(self) -> None:
        """Load and parse lumen.cfg with validation."""
        path = Path(self.config_path).expanduser()
        if not path.exists():
            self._log_warning(f"Config not found: {path}")
            return
        
        # Clear previous state for reload
        self.led_groups.clear()
        self.event_mappings.clear()
        self.effect_settings.clear()
        self.config_warnings.clear()
        
        try:
            with open(path, 'r') as f:
                lines = f.readlines()
            
            current_section = None
            current_section_line = 0
            current_data: Dict[str, str] = {}
            
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                if line.startswith('[') and line.endswith(']'):
                    if current_section:
                        self._process_section(current_section, current_data, current_section_line)
                    current_section = line[1:-1]
                    current_section_line = line_num
                    current_data = {}
                elif ':' in line and current_section:
                    key, value = line.split(':', 1)
                    # Strip inline comments (# ...)
                    if '#' in value:
                        value = value.split('#', 1)[0]
                    current_data[key.strip()] = value.strip()
            
            if current_section:
                self._process_section(current_section, current_data, current_section_line)
            
            # Validate all event mappings have valid colors
            self._validate_config()
            
            self._log_info(f"Loaded: {len(self.led_groups)} groups, {len(self.event_mappings)} events")
        except Exception as e:
            self._log_error(f"Config error: {e}")
    
    def _validate_config(self) -> None:
        """Validate configuration and collect warnings."""
        available_colors = list_colors()
        valid_effects = set(EFFECT_REGISTRY.keys())
        valid_events = {"idle", "heating", "printing", "cooldown", "error", "bored", "sleep"}

        # Effects that require addressable LEDs (not compatible with PWM driver)
        addressable_only_effects = {"disco", "thermal", "progress"}

        # Check event mappings
        for event_name, mappings in self.event_mappings.items():
            if event_name not in valid_events:
                self.config_warnings.append(f"Unknown event '{event_name}' (valid: {', '.join(valid_events)})")

            for mapping in mappings:
                effect = mapping.get("effect", "")
                color = mapping.get("color")
                group = mapping.get("group", "?")

                # Get group driver type
                group_config = self.led_groups.get(group, {})
                driver_type = group_config.get("driver", "klipper")

                # PWM groups use brightness values, not effect names
                if driver_type == "pwm":
                    if not self._is_pwm_value(effect):
                        self.config_warnings.append(
                            f"Group '{group}' on_{event_name}: invalid PWM value '{effect}' (valid: on, off, dim, or 0.0-1.0)"
                        )
                else:
                    # Validate effect name for addressable LED groups
                    if effect not in valid_effects:
                        self.config_warnings.append(
                            f"Group '{group}' on_{event_name}: unknown effect '{effect}' (valid: {', '.join(valid_effects)})"
                        )

                    # Warn if using addressable-only effects with PWM driver
                    if driver_type == "pwm" and effect in addressable_only_effects:
                        self.config_warnings.append(
                            f"Group '{group}' on_{event_name}: effect '{effect}' requires addressable LEDs (not compatible with PWM driver). Use 'solid', 'pulse', or 'heartbeat' instead."
                        )

                    # Validate color name (if specified)
                    if color and color.lower() not in available_colors:
                        self.config_warnings.append(
                            f"Group '{group}' on_{event_name}: unknown color '{color}' (check /server/lumen/colors for list)"
                        )

        # Check LED groups have required fields
        for group_name, group_config in self.led_groups.items():
            driver = group_config.get("driver", "klipper")
            if driver == "klipper" and not group_config.get("neopixel"):
                self.config_warnings.append(f"Group '{group_name}': missing 'neopixel' for klipper driver")
            elif driver == "pwm" and not group_config.get("pin_name"):
                self.config_warnings.append(f"Group '{group_name}': missing 'pin_name' for pwm driver")
    
    def _is_pwm_value(self, value: str) -> bool:
        """Check if value is a PWM brightness value (on, off, dim, or 0.0-1.0)."""
        if value.lower() in ("on", "off", "dim"):
            return True
        try:
            float(value)
            return True
        except ValueError:
            return False
    
    def _process_section(self, section: str, data: Dict[str, str], line_num: int = 0) -> None:
        """Process a config section."""
        try:
            parts = section.split(None, 1)
            section_type = parts[0]
            section_name = parts[1] if len(parts) > 1 else None
            
            if section_type == "lumen_settings":
                self.temp_floor = float(data.get("temp_floor", self.temp_floor))
                self.bored_timeout = float(data.get("bored_timeout", self.bored_timeout))
                self.sleep_timeout = float(data.get("sleep_timeout", self.sleep_timeout))
                self.max_brightness = float(data.get("max_brightness", self.max_brightness))
                self.update_rate = float(data.get("update_rate", self.update_rate))
                self.update_rate_printing = float(data.get("update_rate_printing", self.update_rate_printing))
                self.gpio_fps = int(data.get("gpio_fps", self.gpio_fps))
                # Bed dimensions for KITT tracking
                self.bed_x_min = float(data.get("bed_x_min", self.bed_x_min))
                self.bed_x_max = float(data.get("bed_x_max", self.bed_x_max))
                self.bed_y_min = float(data.get("bed_y_min", self.bed_y_min))
                self.bed_y_max = float(data.get("bed_y_max", self.bed_y_max))
            
            elif section_type == "lumen_effect" and section_name:
                self.effect_settings[section_name] = data.copy()
            
            elif section_type == "lumen_group" and section_name:
                self.led_groups[section_name] = {
                    "driver": data.get("driver", "klipper"),
                    "neopixel": data.get("neopixel"),
                    "gpio_pin": int(data.get("gpio_pin", 18)) if "gpio_pin" in data else None,
                    "proxy_host": data.get("proxy_host", "127.0.0.1"),
                    "proxy_port": int(data.get("proxy_port", 3769)),
                    "color_order": data.get("color_order", "GRB"),
                    "index_start": int(data.get("index_start", 1)),
                    "index_end": int(data.get("index_end", 1)),
                    "pin_name": data.get("pin_name"),
                    "scale": float(data.get("scale", 10.0)),
                    "direction": data.get("direction", "standard").strip().lower(),
                }
                
                # Extract event mappings (on_idle, on_heating, etc.)
                for key, value in data.items():
                    if key.startswith("on_"):
                        event_name = key[3:]
                        parsed = self._parse_effect_color(value)
                        if event_name not in self.event_mappings:
                            self.event_mappings[event_name] = []
                        # Store full parsed dict plus group name
                        mapping = {"group": section_name, **parsed}
                        self.event_mappings[event_name].append(mapping)
        except Exception as e:
            loc = f" (line {line_num})" if line_num else ""
            self._log_error(f"Error in section [{section}]{loc}: {e}")
    
    def _parse_effect_color(self, value: str) -> Dict[str, Any]:
        """Parse effect specification with optional inline parameters.

        Formats:
            effect                           → basic effect
            effect color                     → effect with color
            effect group_num                 → multi-group effect (chase 1, chase 2, etc.)
            thermal [source] start end [curve]  → thermal with params
            progress start end [curve]       → progress with params
            comet color                      → comet with color
            kitt                             → kitt scanner

        Returns dict with: effect, color, start_color, end_color, gradient_curve, temp_source, group_num
        """
        parts = value.strip().split()
        result: Dict[str, Any] = {"effect": parts[0], "color": None, "group_num": None}

        # Check for multi-group numbering (chase 1, chase 2, etc.)
        if len(parts) >= 2 and parts[1].isdigit():
            result["group_num"] = int(parts[1])
            # Remove group number from parts for further parsing
            parts = [parts[0]] + parts[2:]

        if parts[0] == "thermal":
            # thermal [temp_source] [start_color] [end_color] [gradient_curve]
            idx = 1
            # Check if first param is a temp source
            if len(parts) > idx and parts[idx] in ("extruder", "bed", "chamber"):
                result["temp_source"] = parts[idx]
                idx += 1
            # Next two are colors
            if len(parts) > idx:
                result["start_color"] = parts[idx]
                idx += 1
            if len(parts) > idx:
                result["end_color"] = parts[idx]
                idx += 1
            # Optional gradient curve
            if len(parts) > idx:
                try:
                    result["gradient_curve"] = float(parts[idx])
                except ValueError:
                    pass
        
        elif parts[0] == "progress":
            # progress [start_color] [end_color] [gradient_curve]
            if len(parts) > 1:
                result["start_color"] = parts[1]
            if len(parts) > 2:
                result["end_color"] = parts[2]
            if len(parts) > 3:
                try:
                    result["gradient_curve"] = float(parts[3])
                except ValueError:
                    pass

        elif parts[0] in ("comet", "kitt") and len(parts) >= 2:
            # comet/kitt with color: comet blue, kitt cobalt
            result["color"] = parts[1]

        elif len(parts) >= 2:
            # Standard: effect color (or effect:color)
            if ':' in value:
                effect, color = value.split(':', 1)
                result["effect"] = effect.strip()
                result["color"] = color.strip()
            else:
                result["color"] = parts[1]
        
        return result
    
    def _create_drivers(self) -> None:
        """Create LED drivers for each group."""
        self.drivers.clear()
        for name, config in self.led_groups.items():
            driver = create_driver(name, config, self.server)
            if driver:
                self.drivers[name] = driver
                self._log_debug(f"Created driver for group '{name}': {config.get('driver', 'klipper')}")
    
    # ─────────────────────────────────────────────────────────────
    # Event Handlers
    # ─────────────────────────────────────────────────────────────
    
    async def _on_klippy_ready(self) -> None:
        self.klippy_ready = True
        self._log_info("Klippy ready")
        try:
            klippy_apis = self.server.lookup_component("klippy_apis")
            
            # Subscribe to status updates
            await klippy_apis.subscribe_objects({
                "webhooks": ["state", "state_message"],
                "print_stats": ["state", "filename", "info"],
                "display_status": ["progress", "message"],
                "heater_bed": ["temperature", "target"],
                "extruder": ["temperature", "target"],
                "idle_timeout": ["state"],
                "toolhead": ["position"],
            })
            
            # Query current state (subscription only gives deltas)
            result = await klippy_apis.query_objects({
                "webhooks": ["state"],
                "print_stats": ["state", "filename"],
                "display_status": ["progress"],
                "heater_bed": ["temperature", "target"],
                "extruder": ["temperature", "target"],
                "idle_timeout": ["state"],
                "toolhead": ["position"],
            })
            if result:
                self.printer_state.update_from_status(result)
                self._log_debug(f"Initial state: print={self.printer_state.print_state}, bed_target={self.printer_state.bed_target}")
            
            # Detect current event from queried state
            event = self.state_detector.update(self.printer_state)
            if event:
                await self._apply_event(event)
            else:
                await self._apply_event(PrinterEvent.IDLE)
                
        except Exception as e:
            self._log_error(f"Subscribe error: {e}")
    
    async def _on_klippy_shutdown(self) -> None:
        self.klippy_ready = False
        self._animation_running = False
        self._log_debug("Klippy shutdown")
    
    async def _on_klippy_disconnected(self) -> None:
        self.klippy_ready = False
        self._animation_running = False
        self._log_debug("Klippy disconnected")

    async def _on_server_shutdown(self) -> None:
        """Clean shutdown: stop animation loop and turn off LEDs."""
        self._log_info("Moonraker shutdown - cleaning up LUMEN")

        # Stop animation loop
        self._animation_running = False
        if self._animation_task:
            self._animation_task.cancel()
            try:
                await self._animation_task
            except asyncio.CancelledError:
                pass

        # Turn off all LEDs
        for name, driver in self.drivers.items():
            try:
                await driver.set_off()
                self._log_debug(f"Turned off LEDs for group: {name}")
            except Exception as e:
                self._log_error(f"Failed to turn off {name}: {e}")

    async def _on_status_update(self, status: Dict[str, Any]) -> None:
        self.printer_state.update_from_status(status)
        new_event = self.state_detector.update(self.printer_state)
        if new_event:
            task = asyncio.create_task(self._apply_event(new_event))
            task.add_done_callback(self._task_exception_handler)
    
    def _on_event_change(self, event: PrinterEvent) -> None:
        """Called when printer event changes."""
        self._log_debug(f"Event: {event.value}")
    
    # ─────────────────────────────────────────────────────────────
    # Effect Application
    # ─────────────────────────────────────────────────────────────
    
    async def _apply_event(self, event: PrinterEvent) -> None:
        """Apply LED effects for an event."""
        event_name = event.value
        if event_name not in self.event_mappings:
            self._log_debug(f"No mappings for event: {event_name}")
            return
        
        self._log_debug(f"Applying event: {event_name} to {len(self.event_mappings[event_name])} groups")
        
        for mapping in self.event_mappings[event_name]:
            group_name = mapping["group"]
            
            driver = self.drivers.get(group_name)
            if not driver:
                self._log_debug(f"No driver for group: {group_name}")
                continue
            
            await self._apply_effect(group_name, driver, mapping)

        await self._ensure_animation_loop()
    
    async def _apply_effect(self, group_name: str, driver: LEDDriver, mapping: Dict[str, Any]) -> None:
        """Apply effect to a driver.
        
        Args:
            group_name: Name of the LED group
            driver: LED driver instance
            mapping: Parsed effect mapping with inline params
        """
        effect = mapping["effect"]
        color_name = mapping.get("color")
        
        # Get base color
        if color_name:
            base_r, base_g, base_b = get_color(color_name)
        else:
            base_r, base_g, base_b = (1.0, 1.0, 1.0)
        
        r = base_r * self.max_brightness
        g = base_g * self.max_brightness
        b = base_b * self.max_brightness
        
        # Get effect params from [lumen_effect] section (defaults)
        params = self.effect_settings.get(effect, {})
        speed = float(params.get("speed", 1.0))
        min_bright = float(params.get("min_brightness", 0.2))
        max_bright = float(params.get("max_brightness", 0.8))
        min_sparkle = int(params.get("min_sparkle", 1))
        max_sparkle = int(params.get("max_sparkle", 6))

        # Thermal/Progress fill params - inline overrides [lumen_effect] defaults
        start_color_name = mapping.get("start_color") or params.get("start_color", "steel")
        end_color_name = mapping.get("end_color") or params.get("end_color", "matrix")
        gradient_curve = mapping.get("gradient_curve") or float(params.get("gradient_curve", 2.0))
        temp_source = mapping.get("temp_source") or params.get("temp_source", "extruder")

        # Rainbow params
        rainbow_spread = float(params.get("rainbow_spread", 1.0))

        # Fire params
        fire_cooling = float(params.get("fire_cooling", 0.3))

        # Comet params
        comet_tail_length = int(params.get("comet_tail_length", 10))
        comet_fade_rate = float(params.get("comet_fade_rate", 0.5))

        # Chase params
        chase_color_1_name = params.get("chase_color_1", "red")
        chase_color_2_name = params.get("chase_color_2", "blue")
        chase_color_1 = get_color(chase_color_1_name)
        chase_color_2 = get_color(chase_color_2_name)
        chase_size = int(params.get("chase_size", 5))
        chase_offset_base = float(params.get("chase_offset_base", 0.5))
        chase_offset_variation = float(params.get("chase_offset_variation", 0.1))

        # KITT params
        kitt_eye_size = int(params.get("kitt_eye_size", 3))
        kitt_tail_length = int(params.get("kitt_tail_length", 8))
        kitt_tracking_axis = params.get("kitt_tracking_axis", "none").lower()
        
        # Get actual RGB for start/end colors
        start_color = get_color(start_color_name)
        end_color = get_color(end_color_name)
        # Apply brightness cap
        start_color = (start_color[0] * self.max_brightness, 
                       start_color[1] * self.max_brightness, 
                       start_color[2] * self.max_brightness)
        end_color = (end_color[0] * self.max_brightness, 
                     end_color[1] * self.max_brightness, 
                     end_color[2] * self.max_brightness)
        
        # Apply immediate effects FIRST (before updating state)
        # This ensures the driver shows the correct state immediately
        if effect == "off":
            await driver.set_off()
        elif effect == "solid":
            await driver.set_color(r, g, b)
        elif effect in ("pulse", "heartbeat", "disco"):
            await driver.set_color(r, g, b)
        else:
            await driver.set_color(r, g, b)

        # Update effect state AFTER applying immediate effect
        # This prevents race condition with animation loop
        state = self.effect_states.get(group_name)
        if state:
            # Clear old cached effect instance if effect type changed
            old_effect = state.effect
            if old_effect != effect:
                old_cache_key = f"{group_name}:{old_effect}"
                self.effect_instances.pop(old_cache_key, None)

            state.effect = effect
            state.base_color = (r, g, b)
            state.color = (r, g, b)
            state.start_time = time.time()
            state.last_update = 0.0
            state.speed = speed
            state.min_brightness = min_bright
            state.max_brightness = max_bright
            state.min_sparkle = min_sparkle
            state.max_sparkle = max_sparkle
            # Thermal/Progress
            state.start_color = start_color
            state.end_color = end_color
            state.gradient_curve = float(gradient_curve)
            state.temp_source = temp_source
            # Rainbow
            state.rainbow_spread = rainbow_spread
            # Fire
            state.fire_cooling = fire_cooling
            # Comet
            state.comet_tail_length = comet_tail_length
            state.comet_fade_rate = comet_fade_rate
            # Chase
            state.chase_color_1 = chase_color_1
            state.chase_color_2 = chase_color_2
            state.chase_size = chase_size
            state.chase_offset_base = chase_offset_base
            state.chase_offset_variation = chase_offset_variation
            # KITT
            state.kitt_eye_size = kitt_eye_size
            state.kitt_tail_length = kitt_tail_length
            state.kitt_tracking_axis = kitt_tracking_axis
            # Direction (default to 'standard' if not set)
            group_cfg = self.led_groups.get(group_name, {})
            state.direction = group_cfg.get("direction", "standard")
    
    # ─────────────────────────────────────────────────────────────
    # Animation Loop
    # ─────────────────────────────────────────────────────────────
    
    async def _ensure_animation_loop(self) -> None:
        """Start/stop animation loop based on active effects."""
        # Check if any effect needs animation (not "off" or "solid")
        static_effects = {"off", "solid"}
        has_animated = any(s.effect not in static_effects for s in self.effect_states.values())

        if has_animated and not self._animation_running:
            # Cancel any existing task before starting new one
            if self._animation_task and not self._animation_task.done():
                self._animation_task.cancel()
                try:
                    await self._animation_task
                except asyncio.CancelledError:
                    pass

            self._animation_running = True
            self._animation_task = asyncio.create_task(self._animation_loop())
        elif not has_animated and self._animation_running:
            self._animation_running = False
            if self._animation_task:
                self._animation_task.cancel()
                try:
                    await self._animation_task
                except asyncio.CancelledError:
                    pass
    
    async def _animation_loop(self) -> None:
        """Background loop for animated effects."""
        # Import driver types for isinstance checks
        from .lumen_lib.drivers import GPIODriver, ProxyDriver

        try:
            while self._animation_running:
                now = time.time()
                is_printing = self.printer_state.print_state == "printing"

                # Collect intervals from all active animated groups
                intervals = []

                for group_name, state in self.effect_states.items():
                    # Check if effect exists in registry
                    effect_class = EFFECT_REGISTRY.get(state.effect)
                    if not effect_class:
                        continue

                    driver = self.drivers.get(group_name)
                    if not driver:
                        continue

                    # Determine interval for this driver type
                    # GPIO/Proxy drivers can use high FPS, Klipper driver is G-code limited
                    if isinstance(driver, (GPIODriver, ProxyDriver)):
                        # High FPS for GPIO/Proxy drivers
                        driver_interval = 1.0 / self.gpio_fps
                    else:
                        # Klipper driver limited by G-code queue
                        driver_interval = self.update_rate_printing if is_printing else self.update_rate

                    intervals.append(driver_interval)

                    try:
                        # Get cached effect instance (one per group+effect combo)
                        # IMPORTANT: Cache key must be unique per group to prevent state corruption
                        cache_key = f"{group_name}:{state.effect}"
                        if cache_key not in self.effect_instances:
                            self.effect_instances[cache_key] = effect_class()
                        effect = self.effect_instances[cache_key]

                        led_count = driver.led_count if hasattr(driver, 'led_count') else 1

                        # Build state data for effects that need it
                        state_data = None
                        if effect.requires_state_data:
                            state_data = {
                                # Temps for thermal effect
                                'bed_temp': self.printer_state.bed_temp,
                                'bed_target': self.printer_state.bed_target,
                                'extruder_temp': self.printer_state.extruder_temp,
                                'extruder_target': self.printer_state.extruder_target,
                                'chamber_temp': 0.0,  # TODO: Add chamber tracking
                                'chamber_target': 0.0,
                                'temp_floor': self.temp_floor,
                                # Progress for progress effect
                                'print_progress': self.printer_state.progress,
                                # Toolhead position for KITT tracking
                                'toolhead_pos_x': self.printer_state.position_x,
                                'toolhead_pos_y': self.printer_state.position_y,
                                'toolhead_pos_z': self.printer_state.position_z,
                                # Bed dimensions
                                'bed_x_min': self.bed_x_min,
                                'bed_x_max': self.bed_x_max,
                                'bed_y_min': self.bed_y_min,
                                'bed_y_max': self.bed_y_max,
                            }

                            # Throttle thermal debug logging
                            if state.effect == "thermal":
                                current_temp = state_data.get(f'{state.temp_source}_temp', 0.0)
                                target_temp = state_data.get(f'{state.temp_source}_target', 0.0)

                                should_log = False
                                if group_name in self._last_thermal_log:
                                    last_time, last_current, last_target = self._last_thermal_log[group_name]
                                    temp_changed = abs(current_temp - last_current) >= 1.0 or abs(target_temp - last_target) >= 1.0
                                    time_elapsed = now - last_time >= 10.0
                                    should_log = temp_changed or time_elapsed
                                else:
                                    should_log = True

                                if should_log:
                                    self._last_thermal_log[group_name] = (now, current_temp, target_temp)
                                    self._log_debug(f"Thermal {group_name}: source={state.temp_source}, current={current_temp:.1f}, target={target_temp:.1f}, floor={self.temp_floor}")

                        # Calculate effect colors
                        colors, needs_update = effect.calculate(state, now, led_count, state_data)

                        if not needs_update:
                            continue

                        # Update last_update time for effects that use it
                        if state.effect in ("disco",):
                            state.last_update = now

                        # Apply colors to driver
                        if len(colors) == 1:
                            # Single color effect (pulse, heartbeat, solid, off)
                            color = colors[0]
                            if color is None:
                                await driver.set_off()
                            else:
                                r, g, b = color
                                await driver.set_color(r, g, b)
                        else:
                            # Multi-LED effect (disco, thermal, progress)
                            if hasattr(driver, 'set_leds'):
                                await driver.set_leds(colors)

                    except Exception as e:
                        self._log_error(f"Animation error in {group_name}: {e}")

                # Use the smallest interval (highest update rate needed)
                # This ensures fast drivers get their updates while slow drivers still work
                interval = min(intervals) if intervals else self.update_rate
                # Clamp to minimum 1ms (1000Hz max) to prevent busy-looping
                interval = max(interval, 0.001)
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            self._log_debug("Animation loop cancelled")
    
    # ─────────────────────────────────────────────────────────────
    # API Endpoints
    # ─────────────────────────────────────────────────────────────
    
    async def _handle_status(self, web_request: WebRequest) -> Dict[str, Any]:
        return {
            "version": __version__,
            "klippy_ready": self.klippy_ready,
            "detector": self.state_detector.status(),
            "printer": {
                "klipper_state": self.printer_state.klipper_state,
                "print_state": self.printer_state.print_state,
                "progress": self.printer_state.progress,
                "bed_temp": self.printer_state.bed_temp,
                "bed_target": self.printer_state.bed_target,
                "extruder_temp": self.printer_state.extruder_temp,
                "extruder_target": self.printer_state.extruder_target,
                "position": {
                    "x": round(self.printer_state.position_x, 2),
                    "y": round(self.printer_state.position_y, 2),
                    "z": round(self.printer_state.position_z, 2),
                },
            },
            "config": {
                "max_brightness": self.max_brightness,
                "update_rate": self.update_rate,
                "update_rate_printing": self.update_rate_printing,
                "debug": "console" if self.debug_console else self.debug,
            },
            "animation": {
                "running": self._animation_running,
                "effects": {n: s.effect for n, s in self.effect_states.items()},
            },
            "led_groups": list(self.led_groups.keys()),
            "warnings": self.config_warnings,
        }
    
    async def _handle_colors(self, web_request: WebRequest) -> Dict[str, Any]:
        return {"colors": list_colors()}
    
    async def _handle_test_event(self, web_request: WebRequest) -> Dict[str, Any]:
        event_name = web_request.get_str("event", "idle")
        try:
            event = PrinterEvent(event_name)
            self.state_detector.force_event(event)
            await self._apply_event(event)
            return {"result": "ok", "event": event.value}
        except ValueError:
            return {"result": "error", "message": f"Unknown event: {event_name}"}
    
    async def _handle_reload(self, web_request: WebRequest) -> Dict[str, Any]:
        """Reload lumen.cfg without restarting Moonraker."""
        self._log_info("Reloading configuration...")
        
        # Stop animation loop
        if self._animation_running:
            self._animation_running = False
            if self._animation_task:
                self._animation_task.cancel()
                try:
                    await self._animation_task
                except asyncio.CancelledError:
                    pass
        
        # Reload config
        self._load_config()
        self._create_drivers()

        # Clear caches to prevent memory leaks
        self.effect_instances.clear()
        self._last_thermal_log.clear()

        # Recreate effect states for new drivers
        self.effect_states.clear()
        for name in self.drivers:
            self.effect_states[name] = EffectState()
        
        # Re-apply current event (this also restarts animation loop)
        current_event = self.state_detector.current_event
        await self._apply_event(current_event)
        
        result = {
            "result": "ok",
            "groups": list(self.led_groups.keys()),
            "events": list(self.event_mappings.keys()),
            "current_event": current_event.value,
        }
        
        if self.config_warnings:
            result["warnings"] = self.config_warnings
        
        return result


def load_component(config: ConfigHelper) -> Lumen:
    return Lumen(config)
