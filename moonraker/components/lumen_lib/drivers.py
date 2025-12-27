"""
LUMEN Drivers - LED hardware drivers

KlipperDriver: SET_LED for MCU-attached neopixels
PWMDriver: SET_PIN for non-addressable strips
GPIODriver: rpi_ws281x for Pi GPIO-attached neopixels
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from .colors import RGB
import urllib.request
import urllib.error
import json

_logger = logging.getLogger(__name__)

# Timeout for gcode commands (seconds)
GCODE_TIMEOUT = 2.0

# Try to import rpi_ws281x (only available on Raspberry Pi)
try:
    from rpi_ws281x import PixelStrip, Color
    RPI_WS281X_AVAILABLE = True
except ImportError:
    RPI_WS281X_AVAILABLE = False
    PixelStrip = None
    Color = None

# Shared pixel strips by GPIO pin (multiple groups can share one strip)
# Thread-safe global state with locks (similar to ws281x_proxy.py)
from threading import Lock
_gpio_strips: Dict[int, "PixelStrip"] = {}
_gpio_strip_sizes: Dict[int, int] = {}
_gpio_strip_locks: Dict[int, Lock] = {}
_gpio_strip_locks_lock = Lock()  # Protect lock creation


class LEDDriver:
    """Base class for LED drivers."""
    
    def __init__(self, name: str, config: Dict[str, Any], server: Any):
        self.name = name
        self.config = config
        self.server = server
        self.led_count = 1
    
    async def set_color(self, r: float, g: float, b: float) -> None:
        """Set all LEDs to a solid color."""
        raise NotImplementedError
    
    async def set_off(self) -> None:
        """Turn off all LEDs."""
        await self.set_color(0.0, 0.0, 0.0)


class KlipperDriver(LEDDriver):
    """
    Driver for Klipper MCU-attached neopixels.
    Uses SET_LED gcode command via klippy_apis.
    """
    
    def __init__(self, name: str, config: Dict[str, Any], server: Any):
        super().__init__(name, config, server)
        self.neopixel = config.get("neopixel", name)
        self.index_start = config.get("index_start", 1)
        self.index_end = config.get("index_end", self.index_start)
        self.led_count = self.index_end - self.index_start + 1
    
    async def set_color(self, r: float, g: float, b: float) -> None:
        """Set LEDs in this group's index range to a solid color."""
        try:
            klippy_apis = self.server.lookup_component("klippy_apis")

            # Set all LEDs except the last with TRANSMIT=0
            if self.led_count > 1:
                for i in range(self.index_start, self.index_end):  # This excludes index_end
                    gcode = f"SET_LED LED={self.neopixel} RED={r:.3f} GREEN={g:.3f} BLUE={b:.3f} INDEX={i} TRANSMIT=0"
                    await asyncio.wait_for(klippy_apis.run_gcode(gcode), timeout=GCODE_TIMEOUT)

            # Set the last LED with TRANSMIT=1 to flush all changes
            gcode = f"SET_LED LED={self.neopixel} RED={r:.3f} GREEN={g:.3f} BLUE={b:.3f} INDEX={self.index_end} TRANSMIT=1"
            await asyncio.wait_for(klippy_apis.run_gcode(gcode), timeout=GCODE_TIMEOUT)
        except asyncio.TimeoutError:
            _logger.warning(f"[LUMEN] {self.name} SET_LED timeout (Klipper busy)")
        except Exception as e:
            _logger.error(f"[LUMEN] {self.name} SET_LED failed: {e}")
    
    async def set_leds(self, colors: List[Optional[RGB]]) -> None:
        """Set individual LEDs to specific colors. None = off."""
        try:
            klippy_apis = self.server.lookup_component("klippy_apis")
            
            for i, color in enumerate(colors):
                led_index = self.index_start + i
                if led_index > self.index_end:
                    break
                
                is_last = (i == len(colors) - 1) or (led_index == self.index_end)
                transmit = 1 if is_last else 0
                
                if color is None:
                    r, g, b = 0.0, 0.0, 0.0
                else:
                    r, g, b = color
                
                gcode = f"SET_LED LED={self.neopixel} RED={r:.3f} GREEN={g:.3f} BLUE={b:.3f} INDEX={led_index} TRANSMIT={transmit}"
                await asyncio.wait_for(klippy_apis.run_gcode(gcode), timeout=GCODE_TIMEOUT)
        except asyncio.TimeoutError:
            _logger.warning(f"[LUMEN] {self.name} SET_LEDS timeout (Klipper busy)")
        except Exception as e:
            _logger.error(f"[LUMEN] {self.name} SET_LEDS failed: {e}")


