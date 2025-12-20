# LUMEN Development Roadmap

Active development tasks and future enhancements for LUMEN.

---

## ✅ v0.1.0 Complete (December 2025)

### Core Features
- [x] Real-time state detection (idle, heating, printing, cooldown, error, bored, sleep)
- [x] GPIO driver with ws281x-proxy (60fps, bypasses G-code queue)
- [x] Klipper driver (SET_LED for MCU-attached LEDs)
- [x] PWM driver (SET_PIN for non-addressable strips)
- [x] Effects: solid, pulse, heartbeat, disco, thermal, progress
- [x] 50+ named colors (Aurora-compatible)
- [x] Hot reload via `/server/lumen/reload` API
- [x] Config validation with helpful warnings
- [x] Debug logging to journalctl and Mainsail console
- [x] Interactive installer with auto-path detection
- [x] Thread-safe ws281x proxy with proper locking
- [x] Shutdown cleanup handler (turns off LEDs gracefully)
- [x] Motion report subscription for position tracking

### Bug Fixes (December 19, 2025)
- [x] Fixed install.sh proxy path (line 342)
- [x] Fixed race condition in ws281x_proxy.py (global _strip_locks_lock)
- [x] Fixed GPIO driver strip expansion (properly recreates PixelStrip)
- [x] Fixed ProxyDriver async init (removed broken code)
- [x] Added color_order validation with warnings
- [x] Verified gpio_fps setting actively used (line 634)
- [x] Added thermal logging throttle (only on temp change ≥1°C or every 10s)
- [x] Added motion_report to initial query (position available immediately)

---

## 🎯 v0.2.0 - Additional Printer States

### New States to Detect
- [ ] **Paused** - Print paused by user or M600
- [ ] **Homing** - G28 in progress
- [ ] **Meshing** - BED_MESH_CALIBRATE running
- [ ] **Leveling** - QUAD_GANTRY_LEVEL or Z_TILT_ADJUST running
- [ ] **Probing** - PROBE_CALIBRATE or similar

**Implementation Notes:**
- Subscribe to `toolhead` object for `homing_origin` tracking
- Track macro execution for QGL/Z_TILT/BED_MESH
- Add state transition logic in state.py

---

## 🎨 v0.3.0 - New Effects

### Planned Effects
- [ ] **Rainbow** - Cycling rainbow pattern
- [ ] **Fire** - Flickering flame simulation
- [ ] **Comet** - Moving light with trailing tail
- [ ] **Chase** - Sequential LED activation (KIT scanner style)
- [ ] **Alert** - Fast blinking for critical notifications
- [ ] **Wipe** - Fill/clear animation (left-to-right, right-to-left)

**Implementation Notes:**
- Add to `moonraker/components/lumen_lib/effects.py`
- Update config parsing in lumen.py
- Add effect settings to lumen.cfg.example

---

## 📊 v0.4.0 - Data Sources

### New Temperature Sources
- [ ] **Chamber temperature** - Add to thermal effect
  - Subscribe to `temperature_sensor chamber` if available
  - Graceful fallback if not present

### Filament Sensor Integration
- [ ] **Filament runout detection** - Trigger special effect
  - Subscribe to `filament_switch_sensor` events
  - Configurable `on_runout` effect per group

### Position-Based Effects
- [ ] **Z-height gradient** - Color changes based on current Z position
  - Use toolhead position data
  - Useful for showing print height visually

---

## 🔧 v0.5.0 - Quality of Life

### Configuration Enhancements
- [ ] **Per-group FPS override** - Allow different update rates per group
- [ ] **Direction parameter** - Reverse LED addressing (end-to-start)
  - Already in config schema, needs implementation verification
- [ ] **Multi-color solid** - Alternating color patterns for solid effect
- [ ] **Effect chaining** - Transition between effects smoothly

### API Improvements
- [ ] **GET /server/lumen/effects** - List all available effects and parameters
- [ ] **POST /server/lumen/set_group** - Temporarily override group effect via API
- [ ] **WebSocket notifications** - Broadcast state changes to Mainsail/Fluidd
- [ ] **Macro integration** - LUMEN_SET_EFFECT macro for G-code control

### Debugging Tools
- [ ] **Effect preview mode** - Test effects without changing hardware
- [ ] **FPS counter** - Report actual achieved frame rate
- [ ] **Performance profiling** - Identify slow effects or bottlenecks

---

## 🎮 v0.6.0 - Fun Features

### PONG Mode
- [ ] **Interactive LED Pong game** - Play during long prints!
  - Use position_x for paddle control
  - Ball bounces off "walls" (LED ends)
  - Score tracking via Mainsail console
  - Enable via `on_printing: pong` (because why not?)

### Music Reactive (Stretch Goal)
- [ ] **Audio input integration** - LEDs react to print noises?
  - USB microphone support
  - FFT analysis for frequency-based colors
  - Beat detection for pulse timing

---

## 🐛 Known Issues / Tech Debt

### Performance
- [ ] Optimize disco effect random seed (currently uses time.time())
- [ ] Add frame skip detection for overloaded systems
- [ ] Consider LRU cache for color lookups

### Code Quality
- [ ] Add type stubs for better IDE support
- [ ] Unit tests for state detection logic
- [ ] Integration tests for drivers (with mock hardware)
- [ ] Add mypy/flake8 to CI/CD

### Documentation
- [ ] Video tutorial for installation
- [ ] GIF demonstrations of each effect
- [ ] Troubleshooting flow chart

---

## 🚫 Non-Goals (Won't Implement)

- **RGB color mixing in config** - Use named colors or extend color.py
- **Per-LED config in lumen.cfg** - Use `index_start`/`index_end` groups instead
- **Windows/macOS support** - Raspberry Pi GPIO is Linux-only
- **Standalone mode without Moonraker** - LUMEN is a Moonraker component by design
- **GUI configuration tool** - Editing lumen.cfg is intentionally simple

---

## 📅 Release Cycle

- **Patch releases (v0.1.x)**: Bug fixes only, no new features
- **Minor releases (v0.x.0)**: New features, backward compatible
- **Major releases (vX.0.0)**: Breaking changes (config format, API changes)

**Next planned release:** v0.2.0 (Additional printer states) - Q1 2026

---

## 🙏 Contributing

Want to help? Check the roadmap above and:
1. Open an issue to discuss your idea
2. Fork the repo and create a feature branch
3. Submit a PR with clear description and testing notes

See existing code for patterns (async/await, type hints, docstrings).

---

## 📝 Ideas Parking Lot

Random ideas not yet prioritized:

- Adaptive brightness based on time of day
- Sunrise/sunset effect (gradual warm color fade)
- Integration with Home Assistant (publish state via MQTT)
- LED strip health monitoring (detect dead LEDs, report via API)
- Custom user effects via Python plugins
- Multi-zone thermal gradients (bed left/right, extruder zones)
- Print time remaining estimation (via progress effect labels)

---

**Last Updated:** December 19, 2025
**Current Version:** 0.1.0
**Status:** Production Ready
