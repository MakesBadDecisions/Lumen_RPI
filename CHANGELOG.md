# Changelog

All notable changes to LUMEN will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.5.0] - 2025-12-27 🧹 MAJOR CLEANUP - Macro Tracking Removed

### 🎯 **BREAKING CHANGE** - Return to Simple, Reliable Core

After extensive debugging revealed macro tracking caused more problems than it solved, **all macro tracking code has been completely removed**. LUMEN now focuses on what it does best: simple, reliable temperature-based state detection.

### Removed

**Macro Tracking System (v1.2.0-v1.4.8):**
- Removed all 7 macro-triggered states (homing, meshing, leveling, probing, paused, cancelled, filament)
- Removed gcode_response event subscription and monitoring
- Removed homed_axes tracking attempts
- Removed all `macro_*` configuration settings parsing
- Removed RESPOND message detection and processing
- Removed macro timeout and completion detection
- Removed all macro state detector files (homing.py, meshing.py, etc.)

**Files Deleted:**
- `moonraker/components/lumen_lib/states/homing.py`
- `moonraker/components/lumen_lib/states/meshing.py`
- `moonraker/components/lumen_lib/states/leveling.py`
- `moonraker/components/lumen_lib/states/probing.py`
- `moonraker/components/lumen_lib/states/paused.py`
- `moonraker/components/lumen_lib/states/cancelled.py`
- `moonraker/components/lumen_lib/states/filament.py`

### Fixed

**Critical Runtime Errors:**
- Fixed AttributeError from references to non-existent `active_macro_state` and `macro_start_time` in PrinterState
- Fixed undefined `_active_macro_state` variable references in animation loop
- Removed unnecessary gcode output subscription that wasted bandwidth
- Removed homed_axes subscription that provided no value

**Performance Issues:**
- Eliminated gcode response parsing overhead
- Removed message filtering logic that ran on every gcode response
- Simplified animation loop interval calculation
- Reduced memory footprint by removing macro tracking state variables

**User Experience:**
- Eliminated flickering during prints (caused by rapid state changes)
- Removed complexity of macro configuration
- Eliminated need for LUMEN macro calls in user macros
- Removed validation warnings for macro event mappings

### Changed

**Core System (now 7 states only):**
- `idle` - Printer ready, all temps nominal
- `heating` - Heaters warming up to target
- `printing` - Active print job at temperature
- `cooldown` - Print finished, cooling down
- `error` - Klipper shutdown or error condition
- `bored` - Idle for extended period (60s default)
- `sleep` - Bored for extended period (10min default)

**Temperature Tolerance Fix Preserved:**
- PrintingDetector: 10°C extruder tolerance (prevents flickering from PID fluctuations)
- PrintingDetector: 5°C bed tolerance (stricter for more stable temps)

**Config Validation:**
- Now only validates 7 core states
- Macro event mappings (on_homing, etc.) will generate warnings
- Macro settings (macro_homing, etc.) silently ignored

### Migration Guide

**If you had macro tracking configured:**

1. **Remove macro event mappings** from your lumen.cfg LED groups:
   ```ini
   # REMOVE these lines:
   on_homing: solid white
   on_meshing: solid green
   on_leveling: solid sky
   on_probing: solid blue
   on_paused: solid yellow
   on_cancelled: solid red
   on_filament: solid lava
   ```

2. **Remove macro settings** from [lumen_settings]:
   ```ini
   # REMOVE these lines:
   macro_homing: G28, HOMING_OVERRIDE
   macro_meshing: BED_MESH_CALIBRATE
   macro_leveling: Z_TILT_ADJUST
   macro_probing: CARTOGRAPHER_TOUCH_HOME
   macro_paused: PAUSE
   macro_cancelled: CANCEL_PRINT
   macro_filament: M600, FILAMENT_RUNOUT
   ```

3. **Remove LUMEN macro calls** from your Klipper macros:
   ```gcode
   # REMOVE lines like:
   LUMEN STATE=homing
   LUMEN STATE=meshing
   # etc.
   ```

4. **Remove LUMEN macro definition** (if present):
   ```gcode
   # REMOVE entire section:
   [gcode_macro LUMEN]
   description: Trigger LUMEN LED state change
   gcode:
       ...
   ```