class PWMDriver(LEDDriver):
    """
    Driver for simple PWM LED strips (brightness only, no color).
    Uses SET_PIN gcode command via klippy_apis.
    """
    
    def __init__(self, name: str, config: Dict[str, Any], server: Any):
        super().__init__(name, config, server)
        self.pin_name = config.get("pin_name", name)
        self.scale = config.get("scale", 1.0)
    
    async def set_color(self, r: float, g: float, b: float) -> None:
        """Set brightness based on color intensity."""
        brightness = max(r, g, b)
        await self.set_brightness(brightness)
    
    async def set_brightness(self, value: float) -> None:
        """Set PWM brightness (0.0-1.0)."""
        try:
            klippy_apis = self.server.lookup_component("klippy_apis")
            scaled = value * self.scale
            gcode = f"SET_PIN PIN={self.pin_name} VALUE={scaled:.2f}"
            await asyncio.wait_for(klippy_apis.run_gcode(gcode), timeout=GCODE_TIMEOUT)
        except asyncio.TimeoutError:
            _logger.warning(f"[LUMEN] {self.name} SET_PIN timeout (Klipper busy)")
        except Exception as e:
            _logger.error(f"[LUMEN] {self.name} SET_PIN failed: {e}")
    
    async def set_off(self) -> None:
        await self.set_brightness(0.0)


