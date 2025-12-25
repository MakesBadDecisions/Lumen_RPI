# Changelog

All notable changes to LUMEN will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.4.1] - 2025-12-25

### 🐛 Critical Bug Fixes - Macro Tracking

#### Infinite Loop Console Spam
- **Root cause**: LUMEN console messages containing macro names (e.g., "BED_MESH_CALIBRATE") triggered infinite detection loops
- **Fix**: Added filter to ignore G-code responses starting with "LUMEN" or "// LUMEN" (lumen.py:603-605)
- **Impact**: Prevented system lockups during bed meshing and other macros

#### Malformed G-code Debug Messages
- **Root cause**: Long debug messages with probe results caused truncated RESPOND commands
- **Fix**: Added filter to skip probe result messages (lumen.py:607-610)
- **Impact**: Eliminated "Malformed command" errors in Klipper logs

#### Klipper Driver Timeout Spam
- **Root cause**: Klipper's G-code queue blocks during macro execution, causing SET_LED commands to timeout every 2 seconds
- **Fix**: Skip Klipper driver updates when macro state is active, allowing only GPIO/Proxy drivers to update (lumen.py:956-959, 1071-1075)
- **Impact**: Eliminated timeout spam in logs, LEDs now respond correctly to macro states on GPIO-attached strips

### ✨ New Features
- **Macro completion detection**: Automatically detects macro completion messages (e.g., "// Mesh Bed Leveling Complete") and returns to normal state cycle (lumen.py:612-636)
- **Macro timeout**: 120-second safety timeout prevents stuck macro states if completion message not detected (lumen.py:584-591)

### Changed
- Version bumped from v1.4.0 to v1.4.1

---

## [1.4.0] - 2025-12-25

### ⚡ Performance Optimizations

#### Hot Path Improvements
- **Driver interval caching**: Eliminated 240-300 `isinstance()` checks per second at 60 FPS by pre-caching driver intervals during initialization
- **State_data pre-building**: Build printer state data once per animation cycle instead of rebuilding for each effect (93% reduction in dictionary operations)
- **Loop attribute caching**: Cache repeated attribute lookups in chase, kitt, and fire effects before entering render loops
- **Disco random selection**: Optimized LED selection from O(n log n) sort-based approach to O(k) `random.sample()` algorithm

#### Code Deduplication
- **HSV utility extraction**: Created shared `hsv_to_rgb()` function in `colors.py`, eliminating ~90 lines of duplicated HSV→RGB conversion code across rainbow, fire, and disco effects

### 🐛 Critical Bug Fixes
- **Disco bounds validation**: Fixed `ValueError` crash when `min_sparkle > max_sparkle` by ensuring min ≤ max before calling `random.randint()`
- **Thermal division by zero**: Added safety check to prevent division by zero when `temp_range ≤ 0` in edge cases

### 🔧 Code Cleanup
- **Removed unused imports**: Deleted unused `json` and `os` imports from `lumen.py`
- **Removed dead telemetry code**: Cleaned up unused tracking variables from early development
- **Removed unused PWMDriver methods**: Deleted `set_on()` and `set_dim()` methods (only `set_brightness()` and `set_off()` are used)
- **Added error logging**: Improved debugging by logging exceptions in previously silent exception handlers

### Changed
- Version bumped from v1.3.0 to v1.4.0

---

## [1.3.0] - 2025-12-24

### ✨ New Features

#### Temperature Sources
- **Chamber temperature support**: Added `temp_source: chamber` option for thermal effect
  - Subscribes to `temperature_sensor chamber_temp` if available in Klipper config
  - Graceful fallback if chamber sensor not present
  - Status API now includes `chamber_temp` and `chamber_target` fields

#### Filament Sensor Integration
- **Automatic filament runout detection**: Subscribes to `filament_switch_sensor filament_sensor` events
  - Automatically triggers `on_filament` state when runout detected (`filament_detected: false`)
  - Works alongside existing macro-triggered filament states from v1.2.0
  - Status API includes `filament_detected` field (true/false/null if no sensor)

### Fixed
- **Config validator**: Added v1.2.0 states (homing, meshing, leveling, probing, paused, cancelled, filament) to valid_events set
- **Chamber sensor naming**: Updated code to use `chamber_temp` instead of generic `chamber` to match common Klipper conventions

