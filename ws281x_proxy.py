#!/usr/bin/env python3
"""
Simple WS281x Proxy server.

Runs as root (or a user with access to /dev/mem) and exposes a minimal JSON HTTP
API on localhost for setting PixelStrip colors. LUMEN can communicate with this
service instead of linking rpi_ws281x into Moonraker's process.

Usage:
  sudo python3 ws281x_proxy.py --port 3769

Endpoints:
  POST /set_color  - payload: {gpio_pin, index_start, index_end, r, g, b, color_order}
  POST /set_leds   - payload: {gpio_pin, index_start, colors: [[r,g,b], ...], color_order}
  GET  /status     - returns active strips
"""

import argparse
import os
import sys
import json
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from threading import Lock, Thread
import time

from rpi_ws281x import PixelStrip, Color, ws
import traceback

# Systemd watchdog support (optional)
try:
    import systemd.daemon
    SYSTEMD_AVAILABLE = True
except ImportError:
    SYSTEMD_AVAILABLE = False

_logger = logging.getLogger(__name__)
_logging_handler = logging.StreamHandler()
_logging_handler.setFormatter(logging.Formatter('[WS281X_PROXY] %(message)s'))
_logger.addHandler(_logging_handler)

# v1.4.3: Quiet mode for high FPS operation (reduces CPU overhead from logging spam)
import os as _os_env
_QUIET_MODE = _os_env.getenv('WS281X_QUIET', '').lower() in ('1', 'true', 'yes')
_logger.setLevel(logging.WARNING if _QUIET_MODE else logging.INFO)

# Strip type mapping for color order
# rpi_ws281x uses these constants for different color orders
STRIP_TYPES = {
    'RGB': ws.WS2811_STRIP_RGB,
    'RBG': ws.WS2811_STRIP_RBG,
    'GRB': ws.WS2811_STRIP_GRB,
    'GBR': ws.WS2811_STRIP_GBR,
    'BRG': ws.WS2811_STRIP_BRG,
    'BGR': ws.WS2811_STRIP_BGR,
}
DEFAULT_STRIP_TYPE = ws.WS2811_STRIP_GRB  # Most common for WS2812B

# Shared strips by pin
_strips: Dict[int, PixelStrip] = {}
_strip_sizes: Dict[int, int] = {}
_strip_types: Dict[int, int] = {}  # Store strip_type per pin
_strip_errors: Dict[int, str] = {}
_strip_locks: Dict[int, Lock] = {}
_strip_locks_lock = Lock()  # Global lock to protect _strip_locks creation


def _get_strip(pin: int, total: int, strip_type: int = DEFAULT_STRIP_TYPE) -> Optional[PixelStrip]:
    """Get or create a PixelStrip for a pin with at least `total` LEDs.

    Args:
        pin: GPIO pin number
        total: Minimum number of LEDs needed
        strip_type: Color order constant (e.g., ws.WS2811_STRIP_GRB)
    """
    # Ensure a per-pin lock exists (thread-safe creation)
    global _strip_locks, _strip_locks_lock
    with _strip_locks_lock:
        if pin not in _strip_locks:
            _strip_locks[pin] = Lock()

    with _strip_locks[pin]:
        # Check if strip already exists
        if pin in _strips:
            cur = _strip_sizes[pin]
            cur_type = _strip_types.get(pin, DEFAULT_STRIP_TYPE)
            
            # Need to recreate if size increased OR strip_type changed
            if total > cur or strip_type != cur_type:
                reason = f"{cur} -> {total}" if total > cur else f"color_order changed"
                _logger.info(f"Recreating strip on GPIO {pin}: {reason}")
                try:
                    old = _strips[pin]
                    new_strip = PixelStrip(
                        max(total, cur), pin, 800000, 10, False, 255, 0, strip_type
                    )
                    new_strip.begin()
                    # copy old pixels if just expanding (not changing type)
                    if strip_type == cur_type:
                        try:
                            for i in range(cur):
                                try:
                                    c = old.getPixelColor(i)
                                    new_strip.setPixelColor(i, c)
                                except Exception:
                                    pass
                        except Exception:
                            pass
                    _strips[pin] = new_strip
                    _strip_sizes[pin] = max(total, cur)
                    _strip_types[pin] = strip_type
                    if pin in _strip_errors:
                        del _strip_errors[pin]
                    return new_strip
                except Exception as e:
                    _logger.exception(f"Failed to recreate PixelStrip on {pin}")
                    _strip_errors[pin] = traceback.format_exc()
                    return _strips[pin]
            return _strips[pin]

        # Strip doesn't exist - create it (inside the lock!)
        _logger.info(f"Creating PixelStrip on GPIO {pin} with {total} LEDs, strip_type={strip_type}")
        try:
            strip = PixelStrip(total, pin, 800000, 10, False, 255, 0, strip_type)
            strip.begin()
            _strips[pin] = strip
            _strip_sizes[pin] = total
            _strip_types[pin] = strip_type
            if pin in _strip_errors:
                del _strip_errors[pin]
            return strip
        except Exception as e:
            _logger.exception(f"Failed to init PixelStrip on {pin}")
            _strip_errors[pin] = traceback.format_exc()
            return None