class GPIODriver(LEDDriver):
    """
    Driver for Raspberry Pi GPIO-attached neopixels.
    Uses rpi_ws281x library for direct hardware control.
    
    Multiple groups can share the same GPIO pin with different index ranges.
    """
    
    # LED strip configuration (WS2812B defaults)
    LED_FREQ_HZ = 800000      # LED signal frequency in hertz
    LED_DMA = 10              # DMA channel for generating signal
    LED_INVERT = False        # True to invert the signal
    LED_BRIGHTNESS = 255      # Global brightness (0-255)
    LED_CHANNEL = 0           # GPIO 18 uses PWM channel 0
    
    def __init__(self, name: str, config: Dict[str, Any], server: Any):
        super().__init__(name, config, server)
        self.gpio_pin = int(config.get("gpio_pin", 18))
        self.index_start = config.get("index_start", 1)
        self.index_end = config.get("index_end", self.index_start)
        self.led_count = self.index_end - self.index_start + 1
        self.strip: Optional["PixelStrip"] = None
        
        if not RPI_WS281X_AVAILABLE:
            _logger.error(f"[LUMEN] {name}: rpi_ws281x not available (install with: pip install rpi_ws281x)")
            return
        
        # Get or create shared strip for this GPIO pin
        self._init_strip()
    
    def _init_strip(self) -> None:
        """Initialize or get shared PixelStrip for this GPIO pin."""
        global _gpio_strips, _gpio_strip_sizes, _gpio_strip_locks, _gpio_strip_locks_lock

        # Ensure per-pin lock exists (thread-safe lock creation)
        with _gpio_strip_locks_lock:
            if self.gpio_pin not in _gpio_strip_locks:
                _gpio_strip_locks[self.gpio_pin] = Lock()

        # All strip operations protected by pin-specific lock
        with _gpio_strip_locks[self.gpio_pin]:
            if self.gpio_pin in _gpio_strips:
                # Strip already exists - check if we need more LEDs
                current_size = _gpio_strip_sizes[self.gpio_pin]
                if self.index_end > current_size:
                    # Need to recreate strip with more LEDs
                    _logger.info(f"[LUMEN] Expanding GPIO {self.gpio_pin} strip from {current_size} to {self.index_end} LEDs")
                    old_strip = _gpio_strips[self.gpio_pin]

                    try:
                        # Create new strip with expanded size
                        new_strip = PixelStrip(
                            self.index_end,
                            self.gpio_pin,
                            self.LED_FREQ_HZ,
                            self.LED_DMA,
                            self.LED_INVERT,
                            self.LED_BRIGHTNESS,
                            self.LED_CHANNEL
                        )
                        new_strip.begin()

                        # Copy existing LED states from old strip
                        for i in range(current_size):
                            try:
                                color = old_strip.getPixelColor(i)
                                new_strip.setPixelColor(i, color)
                            except Exception as e:
                                # v1.4.0: Log exception for debugging
                                _logger.debug(f"[LUMEN] Failed to copy LED {i} state during strip expansion: {e}")

                        # Replace with new expanded strip
                        _gpio_strips[self.gpio_pin] = new_strip
                        _gpio_strip_sizes[self.gpio_pin] = self.index_end
                        self.strip = new_strip
                        _logger.info(f"[LUMEN] Successfully expanded GPIO {self.gpio_pin} strip to {self.index_end} LEDs")
                    except Exception as e:
                        _logger.error(f"[LUMEN] Failed to expand GPIO strip: {e}")
                        # Keep using old strip if expansion fails
                        self.strip = old_strip
                else:
                    self.strip = _gpio_strips[self.gpio_pin]
            else:
                # Create new strip
                total_leds = self.index_end  # index_end is the highest LED we need
                _logger.info(f"[LUMEN] Creating GPIO {self.gpio_pin} strip with {total_leds} LEDs")

                try:
                    self.strip = PixelStrip(
                        total_leds,
                        self.gpio_pin,
                        self.LED_FREQ_HZ,
                        self.LED_DMA,
                        self.LED_INVERT,
                        self.LED_BRIGHTNESS,
                        self.LED_CHANNEL
                    )
                    self.strip.begin()
                    _gpio_strips[self.gpio_pin] = self.strip
                    _gpio_strip_sizes[self.gpio_pin] = total_leds
                except Exception as e:
                    _logger.error(f"[LUMEN] Failed to initialize GPIO strip: {e}")
                self.strip = None
    
    def _rgb_to_color(self, r: float, g: float, b: float) -> int:
        """Convert 0.0-1.0 RGB to rpi_ws281x Color."""
        return Color(int(r * 255), int(g * 255), int(b * 255))
    
    async def set_color(self, r: float, g: float, b: float) -> None:
        """Set all LEDs in this group's range to a solid color."""
        if not self.strip:
            return
        
        color = self._rgb_to_color(r, g, b)
        for i in range(self.index_start - 1, self.index_end):  # Convert to 0-indexed
            self.strip.setPixelColor(i, color)
        self.strip.show()
    
    async def set_leds(self, colors: List[Optional[RGB]]) -> None:
        """Set individual LEDs to specific colors. None = off."""
        if not self.strip:
            return
        
        for i, color in enumerate(colors):
            led_index = self.index_start - 1 + i  # Convert to 0-indexed
            if led_index >= self.index_end:
                break
            
            if color is None:
                self.strip.setPixelColor(led_index, Color(0, 0, 0))
            else:
                r, g, b = color
                self.strip.setPixelColor(led_index, self._rgb_to_color(r, g, b))
        
        self.strip.show()
    
    async def set_off(self) -> None:
        """Turn off all LEDs in this group's range."""
        if not self.strip:
            return
        
        for i in range(self.index_start - 1, self.index_end):
            self.strip.setPixelColor(i, Color(0, 0, 0))
        self.strip.show()




# Per-GPIO request queues to serialize updates without blocking animation loop
_gpio_request_queues: Dict[int, asyncio.Queue] = {}
_gpio_queue_workers: Dict[int, asyncio.Task] = {}