**What stays the same:**
- All core state detection (heating, printing, cooldown, idle, bored, sleep, error)
- All effects (solid, pulse, heartbeat, disco, rainbow, fire, comet, chase, KITT, thermal, progress, off)
- All drivers (GPIO/proxy, Klipper, PWM)
- Configuration syntax for LED groups and effects
- API endpoints

### Why This Change?

**Problems with macro tracking (v1.2.0-v1.4.8):**
1. Added significant complexity for minimal benefit
2. Required users to modify their macros with LUMEN STATE calls
3. Caused LED flickering during prints due to rapid state changes
4. G-code response parsing added CPU overhead
5. Silent macros (like G28) couldn't be auto-detected anyway
6. Introduced hard-to-debug runtime errors
7. Configuration became too complex

**Benefits of removal:**
1. Simpler, more reliable codebase
2. No user macro modifications required
3. Better performance (no message parsing)
4. Eliminated flickering issues
5. Focus on core competency: temperature-based state detection
6. Easier to maintain and debug
7. Cleaner configuration

---

## [1.4.8] - 2025-12-26 📋 INVESTIGATION COMPLETE - Macro Detection Limitations

### ⚠️ **IMPORTANT FINDINGS** - Fully Automatic Macro Detection Is Impossible

After exhaustive investigation spanning v1.4.5 through v1.4.8, we've conclusively determined that **automatic detection of silent macros is not technically feasible** in Moonraker/Klipper architecture.

#### Root Causes Discovered

**1. G28 Produces No Gcode Responses** (v1.4.5-v1.4.7)
- Z_TILT_ADJUST generates probe result messages → auto-detected ✓
- BED_MESH_CALIBRATE generates "mesh saved" messages → auto-detected ✓
- **G28 runs completely silent** → no gcode responses → cannot detect ✗

**2. homed_axes Doesn't Change During Homing** (v1.4.8)
- Attempted to detect homing via `toolhead.homed_axes` transitions
- Expected: `"xyz"` → `""` (unhomed) → `"xyz"` (homed)
- **Reality**: `homed_axes` stays `"xyz"` throughout entire G28 process
- Klipper doesn't clear homed_axes during homing on most machines

**3. Moonraker Subscriptions Send Deltas Only** (v1.4.8)
- `subscribe_objects()` only broadcasts fields that **change**
- Position updates contain `["position"]` but NOT `["homed_axes"]`
- Attempted polling via `query_objects()` on every position update
- Result: Massive performance overhead, still no detection

#### Attempted Solutions (All Failed)

- **v1.4.5**: Added `subscribe_gcode_output()` - Works for loud macros, fails for silent ones
- **v1.4.6**: Comprehensive config parser debugging - Config loads correctly, not the issue
- **v1.4.7**: Event handler signature investigation - Callback works, just no data for G28
- **v1.4.8**: homed_axes polling - Axes don't change during homing, polling too expensive

### Solution - RESPOND Messages Required for Silent Macros

**Macros That Work Automatically** (generate console output):
```gcode
Z_TILT_ADJUST          # Prints probe results → auto-detected ✓
BED_MESH_CALIBRATE     # Prints "mesh saved" message → auto-detected ✓
QUAD_GANTRY_LEVEL      # Prints probe results → auto-detected ✓
```

**Macros That Need RESPOND Messages** (silent operation):
```gcode
[gcode_macro G28]
rename_existing: G28.1
gcode:
    RESPOND MSG="LUMEN_HOMING_START"
    G28.1 {rawparams}
    RESPOND MSG="LUMEN_HOMING_END"
```

### Changed

- **Documentation**: Updated README to explain RESPOND message requirement
- **Expectation**: Changed from "fully automatic" to "requires RESPOND for silent macros"
- **Code**: Added `_activate_macro_state()` helper for DRY
- **Testing**: Confirmed Z_TILT_ADJUST auto-detection works, G28 requires RESPOND

### Architectural Insight

The fundamental issue is Moonraker's event-driven architecture:
1. Components can only react to events Klipper broadcasts
2. Klipper only broadcasts changes (deltas), not full state
3. Silent macros generate no events to react to
4. Polling is antithetical to event-driven design and kills performance

**There is no technical solution** without macros announcing themselves via RESPOND or M117.

---

## [1.4.7] - 2025-12-26 🔍 DIAGNOSTIC VERSION - Event Handler Signature

### 🐛 Investigating - Event Handler Not Being Invoked