def parse_lumen_cfg(path: str) -> Tuple[Dict[int, int], Dict[int, int]]:
    """Parse a lumen.cfg file and return mappings for proxy groups.
    
    Returns:
        Tuple of (gpio_pin -> max total LEDs, gpio_pin -> strip_type)
    
    Only groups with 'driver: proxy' are considered.
    """
    size_mapping: Dict[int, int] = {}
    type_mapping: Dict[int, int] = {}
    cur: Dict[str, str] = {}
    
    def process_group(group: Dict[str, str]):
        driver = group.get('driver')
        if driver and driver == 'proxy' and 'gpio_pin' in group:
            try:
                pin = int(group.get('gpio_pin'))
                end = group.get('index_end')
                start = group.get('index_start')
                if end is None and start is None:
                    return
                total = int(end) if end is not None else int(start)
                size_mapping[pin] = max(size_mapping.get(pin, 0), total)
                
                # Parse color_order if present
                color_order = group.get('color_order', 'GRB').upper().strip()
                if color_order in STRIP_TYPES:
                    type_mapping[pin] = STRIP_TYPES[color_order]
                else:
                    _logger.warning(f"Unknown color_order '{color_order}' for GPIO {pin}, using GRB")
                    type_mapping[pin] = DEFAULT_STRIP_TYPE
            except Exception:
                pass
    
    try:
        with open(path, 'r') as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith('#'):
                    continue
                if s.startswith('[') and s.endswith(']'):
                    # process previous
                    if cur:
                        process_group(cur)
                    cur = {}
                else:
                    if ':' in s:
                        k, v = s.split(':', 1)
                        v = v.split('#', 1)[0].strip()
                        cur[k.strip()] = v
            # end loop: process last
            if cur:
                process_group(cur)
    except FileNotFoundError:
        _logger.warning(f"lumen cfg not found: {path}")
    except Exception:
        _logger.exception(f"Failed to parse lumen cfg: {path}")
    return size_mapping, type_mapping