class ProxyDriver(LEDDriver):
    """
    Driver communicating with a helper ws281x proxy server running as root.
    The proxy avoids needing Moonraker to run with raw IO privileges.

    v1.4.10: Uses per-GPIO queue to serialize requests without blocking animation loop.
    """
    def __init__(self, name: str, config: Dict[str, Any], server: Any):
        super().__init__(name, config, server)
        self.gpio_pin = int(config.get("gpio_pin", 18))
        self.index_start = int(config.get("index_start", 1))
        self.index_end = int(config.get("index_end", self.index_start))
        self.led_count = self.index_end - self.index_start + 1
        self.proxy_host = config.get("proxy_host", "127.0.0.1")
        self.proxy_port = int(config.get("proxy_port", 3769))
        # Color order for WS281x strips (most common is GRB for WS2812B)
        self.color_order = config.get("color_order", "GRB").upper().strip()

        # v1.4.10: Ensure queue worker exists for this GPIO pin
        self._ensure_queue_worker()

    def _ensure_queue_worker(self) -> None:
        """Ensure background queue worker exists for this GPIO pin."""
        global _gpio_request_queues, _gpio_queue_workers

        if self.gpio_pin not in _gpio_request_queues:
            _gpio_request_queues[self.gpio_pin] = asyncio.Queue()
            # Don't start worker here - will be started on first use when event loop exists
            _gpio_queue_workers[self.gpio_pin] = None

    async def _start_queue_worker(self) -> None:
        """Start queue worker if not already running."""
        global _gpio_queue_workers

        if _gpio_queue_workers[self.gpio_pin] is None or _gpio_queue_workers[self.gpio_pin].done():
            _gpio_queue_workers[self.gpio_pin] = asyncio.create_task(self._queue_worker())

    async def _queue_worker(self) -> None:
        """Background worker that processes queued requests serially."""
        import time
        queue = _gpio_request_queues[self.gpio_pin]

        while True:
            try:
                url, data = await queue.get()

                def _send():
                    try:
                        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
                        with urllib.request.urlopen(req, timeout=0.1) as resp:
                            pass
                    except Exception:
                        pass  # Silent failure - proxy updates are best-effort

                # Process request (blocking this worker, but not the animation loop)
                await asyncio.to_thread(_send)
                queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                _logger.error(f"[LUMEN] Queue worker error on GPIO {self.gpio_pin}: {e}")

    def _proxy_url(self, path: str) -> str:
        return f"http://{self.proxy_host}:{self.proxy_port}{path}"

    async def _post(self, path: str, payload: Dict[str, Any]) -> None:
        """Queue HTTP POST to proxy (v1.4.11: non-blocking serialized queue)."""
        # Start worker if needed
        await self._start_queue_worker()

        url = self._proxy_url(path)
        data = json.dumps(payload).encode('utf-8')

        queue = _gpio_request_queues[self.gpio_pin]

        # v1.4.11: Queue all requests - proxy now uses locks to prevent thread interleaving
        # No frame dropping needed since threading race condition is fixed in proxy
        await queue.put((url, data))

    async def set_color(self, r: float, g: float, b: float) -> None:
        payload = {
            "gpio_pin": self.gpio_pin,
            "index_start": self.index_start,
            "index_end": self.index_end,
            "r": r,
            "g": g,
            "b": b,
            "color_order": self.color_order,
        }
        await self._post('/set_color', payload)  # Returns immediately now

    async def set_leds(self, colors: List[Optional[RGB]]) -> None:
        payload = {
            "gpio_pin": self.gpio_pin,
            "index_start": self.index_start,
            "colors": colors,
            "color_order": self.color_order,
        }
        await self._post('/set_leds', payload)  # Returns immediately now

    async def set_off(self) -> None:
        await self.set_color(0.0, 0.0, 0.0)

    async def set_batch(self, updates: List[Dict[str, Any]]) -> None:
        """
        v1.4.6: Batch multiple LED range updates into one atomic HTTP request.
        This prevents flickering when multiple groups share the same GPIO pin.

        Args:
            updates: List of update dicts, each containing either:
                - colors update: {index_start, colors, color_order}
                - solid color update: {index_start, index_end, r, g, b, color_order}
        """
        payload = {
            "gpio_pin": self.gpio_pin,
            "updates": updates,
        }
        await self._post('/set_batch', payload)


def create_driver(name: str, config: Dict[str, Any], server: Any) -> Optional[LEDDriver]:
    """Factory function to create the appropriate driver."""
    driver_type = config.get("driver", "klipper")
    
    if driver_type == "klipper":
        return KlipperDriver(name, config, server)
    elif driver_type == "pwm":
        return PWMDriver(name, config, server)
    elif driver_type == "gpio":
        if not RPI_WS281X_AVAILABLE:
            _logger.error(f"[LUMEN] GPIO driver requires rpi_ws281x (pip install rpi_ws281x)")
            return None
        return GPIODriver(name, config, server)
    elif driver_type == "proxy":
        return ProxyDriver(name, config, server)
    else:
        _logger.error(f"[LUMEN] Unknown driver type '{driver_type}' for {name}")
        return None