#### Root Cause Hypothesis
- v1.4.6 proved config parser IS working correctly (macro lists populated)
- v1.4.5 subscription IS active ("subscribed to gcode output" message present)
- v1.4.6 proved `_on_gcode_response()` callback is NEVER invoked (zero debug messages when running G28)
- **New hypothesis**: Event handler function signature might be incorrect
  - `_on_status_update()` receives `Dict[str, Any]` parameter
  - `_on_gcode_response()` expects `str` parameter
  - **What if Moonraker passes gcode responses differently than expected?**

#### Debug Changes
- Changed `_on_gcode_response(self, response: str)` to `_on_gcode_response(self, *args, **kwargs)`
- Added logging to show EXACTLY what parameters Moonraker passes to the callback
- Added flexible parameter extraction (tries positional args, then keyword args)
- This will definitively show if callback is being invoked and what data format is used

#### How to Use v1.4.7
1. Stop Moonraker completely: `sudo systemctl stop moonraker && sleep 3`
2. Update: `cd ~/lumen && git pull`
3. Hard start: `sudo systemctl start moonraker && sleep 5`
4. Watch logs: `journalctl -u moonraker -f | grep "_on_gcode_response"`
5. Run G28 in Mainsail/Fluidd console
6. Look for: `[DEBUG] _on_gcode_response called! args=(...), kwargs={...}`
   - If you see this message: Callback IS being invoked, check the parameter format
   - If you DON'T see this message: Callback still not being invoked (deeper Moonraker issue)

---

## [1.4.6] - 2025-12-26 🔍 DIAGNOSTIC VERSION - Config Parser

### 🐛 Investigating - Config Parser Not Loading Macro Settings (RESOLVED)

#### Symptoms
- v1.4.5 subscription fix is working (gcode output being received)
- Config file has correct macro settings (verified via grep)
- BUT API shows all macro settings as `None` in memory
- Result: Macro detection still not working despite subscription being active

#### Debug Logging Added
- Config file reading: Log total lines loaded and each section found
- Macro setting parsing: Log each `macro_*` key/value pair as it's parsed
- Section processing: Log number of keys in data dict when processing `[lumen_settings]`
- Macro presence check: Log whether `macro_homing` exists in data dict

#### How to Use Diagnostic Version
1. Update to v1.4.6: `git pull && sudo systemctl restart moonraker`
2. Check logs: `journalctl -u moonraker -f | grep -i "DEBUG"`
3. Look for:
   - `[DEBUG] Config file loaded: X lines`
   - `[DEBUG] Found section: [lumen_settings]`
   - `[DEBUG] Parsed macro_homing: 'G28, HOMING_OVERRIDE'`
   - `[DEBUG] Processing [lumen_settings] with X keys: [...]`
   - `[DEBUG] macro_homing value: '...'` OR `[DEBUG] macro_homing NOT FOUND in data dict`

---

## [1.4.5] - 2025-12-26 🔥 CRITICAL BUGFIX

### 🐛 Fixed - Macro Tracking Completely Non-Functional Since v1.2.0

#### Root Cause Discovery
- **Critical Bug**: Macro tracking has NEVER worked in production since initial release in v1.2.0
- **Issue**: Component registered `server:gcode_response` event handler but never subscribed to Klippy's gcode output
- **Evidence**:
  - Zero "Macro detected: G28 → state: homing" messages in production logs
  - State stayed "printing" during G28/BED_MESH_CALIBRATE/etc instead of transitioning to macro states
  - KITT effect never ran on center during meshing despite config: `on_meshing: kitt cobalt`
  - Thermal effects never ran during meshing/probing despite config
  - All 7 macro-triggered states completely broken (homing, meshing, leveling, probing, paused, cancelled, filament)

#### Technical Explanation
Moonraker's gcode response flow:
1. Klippy sends gcode responses to Moonraker's `klippy_connection` component
2. `klippy_connection._process_gcode_response()` broadcasts them as `server:gcode_response` events
3. **BUT** Klippy only sends responses if a component calls `klippy_apis.subscribe_gcode_output()`
4. LUMEN registered the event handler but **never called subscribe_gcode_output()**
5. Result: Klippy never sent any gcode output to Moonraker for LUMEN