---

## [1.2.0] - 2025-12-23

### ✨ New Printer States

Added 7 new macro-triggered states with user-configurable tracking:

- **Homing**: G28 in progress
- **Meshing**: BED_MESH_CALIBRATE running
- **Leveling**: QUAD_GANTRY_LEVEL or Z_TILT_ADJUST running
- **Probing**: PROBE_CALIBRATE or similar
- **Paused**: Print paused by user or PAUSE macro
- **Cancelled**: Print cancelled by CANCEL_PRINT macro
- **Filament Change**: Filament load/unload/runout (M600, etc.)

#### Configuration
New `[lumen_settings]` options for macro tracking:
```ini
macro_homing: G28
macro_meshing: BED_MESH_CALIBRATE
macro_leveling: QUAD_GANTRY_LEVEL, Z_TILT_ADJUST
macro_probing: PROBE_CALIBRATE
macro_paused: PAUSE
macro_cancelled: CANCEL_PRINT
macro_filament: M600, FILAMENT_RUNOUT, LOAD_FILAMENT, UNLOAD_FILAMENT
```

New `on_*` effect options for LED groups:
- `on_homing`, `on_meshing`, `on_leveling`, `on_probing`
- `on_paused`, `on_cancelled`, `on_filament`

#### Implementation
- Subscribes to `notify_gcode_response` via Moonraker WebSocket
- Parses G-code responses for user-configured macro names
- Universal compatibility with any printer's custom macros
- Returns to normal state cycle when macro completes

---

## [1.1.5] - 2025-12-22

### ✨ New Effects

#### Chase Effect
Multi-mode predator/prey chase animation:
- **Single-group mode**: Two colored segments chase each other with dynamic offset variation
- **Multi-group circular array mode**: Groups coordinate as a ring with collision detection, role swapping, and proximity acceleration
- Configurable parameters: `chase_size`, `chase_color_1`, `chase_color_2`, `chase_offset_base`, `chase_offset_variation`, `chase_proximity_threshold`, `chase_accel_factor`, `chase_role_swap_interval`, `chase_collision_pause`

#### KITT Effect
Knight Rider-style scanner bounce:
- Smooth back-and-forth animation with bright center "eye"
- Configurable fading tail on both sides
- Optional bed mesh tracking: follows X or Y axis position during moves
- Parameters: `speed`, `base_color`, `kitt_eye_size`, `kitt_tail_length`, `kitt_tracking_axis`

---

## [1.1.0] - 2025-12-22

### ✨ New Effects

#### Rainbow Effect
- Smooth cycling through entire color spectrum using HSV color space
- Configurable spread across LED strip (`rainbow_spread: 0.0-1.0`)
- Works with single and multi-LED configurations
- Parameters: `speed`, `rainbow_spread`, `max_brightness`

#### Fire Effect
- Realistic flickering flame simulation with per-LED heat tracking
- Orange/red/yellow color spectrum (HSV-based)
- Configurable cooling rate for chaos control
- Parameters: `speed`, `min_brightness`, `max_brightness`, `fire_cooling`

#### Comet Effect
- Moving light with exponential trailing tail
- Bright head with configurable fade rate
- Supports forward and reverse direction
- Parameters: `speed`, `max_brightness`, `comet_tail_length`, `comet_fade_rate`

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

[1.4.1]: https://github.com/MakesBadDecisions/Lumen_RPI/releases/tag/v1.4.1
[1.4.0]: https://github.com/MakesBadDecisions/Lumen_RPI/releases/tag/v1.4.0
[1.3.0]: https://github.com/MakesBadDecisions/Lumen_RPI/releases/tag/v1.3.0
[1.2.0]: https://github.com/MakesBadDecisions/Lumen_RPI/releases/tag/v1.2.0
[1.1.5]: https://github.com/MakesBadDecisions/Lumen_RPI/releases/tag/v1.1.5
[1.1.0]: https://github.com/MakesBadDecisions/Lumen_RPI/releases/tag/v1.1.0
[1.0.0]: https://github.com/MakesBadDecisions/Lumen_RPI/releases/tag/v1.0.0
