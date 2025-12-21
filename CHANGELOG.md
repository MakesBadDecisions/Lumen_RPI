# Changelog

All notable changes to LUMEN will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2024-12-21

### 🎉 First Stable Release

Production-ready LED control for Klipper printers. Tested on Voron Trident with full state cycle validation (fresh install → heating → printing → cooldown → idle → bored → sleep → rewake cycle).

**Comprehensive code review completed** - All critical, high, and medium priority issues fixed for release.

### Added

#### Core Features
- **Modular Architecture**: Plugin-based effect and state systems with registry pattern
- Real-time state detection for 7 printer states: idle, heating, printing, cooldown, error, bored, sleep
- GPIO driver with ws281x-proxy (60fps smooth animations, bypasses G-code queue)
- Klipper driver (SET_LED for MCU-attached LEDs)
- PWM driver (SET_PIN for non-addressable LED strips)
- 7 LED effects: solid, pulse, heartbeat, disco, thermal gradient, print progress bar, off
- 50+ named colors (Aurora-compatible palette)
- Hot reload via `/server/lumen/reload` API endpoint
- Config validation with helpful warnings
- Debug logging to journalctl and Mainsail console
- Interactive installer with automatic path detection
- Thread-safe ws281x proxy with proper locking
- Shutdown cleanup handler (gracefully turns off LEDs on exit)
- Motion report subscription for immediate position tracking
- **Task Exception Handling**: Comprehensive error handling for background tasks
- **Performance Optimizations**: Effect instance caching, animation loop improvements

#### Installation & Maintenance
- Automated installer (`install.sh`) with interactive prompts
- Automated uninstaller (`uninstall.sh`) with complete cleanup
- Automatic moonraker.conf section management (install/uninstall)
- Debug mode comments in installer for user guidance

### Fixed

#### Critical Bugs - v1.0 Final Release (December 21, 2024)
- **Memory leak on config reload**: Effect instance cache and thermal log cache now cleared properly
- **Silent task failures**: Background tasks now have exception handlers, errors logged instead of ignored
- **Animation loop race condition**: Properly cancels and awaits old tasks before starting new ones
- **Effect cache corruption**: Per-group effect instance caching prevents state bleeding between groups
- **Bored/Sleep state flapping**: States now persist correctly, no more rapid idle↔bored transitions

#### Critical Bugs - Pre-release (December 19-20, 2024)
- **Config parser bug**: Fixed missing gpio_pin, proxy_host, proxy_port, color_order storage in LED group config
- **Effect state race condition**: Apply immediate effects before updating state to prevent animation loop conflicts
- **Install script path**: Fixed ws281x-proxy path reference (was pointing to outdated location)
- **Race condition in ws281x_proxy.py**: Added global `_strip_locks_lock` for thread-safe lock initialization

#### Driver Improvements
- **GPIODriver thread safety**: Global state protected with per-pin locks
- GPIO driver now properly handles strip expansion (recreates PixelStrip with existing LED states)
- **ProxyDriver connection failures**: Now logged with warnings for debugging
- ProxyDriver async initialization cleaned up (removed broken code)
- KlipperDriver INDEX loop logic verified and documented

#### State Detection Improvements
- **StateDetector listener exceptions**: Now logged instead of silently swallowed
- Bored and sleep states check actual printer state (no heaters, no prints)
- Once entered, states persist correctly until conditions change

#### Logging & Debugging
- Debug logging now properly respects False/True/console modes
- Thermal effect logging throttled (only logs on temp change ≥1°C or every 10s)
- Added color_order validation with helpful warnings
- Task exception handler logs background task failures

#### Performance & Stability
- **Animation loop interval clamping**: Minimum 1ms interval prevents busy-looping
- **Effect instance caching**: Per-group caching eliminates object creation on every frame
- **Smooth 60fps animations**: Achieved on GPIO driver after caching fix

### Documentation
- Comprehensive README.md with installation, configuration, and troubleshooting
- TODO.md roadmap with future feature planning
- Example configuration in `config/lumen.cfg.example`
- GPIO 19 audio conflict troubleshooting documented
- Production status badges and testing notes

---

## Release Notes

### v1.0.0 - What's Working

**Tested Hardware:**
- Voron Trident with Raspberry Pi 4
- WS2812B LED strips on GPIO 21
- Full state cycle validation complete

**Performance:**
- 60fps smooth animations on GPIO driver
- <1% CPU usage on Raspberry Pi 4
- ~50MB memory footprint

**Known Limitations:**
- Klipper driver slower during prints (G-code queue bottleneck) - expected behavior
- GPIO 19 conflicts with audio on Raspberry Pi (use GPIO 18 instead)

**Upgrade Path:**
- v1.1.0 will add: paused, homing, meshing, leveling, probing states
- v1.2.0 will add: rainbow, fire, comet, chase, alert, wipe effects
- v1.3.0 will add: chamber temp, filament sensors, Z-height gradients

---

## Previous Versions

This is the first stable release. Pre-release development history available in commit logs.

---

**Legend:**
- 🎉 Major milestone
- ✨ New feature
- 🐛 Bug fix
- ⚡ Performance improvement
- 📝 Documentation
- 🔧 Maintenance

[1.0.0]: https://github.com/MakesBadDecisions/Lumen_RPI/releases/tag/v1.0.0