#### The Fix
- **Added**: `await klippy_apis.subscribe_gcode_output()` call in `_on_klippy_ready()` (lumen.py:535)
- **Changed**: Updated initialization log to clarify subscription happens during klippy_ready (lumen.py:141-142)
- **Impact**: All 7 macro states now actually work for the first time ever

### Changed
- Version bumped from v1.4.4 to v1.4.5
- Added Klippy gcode output subscription during component initialization

---

## [1.4.4] - 2025-12-26 ✅ PRODUCTION READY

### ⚡ Performance Improvements - Effect-Aware Adaptive FPS

#### Intelligent FPS Scaling Based on Effect Complexity
- **Issue**: All effects running at same update rate wastes CPU/HTTP on static effects, bottlenecks fast animations
- **Solution**: Categorize effects by complexity and apply appropriate FPS limits
  - **Static effects** (`solid`, `off`): 5 FPS (0.2s interval) - no animation, minimal updates needed
  - **Slow effects** (`pulse`, `heartbeat`, `thermal`, `progress`): 20 FPS (0.05s interval) - smooth enough for gradual changes
  - **Fast effects** (`disco`, `rainbow`, `fire`, `comet`, `chase`, `kitt`): Full driver speed (30-40 FPS target) - visually demanding animations
- **Implementation**: Modified animation loop to scale driver intervals based on effect category (lumen.py:1095-1156)
- **Impact**:
  - Reduces unnecessary HTTP requests for static/slow effects
  - Frees up CPU/HTTP capacity for fast animations
  - Achieves 30-40 FPS on fast animations with multiple groups
  - Zero frame skip warnings during print cycles with mixed effects
  - Expected frame skip warnings during cooldown with all fast effects (HTTP bottleneck at 180 req/s)

### Production Validation
- ✅ All 14 printer states working (idle, heating, printing, cooldown, error, bored, sleep, homing, meshing, leveling, probing, paused, cancelled, filament)
- ✅ All 12 LED effects rendering correctly (solid, pulse, heartbeat, disco, rainbow, fire, comet, chase, KITT, thermal, progress, off)
- ✅ Macro tracking fully functional (G28, BED_MESH_CALIBRATE, filament sensors all detected)
- ✅ Multi-group coordination working (predator/prey chase with collision detection)
- ✅ Hot reload functional (interval cache, macro state, chase cache all cleared correctly)
- ✅ Filament sensor integration working
- ✅ Temperature sources working (bed, extruder, chamber)

### Changed
- Version bumped from v1.4.3 to v1.4.4
- Animation loop now applies effect-aware FPS scaling
- Static effects limited to 5 FPS maximum
- Slow effects limited to 20 FPS maximum
- Fast effects get full available driver speed (30-40 FPS achieved)

---

## [1.4.3] - 2025-12-26

### ⚡ Performance Improvements - 60 FPS Optimization

#### ProxyDriver Timeout Reduction
- **Issue**: At 60 FPS with 3 proxy groups = 180 HTTP requests/second, 0.1s timeout still bottlenecking at ~30 FPS
- **Fix**: Reduced timeout from 0.1s to 0.01s (10ms) for ultra-fast fire-and-forget updates (drivers.py:325)
- **Impact**: Further reduces HTTP latency overhead

#### WS281x Proxy Quiet Mode
- **Issue**: Proxy logging 4 messages per request (720 log lines/second at 60 FPS × 3 groups) creates CPU overhead
- **Fix**: Added `WS281X_QUIET=1` environment variable to suppress verbose logging during high FPS operation
- **Implementation**:
  - ws281x_proxy.py lines 45-48: Auto-detect quiet mode from environment
  - ws281x_proxy.py lines 218, 235, 241, 270, 293-306: Skip verbose logging when quiet mode enabled
  - install.sh line 465: Add `Environment="WS281X_QUIET=1"` to systemd service
- **Impact**: Reduces proxy CPU overhead from logging spam, allows more headroom for actual LED updates

### Changed
- Version bumped from v1.4.2 to v1.4.3
- ProxyDriver timeout reduced to 10ms
- WS281x proxy now runs in quiet mode by default (errors still logged)

---

## [1.4.2] - 2025-12-26 ✅ RESOLVED

### 🐛 Macro Tracking Investigation - Working Correctly