def get_strip_type_name(strip_type: int) -> str:
    """Get the name for a strip_type constant."""
    for name, val in STRIP_TYPES.items():
        if val == strip_type:
            return name
    return "GRB"


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, code: int, payload: Dict):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode())

    def do_GET(self):
        try:
            if not _QUIET_MODE:  # v1.4.3: Skip logging in quiet mode (60 FPS = lots of spam)
                _logger.info(f"HTTP GET {self.path} from {self.client_address}")
            if self.path == '/status':
                payload = {
                    'strips': {str(k): _strip_sizes[k] for k in _strip_sizes},
                    'strip_types': {str(k): get_strip_type_name(_strip_types.get(k, DEFAULT_STRIP_TYPE)) for k in _strip_sizes},
                    'errors': {str(k): _strip_errors[k] for k in _strip_errors}
                }
                self._send_json(200, payload)
            else:
                self._send_json(404, {'error': 'not found'})
        except Exception as e:
            _logger.exception('Unhandled exception in do_GET')
            self._send_json(500, {'error': 'internal', 'message': str(e)})

    def do_POST(self):
        try:
            if not _QUIET_MODE:  # v1.4.3: Skip logging in quiet mode (60 FPS = lots of spam)
                _logger.info(f"HTTP {self.command} {self.path} from {self.client_address}")
            length = int(self.headers.get('Content-Length', '0'))
            try:
                body = self.rfile.read(length)
                data = json.loads(body or b'{}')
                if not _QUIET_MODE:  # v1.4.3: Skip logging in quiet mode
                    _logger.info(f"Request JSON: {data}")
            except Exception as e:
                self._send_json(400, {'error': 'bad json', 'message': str(e)})
                return

            if self.path == '/set_color':
                gpio_pin = int(data.get('gpio_pin', 18))
                start = int(data.get('index_start', 1))
                end = int(data.get('index_end', start))
                r = float(data.get('r', 1.0))
                g = float(data.get('g', 1.0))
                b = float(data.get('b', 1.0))
                
                # Parse color_order if provided
                color_order = data.get('color_order', 'GRB').upper().strip()
                strip_type = STRIP_TYPES.get(color_order, DEFAULT_STRIP_TYPE)
                if color_order not in STRIP_TYPES:
                    _logger.warning(f"Unknown color_order '{color_order}', falling back to GRB. Valid options: {', '.join(STRIP_TYPES.keys())}")

                strip = _get_strip(gpio_pin, end, strip_type)
                if not strip:
                    self._send_json(500, {'error': 'strip init failed'})
                    return

                c = Color(int(r * 255), int(g * 255), int(b * 255))
                for i in range(start - 1, end):
                    strip.setPixelColor(i, c)
                strip.show()
                time.sleep(0.001)  # v1.4.11: 1ms delay for WS281x reset (requires >50μs between frames)
                if not _QUIET_MODE:  # v1.4.3: Skip logging in quiet mode
                    _logger.info(f"Applied set_color gpio={gpio_pin} start={start} end={end} color=({int(r*255)},{int(g*255)},{int(b*255)})")
                self._send_json(200, {'result': 'ok'})
                return

            if self.path == '/set_leds':
                gpio_pin = int(data.get('gpio_pin', 18))
                start = int(data.get('index_start', 1))
                colors: List = data.get('colors', [])
                end_needed = start - 1 + len(colors)
                
                # Parse color_order if provided
                color_order = data.get('color_order', 'GRB').upper().strip()
                strip_type = STRIP_TYPES.get(color_order, DEFAULT_STRIP_TYPE)
                if color_order not in STRIP_TYPES:
                    _logger.warning(f"Unknown color_order '{color_order}', falling back to GRB. Valid options: {', '.join(STRIP_TYPES.keys())}")

                strip = _get_strip(gpio_pin, end_needed, strip_type)
                if not strip:
                    self._send_json(500, {'error': 'strip init failed'})
                    return

                # v1.4.3: Debug logging only when not in quiet mode
                if not _QUIET_MODE:
                    try:
                        converted = []
                        for c in colors[:3]:
                            if c is None:
                                converted.append((0,0,0))
                            else:
                                r, g, b = c
                                converted.append((int(r*255), int(g*255), int(b*255)))
                        all_equal = len(colors) > 0 and all((((0,0,0) if c is None else (int(c[0]*255), int(c[1]*255), int(c[2]*255))) == ((0,0,0) if colors[0] is None else (int(colors[0][0]*255), int(colors[0][1]*255), int(colors[0][2]*255)))) for c in colors)
                    except Exception:
                        converted = []
                        all_equal = False
                    _logger.info(f"Set_leds gpio={gpio_pin} start={start} len={len(colors)} sample={converted} all_equal={all_equal}")

                for i, color in enumerate(colors):
                    led_index = start - 1 + i
                    if led_index >= _strip_sizes[gpio_pin]:
                        break
                    if color is None:
                        strip.setPixelColor(led_index, Color(0, 0, 0))
                    else:
                        r, g, b = color
                        strip.setPixelColor(led_index, Color(int(r * 255), int(g * 255), int(b * 255)))
                strip.show()
                time.sleep(0.001)  # v1.4.11: 1ms delay for WS281x reset (requires >50μs between frames)
                self._send_json(200, {'result': 'ok'})
                return

            # (end of set_leds)

            # v1.4.6: /set_batch endpoint - atomic update for multiple LED ranges on same GPIO
            if self.path == '/set_batch':
                gpio_pin = int(data.get('gpio_pin', 18))
                updates: List[Dict] = data.get('updates', [])

                if not updates:
                    self._send_json(400, {'error': 'no updates provided'})
                    return

                # Find max LED index needed for strip initialization
                max_index = 0
                for update in updates:
                    start = int(update.get('index_start', 1))
                    colors = update.get('colors', [])
                    if colors:
                        max_index = max(max_index, start - 1 + len(colors))
                    else:
                        end = int(update.get('index_end', start))
                        max_index = max(max_index, end)

                # Use first update's color order (all groups on same GPIO should have same order)
                color_order = updates[0].get('color_order', 'GRB').upper().strip()
                strip_type = STRIP_TYPES.get(color_order, DEFAULT_STRIP_TYPE)

                strip = _get_strip(gpio_pin, max_index, strip_type)
                if not strip:
                    self._send_json(500, {'error': 'strip init failed'})
                    return

                # Apply all updates to the strip (no show() yet - batch them)
                for update in updates:
                    start = int(update.get('index_start', 1))
                    colors = update.get('colors')

                    if colors is not None:
                        # Multi-LED update
                        for i, color in enumerate(colors):
                            led_index = start - 1 + i
                            if led_index >= _strip_sizes[gpio_pin]:
                                break
                            if color is None:
                                strip.setPixelColor(led_index, Color(0, 0, 0))
                            else:
                                r, g, b = color
                                strip.setPixelColor(led_index, Color(int(r * 255), int(g * 255), int(b * 255)))
                    else:
                        # Solid color update
                        end = int(update.get('index_end', start))
                        r = float(update.get('r', 1.0))
                        g = float(update.get('g', 1.0))
                        b = float(update.get('b', 1.0))
                        c = Color(int(r * 255), int(g * 255), int(b * 255))
                        for i in range(start - 1, end):
                            strip.setPixelColor(i, c)

                # CRITICAL: Single atomic show() for all updates
                strip.show()
                time.sleep(0.001)  # v1.4.11: 1ms delay for WS281x reset (requires >50μs between frames)

                if not _QUIET_MODE:
                    _logger.info(f"Applied set_batch gpio={gpio_pin} updates={len(updates)}")

                self._send_json(200, {'result': 'ok'})
                return

            # /init_strip endpoint: allows pre-initialization for diagnostics
            if self.path == '/init_strip':
                gpio_pin = int(data.get('gpio_pin', 18))
                total = int(data.get('total', 4))
                
                # Parse color_order if provided
                color_order = data.get('color_order', 'GRB').upper().strip()
                strip_type = STRIP_TYPES.get(color_order, DEFAULT_STRIP_TYPE)
                if color_order not in STRIP_TYPES:
                    _logger.warning(f"Unknown color_order '{color_order}', falling back to GRB. Valid options: {', '.join(STRIP_TYPES.keys())}")

                strip = _get_strip(gpio_pin, total, strip_type)
                if not strip:
                    self._send_json(500, {'error': 'strip init failed'})
                    return
                self._send_json(200, {'result': 'ok', 'color_order': get_strip_type_name(strip_type)})
                return

            # Fallthrough if path not found
            self._send_json(404, {'error': 'not found'})
        except Exception as e:
            _logger.exception('Unhandled exception in do_POST')
            self._send_json(500, {'error': 'internal', 'message': str(e)})


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