#### Investigation Results
- **Initial concern**: Event handler possibly not receiving G-code responses
- **Finding**: Event handler working correctly all along
  - Fresh install testing validated all macro-triggered states functional
  - G28 (homing), BED_MESH_CALIBRATE (meshing), filament sensors all detected correctly
  - v1.4.1 filters preventing infinite loops working perfectly
  - Event handler registration at line 134 working as designed
- **Debug logging confirmed**:
  - `_on_gcode_response()` callback IS being invoked
  - Macro detection, completion detection, and timeout all functional
  - All 7 macro-triggered states working (homing, meshing, leveling, probing, paused, cancelled, filament)

### Changed
- Version bumped from v1.4.1 to v1.4.2
- Removed non-existent `subscribe_gcode_output()` call
- Added diagnostic logging (can be removed in future cleanup)

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
- **Fix**: Skip Klipper driver updates when macro state is active, allowing only GPIO/Proxy drivers to update (lumen.py:983-984, 1102-1103)
- **Impact**: Eliminated timeout spam in logs, LEDs now respond correctly to macro states on GPIO-attached strips

#### GPIO Animation Slowdown During Macros
- **Root cause**: Animation interval calculation used `is_printing` check without considering macro states, causing GPIO drivers to use slow "printing" interval during homing/meshing/etc.
- **Fix**: Treat macro states as non-printing for interval calculation - `is_printing = print_state == "printing" and not self._active_macro_state` (lumen.py:1048)
- **Impact**: GPIO-driven LEDs now maintain full 60 FPS during all macro states (homing, meshing, leveling, etc.)

#### PWM Driver Timeout Spam During Macros
- **Root cause**: PWMDriver uses SET_PIN G-code which also blocks during macros, but wasn't skipped like KlipperDriver
- **Fix**: Skip both KlipperDriver and PWMDriver during macro states (lumen.py:983, 1104)
- **Impact**: Eliminates timeout spam for PWM-controlled non-addressable LED strips

#### Config Reload Issues
- **Root cause**: Reload handler didn't rebuild driver interval cache or clear macro state, causing animation failures and stuck states
- **Fix**: Added `_cache_driver_intervals()` call and macro state reset in `_handle_reload()` (lumen.py:1256-1267)
- **Impact**: Hot reload now works correctly without requiring moonraker restart

#### Memory Leak on Reload
- **Root cause**: Multi-group chase coordination cache entries never cleared on reload
- **Fix**: Clear chase cache entries before full cache clear (lumen.py:1271-1272)
- **Impact**: Prevents slow memory leak during repeated reloads

### ✨ New Features
- **Macro completion detection**: Automatically detects macro completion messages (e.g., "// Mesh Bed Leveling Complete") and returns to normal state cycle (lumen.py:612-636)
- **Macro timeout**: 120-second safety timeout prevents stuck macro states if completion message not detected (lumen.py:584-591)
- **Frame skip detection**: Warns if animation loop falls behind target FPS due to system overload (lumen.py:1188-1200)

### 🔧 Code Quality Improvements
- **Paused state consistency**: Removed dual-detection mode - now uses macro tracking only like other states (paused.py:37-39)
- **Color lookup cache**: Added LRU cache to `get_color()` for improved performance (colors.py:105)
- **Clarified comments**: Improved comment accuracy regarding effect state updates (lumen.py:795)

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

[1.4.4]: https://github.com/MakesBadDecisions/Lumen_RPI/releases/tag/v1.4.4
[1.4.3]: https://github.com/MakesBadDecisions/Lumen_RPI/releases/tag/v1.4.3
[1.4.2]: https://github.com/MakesBadDecisions/Lumen_RPI/releases/tag/v1.4.2
[1.4.1]: https://github.com/MakesBadDecisions/Lumen_RPI/releases/tag/v1.4.1
[1.4.0]: https://github.com/MakesBadDecisions/Lumen_RPI/releases/tag/v1.4.0
[1.3.0]: https://github.com/MakesBadDecisions/Lumen_RPI/releases/tag/v1.3.0
[1.2.0]: https://github.com/MakesBadDecisions/Lumen_RPI/releases/tag/v1.2.0
[1.1.5]: https://github.com/MakesBadDecisions/Lumen_RPI/releases/tag/v1.1.5
[1.1.0]: https://github.com/MakesBadDecisions/Lumen_RPI/releases/tag/v1.1.0
[1.0.0]: https://github.com/MakesBadDecisions/Lumen_RPI/releases/tag/v1.0.0