def watchdog_thread():
    """Notify systemd watchdog that service is alive."""
    if not SYSTEMD_AVAILABLE:
        return

    # Get watchdog interval from environment variable (in microseconds)
    import os
    watchdog_usec = os.getenv('WATCHDOG_USEC')
    if not watchdog_usec:
        _logger.info("Systemd watchdog not enabled")
        return

    # Convert to seconds and use half interval for safety margin
    interval_sec = int(watchdog_usec) / 1000000.0
    ping_interval = interval_sec / 2.0
    _logger.info(f"Systemd watchdog enabled, pinging every {ping_interval:.1f}s (interval: {interval_sec:.0f}s)")

    while True:
        time.sleep(ping_interval)
        systemd.daemon.notify("WATCHDOG=1")


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--port', type=int, default=3769)
    p.add_argument('--host', type=str, default='127.0.0.1')
    p.add_argument('--lumen-cfg', type=str, default=None,
                   help='Optional path to lumen.cfg to pre-init proxy strips')
    args = p.parse_args()

    server_address = (args.host, args.port)
    _logger.info(f"Starting ws281x proxy on {args.host}:{args.port}")
    _logger.info(f"Python: {sys.executable} script: {Path(__file__).resolve()} pid: {os.getpid()}")
    httpd = ThreadingHTTPServer(server_address, Handler)

    # Start watchdog thread if systemd available
    if SYSTEMD_AVAILABLE:
        watchdog_t = Thread(target=watchdog_thread, daemon=True)
        watchdog_t.start()
        # Notify systemd that we're ready
        systemd.daemon.notify("READY=1")
    else:
        _logger.info("Systemd not available (systemd.daemon module not installed)")

    # Pre-initialize strips based on lumen.cfg if provided
    if args.lumen_cfg:
        try:
            _logger.info(f"Parsing lumen config for pre-init: {args.lumen_cfg}")
            size_map, type_map = parse_lumen_cfg(args.lumen_cfg)
            for pin, total in size_map.items():
                strip_type = type_map.get(pin, DEFAULT_STRIP_TYPE)
                color_order_name = get_strip_type_name(strip_type)
                _logger.info(f"Pre-init strip on GPIO {pin} -> {total} LEDs, color_order={color_order_name}")
                _get_strip(pin, total, strip_type)
        except Exception:
            _logger.exception('Failed to parse lumen cfg')
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        _logger.info('Stopping ws281x proxy')
    finally:
        httpd.server_close()
        if SYSTEMD_AVAILABLE:
            systemd.daemon.notify("STOPPING=1")


if __name__ == '__main__':
    main()
