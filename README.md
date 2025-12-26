# LUMEN - LED Control for Klipper

**Real-time LED control for Klipper 3D printers via Moonraker**

Smart LED effects that respond to your printer's state in real-time. No macros, no delays, no `AURORA_WAKE` commands.

[![Status](https://img.shields.io/badge/status-stable-brightgreen)]()
[![Version](https://img.shields.io/badge/version-v1.4.4-blue)]()
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

> **v1.4.4 Release** - Production-ready with effect-aware adaptive FPS for optimal performance

---

## Features

- **14 Printer States** - Automatic detection: idle, heating, printing, cooldown, error, bored, sleep, homing, meshing, leveling, probing, paused, cancelled, filament change
- **12 LED Effects** - solid, pulse, heartbeat, disco, rainbow, fire, comet, chase, KITT scanner, thermal gradient, print progress bar, off
- **Multi-Group Coordination** - Seamless animations across multiple LED strips with predator/prey chase behavior
- **3 Driver Types** - GPIO (60fps smooth), Klipper SET_LED (MCU-attached), PWM (non-addressable)
- **Chamber Temperature Support** - Thermal effect now supports bed, extruder, and chamber temperature sources
- **Filament Sensor Integration** - Automatic runout detection triggers filament change state
- **Modular Architecture** - Plugin-based effect and state systems for easy extension
- **50+ Named Colors** - Aurora-compatible color palette
- **Hot Reload** - Update config without restarting Moonraker
- **Full API** - REST endpoints for status, testing, and control
- **Production Ready** - Comprehensive testing on Voron Trident with multi-group animations and optimized performance

---

## What's New in v1.4.4

### Effect-Aware Adaptive FPS
- **Intelligent FPS scaling** - Automatically adjusts update rates based on effect complexity
  - Static effects (solid, off): 5 FPS - no animation needed
  - Slow effects (pulse, heartbeat, thermal, progress): 20 FPS - smooth gradual changes
  - Fast effects (disco, rainbow, fire, comet, chase, KITT): Full driver speed (30-40 FPS)
- **Optimized resource usage** - Reduces unnecessary HTTP requests for static/slow effects
- **Better performance** - Frees CPU/bandwidth for fast animations when needed

### Production Ready
- All 14 printer states working correctly (idle, heating, printing, cooldown, error, bored, sleep, homing, meshing, leveling, probing, paused, cancelled, filament)
- All 12 LED effects rendering smoothly (solid, pulse, heartbeat, disco, rainbow, fire, comet, chase, KITT, thermal, progress, off)
- Macro tracking fully functional with automatic completion detection
- Multi-group coordination working perfectly (predator/prey chase behavior)
- Hot reload, filament sensors, temperature sources all verified working

See [CHANGELOG.md](CHANGELOG.md) for complete version history.

---

## Quick Start

### Installation

```bash
cd ~
git clone https://github.com/MakesBadDecisions/Lumen_RPI.git lumen
cd lumen
chmod +x install.sh
./install.sh
```

The installer will:
1. Detect your Moonraker/Klipper paths
2. Install rpi-ws281x library (for GPIO LEDs)
3. Set up ws281x-proxy service (runs as root for GPIO access)
4. Link LUMEN to Moonraker components
5. Create example configuration
6. Add to moonraker.conf

### Basic Configuration

Edit `~/printer_data/config/lumen.cfg`:

```ini
[lumen_settings]
max_brightness: 0.4        # Global brightness limit (0.0-1.0)
gpio_fps: 30               # Base animation frame rate for GPIO drivers (v1.4.4: adaptive scaling applied)

[lumen_group chamber_leds]
driver: proxy              # GPIO via proxy service (recommended, 60fps)
gpio_pin: 18               # BCM GPIO pin number
index_start: 1             # First LED in strip
index_end: 60              # Last LED in strip
color_order: GRB           # WS2812B = GRB, some strips = RGB
on_idle: solid white
on_heating: thermal bed ice lava 2.0
on_printing: progress steel matrix 1.5
on_cooldown: pulse ice
on_error: heartbeat red
on_bored: disco
on_sleep: off
```

Then restart Moonraker:
```bash
sudo systemctl restart moonraker
```

---

## LED Drivers

### GPIO Driver (Proxy Mode - Recommended)

Best for Raspberry Pi GPIO-attached LED strips. Runs at 60fps with no Klipper queue impact.

**Hardware Setup:**
```ini
# No Klipper config needed - GPIO controlled directly by Pi
```

**LUMEN Config:**
```ini
[lumen_group my_leds]
driver: proxy              # Uses ws281x-proxy service
gpio_pin: 18               # Valid pins: 12, 13, 18, 19 (BCM numbering)
proxy_host: 127.0.0.1
proxy_port: 3769
index_start: 1
index_end: 60
color_order: GRB           # GRB for WS2812B, RGB for some WS2811
```

### Klipper Driver

For MCU-attached LEDs (toolhead, EBB42, etc). Uses SET_LED commands via G-code queue.

**Hardware Setup (printer.cfg):**
```ini
[neopixel toolhead_leds]
pin: EBBCan:PD3            # Your MCU pin
chain_count: 6
color_order: GRB
```

**LUMEN Config:**
```ini
[lumen_group toolhead]
driver: klipper
neopixel: toolhead_leds    # Must match [neopixel] name in printer.cfg
index_start: 1
index_end: 6
```

### PWM Driver

For non-addressable LED strips (single-color, brightness-only).

**Hardware Setup (printer.cfg):**
```ini
[output_pin case_light]
pin: PB7
pwm: True
value: 0.5
```

**LUMEN Config:**
```ini
[lumen_group case]
driver: pwm
pin_name: case_light       # Must match [output_pin] name
```

---

## Effects

### Solid
Static color.
```ini
on_idle: solid white
on_printing: solid green
```

### Pulse
Breathing/fade animation.
```ini
on_idle: pulse cobalt
on_heating: pulse orange
```

### Heartbeat
Double-pulse pattern.
```ini
on_error: heartbeat red
on_cooldown: heartbeat ice
```

### Disco
Random rainbow sparkles.
```ini
on_bored: disco
```

### Rainbow
Cycling rainbow animation - smooth spectrum rotation.
```ini
on_bored: rainbow
on_idle: rainbow
```

### Fire
Flickering flame simulation - realistic orange/red/yellow fire effect.
```ini
on_heating: fire
on_error: fire
```

### Comet
Moving light with trailing tail - comet/meteor effect.
```ini
# Format: comet <color>
on_printing: comet cobalt
on_heating: comet orange
```

### Chase
Predator/prey chase animation with collision detection and role swapping.

**Single-group mode:**
```ini
on_bored: chase
```

**Multi-group coordination** - seamless animation across multiple strips:
```ini
# Format: chase <group_number>
[lumen_group left]
on_cooldown: chase 1

[lumen_group center]
on_cooldown: chase 2

[lumen_group right]
on_cooldown: chase 3
```

**Features:**
- Dynamic predator/prey behavior with proximity acceleration
- Collision detection with bounce and role swap
- Random direction changes and speed variations
- Respects `direction: standard` or `direction: reverse` per group
- Configurable chase size, colors, and collision behavior

**Configuration:**
```ini
[lumen_effect chase]
speed: 50.0                      # Movement speed (LEDs per second)
chase_size: 2                    # LEDs per segment
chase_color_1: lava              # Predator color
chase_color_2: ice               # Prey color
chase_proximity_threshold: 0.15  # Distance for acceleration (0.0-1.0)
chase_accel_factor: 1.5          # Speed boost when hunting/fleeing
chase_role_swap_interval: 20     # Avg seconds between role swaps
chase_collision_pause: 0.3       # Pause duration after collision
```

### KITT
Knight Rider scanner effect with smooth bounce animation.
```ini
# Format: kitt <color>
on_idle: kitt red
on_bored: kitt cobalt
```

**Bed mesh tracking** - scanner follows toolhead position:
```ini
[lumen_effect kitt]
kitt_tracking_axis: x    # Track X axis during printing
# kitt_tracking_axis: y  # Track Y axis
# kitt_tracking_axis: none  # No tracking (default)
```

**Configuration:**
```ini
[lumen_effect kitt]
speed: 0.8                # Bounce speed (sweeps per second)
base_color: red           # Scanner color
kitt_eye_size: 3          # LEDs in bright center eye
kitt_tail_length: 2       # Fading LEDs on each side
kitt_tracking_axis: none  # "none", "x", or "y"
max_brightness: 0.6
```

### Thermal
Temperature-based gradient (cold → hot colors as temp rises).
```ini
# Format: thermal <temp_source> <start_color> <end_color> <curve>
on_heating: thermal bed ice lava 2.0
on_cooldown: thermal extruder lava ice 2.0

# temp_source: bed, extruder, chamber
# curve: 1.0 = linear, >1 = sharp at end, <1 = sharp at start
```

### Progress
Print progress bar (fills as print advances).
```ini
# Format: progress <start_color> <end_color> <curve>
on_printing: progress steel matrix 1.5
```

### Off
LEDs off.
```ini
on_sleep: off
```

---

## Printer States

LUMEN automatically detects printer states from Klipper/Moonraker status:

| State | Trigger |
|-------|---------|
| `idle` | Cool, no targets, ready |
| `heating` | Heaters on, warming up |
| `printing` | Active print, at temp |
| `cooldown` | Print done, still hot (temp > 40°C, targets off) |
| `error` | Klipper shutdown/error |
| `bored` | Idle for N minutes (configurable) |
| `sleep` | Bored for N minutes (configurable) |

Configure timeouts:
```ini
[lumen_settings]
bored_timeout: 300         # Seconds idle before "bored" (default: 300)
sleep_timeout: 600         # Seconds bored before "sleep" (default: 600)
```

---

## Effect Settings

Tune how effects behave globally:

```ini
[lumen_effect pulse]
speed: 1.0                 # Cycles per second (1.0 = 1s breathe)
min_brightness: 0.2        # Dimmest point (0.0-1.0)
max_brightness: 0.8        # Brightest point

[lumen_effect heartbeat]
speed: 1.2                 # Beats per second (1.2 = 72 BPM)
min_brightness: 0.1
max_brightness: 1.0

[lumen_effect disco]
speed: 3.0                 # Color changes per second
min_sparkle: 1             # Min LEDs lit per update
max_sparkle: 6             # Max LEDs lit per update

[lumen_effect rainbow]
speed: 0.5                 # Cycles per second (0.5 = 2s full rainbow)
rainbow_spread: 1.0        # Spectrum spread across strip (0.0-1.0)
max_brightness: 0.9

[lumen_effect fire]
speed: 5.0                 # Flicker updates per second
min_brightness: 0.1        # Dimmest flame
max_brightness: 0.6        # Brightest flame
fire_cooling: 0.4          # Cooling rate (0.0-1.0, higher = more chaotic)

[lumen_effect comet]
speed: 10.0                # Movement speed (LEDs per second)
max_brightness: 0.5        # Brightness of comet head
comet_tail_length: 4       # Length of trailing tail (in LEDs)
comet_fade_rate: 0.9       # How quickly tail fades (0.0-1.0)

[lumen_effect chase]
speed: 50.0                      # Movement speed (LEDs per second)
chase_size: 2                    # LEDs per segment
chase_color_1: lava              # Predator color
chase_color_2: ice               # Prey color
chase_offset_base: 0.5           # Base distance between segments (single-group)
chase_offset_variation: 0.1      # Offset variation (single-group)
chase_proximity_threshold: 0.15  # Distance for acceleration (multi-group)
chase_accel_factor: 1.5          # Speed boost when hunting/fleeing
chase_role_swap_interval: 20     # Avg seconds between role swaps
chase_collision_pause: 0.3       # Pause duration after collision
max_brightness: 0.6

[lumen_effect kitt]
speed: 0.8                 # Bounce speed (sweeps per second)
base_color: red            # Scanner color
kitt_eye_size: 3           # LEDs in bright center eye
kitt_tail_length: 2        # Fading LEDs on each side
kitt_tracking_axis: none   # "none" | "x" | "y" (bed mesh tracking)
max_brightness: 0.6

[lumen_effect thermal]
temp_source: extruder      # bed, extruder, chamber
gradient_curve: 2.0        # 1.0=linear, >1=sharp at end

[lumen_effect progress]
gradient_curve: 1.5        # Slightly sharper toward 100%
```

---

## Colors

50+ named colors available. Use `/server/lumen/colors` API to see full list.

**Common:**
`white`, `black`, `red`, `green`, `blue`, `yellow`, `orange`, `purple`, `pink`

**Cool:**
`ice`, `cobalt`, `azure`, `teal`, `mint`, `cyan`

**Warm:**
`lava`, `fire`, `gold`, `amber`, `coral`, `salmon`

**Special:**
`matrix`, `steel`, `neon_pink`, `neon_green`, `dimwhite`

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/server/lumen/status` | GET | Current state, config, LED groups, warnings |
| `/server/lumen/colors` | GET | List all available color names |
| `/server/lumen/test_event?event=STATE` | POST | Manually trigger a state (heating, printing, etc) |
| `/server/lumen/reload` | POST | Hot reload lumen.cfg without Moonraker restart |

**Examples:**
```bash
# Check status
curl http://localhost:7125/server/lumen/status | jq

# List colors
curl http://localhost:7125/server/lumen/colors | jq

# Test heating effect
curl -X POST "http://localhost:7125/server/lumen/test_event?event=heating"

# Hot reload config after editing
curl -X POST "http://localhost:7125/server/lumen/reload"
```

---

## Troubleshooting

### Check Logs
```bash
# LUMEN component logs
sudo journalctl -u moonraker | grep LUMEN | tail -100

# GPIO proxy logs (if using proxy driver)
sudo journalctl -u ws281x-proxy | tail -100
```

### Enable Debug Mode
Edit `~/printer_data/config/moonraker.conf`:
```ini
[lumen]
config_path: ~/printer_data/config/lumen.cfg
debug: console    # Logs to Mainsail console + journalctl
```

### Common Issues

**"The value 'X' is not valid for LED" errors in Mainsail:**
- LUMEN config references hardware that doesn't exist in printer.cfg
- Solution: Comment out or delete the LED groups you don't have
- Example: If you don't have `[neopixel toolhead_leds]` in printer.cfg, comment out any `lumen_group` sections using `neopixel: toolhead_leds`
- Hot reload after fixing: `curl -X POST "http://localhost:7125/server/lumen/reload"`

**LEDs don't light up:**
1. Check GPIO pin number (valid: 12, 13, 18, 19)
2. Verify `ws281x-proxy` service is running: `sudo systemctl status ws281x-proxy`
3. Test proxy: `curl http://127.0.0.1:3769/status`
4. Check color_order (try GRB or RGB)

**GPIO 19 initialization fails:**
- Error: "Gpio 19 is illegal for LED channel 0" or "RuntimeError: ws2811_init failed with code -11"
- Cause: GPIO 19 uses PWM1 hardware which conflicts with audio output
- Check if audio enabled: `grep -i audio /boot/config.txt`
- Solution 1: Disable audio in `/boot/config.txt` (change `dtparam=audio=on` to `dtparam=audio=off`), then reboot
- Solution 2: Use GPIO 18 instead (PWM0, no audio conflict)
- Recommended: Use GPIO 18 unless you specifically need GPIO 19

**Wrong colors:**
Change `color_order` in lumen.cfg:
```ini
color_order: RGB    # Try RGB instead of GRB
```

**Config warnings:**
Check status API for details:
```bash
curl http://localhost:7125/server/lumen/status | jq .warnings
```

**Klipper driver slow during prints:**
Expected! Klipper driver uses G-code queue which gets busy during printing. Use GPIO/proxy driver for smooth 60fps animations.

---

## moonraker.conf Setup

Add to `~/printer_data/config/moonraker.conf`:

```ini
[lumen]
config_path: ~/printer_data/config/lumen.cfg
# debug: True              # Enable for troubleshooting
# debug: console           # Also log to Mainsail console

[update_manager lumen]
type: git_repo
path: ~/lumen
origin: https://github.com/MakesBadDecisions/Lumen_RPI.git
managed_services: moonraker
primary_branch: main
```

---

## Example Configurations

### Voron - Toolhead + Chamber

```ini
[lumen_group toolhead_logo]
driver: klipper
neopixel: sb_leds
index_start: 1
index_end: 1
on_idle: pulse cobalt
on_printing: solid white
on_error: heartbeat red

[lumen_group chamber_strip]
driver: proxy
gpio_pin: 18
index_start: 1
index_end: 60
on_idle: solid dimwhite
on_heating: thermal bed ice lava 2.0
on_printing: progress steel matrix 1.5
on_cooldown: pulse ice
```

### Prusa-Style Status LED

```ini
[lumen_group status_led]
driver: klipper
neopixel: status_rgb
index_start: 1
index_end: 1
on_idle: solid green
on_heating: pulse orange
on_printing: solid green
on_cooldown: pulse blue
on_error: heartbeat red
```

### Case Lights (PWM)

```ini
[lumen_group case_light]
driver: pwm
pin_name: caselight_pwm
on_idle: 0.5
on_printing: 1.0
on_sleep: 0.0
```

### Multi-Group Chase - Seamless Circular Animation

```ini
# Three LED strips forming a continuous ring around the printer
# Chase groups create predator/prey animation across all strips

[lumen_effect chase]
speed: 50.0                      # Movement speed (LEDs per second)
chase_size: 2                    # LEDs per segment
chase_color_1: lava              # Predator color (red/orange)
chase_color_2: ice               # Prey color (blue/white)
chase_proximity_threshold: 0.15  # 15% of ring = "getting close"
chase_accel_factor: 1.5          # Speed boost when hunting/fleeing
chase_role_swap_interval: 20     # Average seconds between role swaps
chase_collision_pause: 0.3       # Pause duration after collision

[lumen_group left_strip]
driver: proxy
gpio_pin: 18
index_start: 19
index_end: 36
direction: reverse               # Physical LEDs go 36→19 (right to left)
on_cooldown: chase 1             # First segment in circular array

[lumen_group center_strip]
driver: proxy
gpio_pin: 18
index_start: 37
index_end: 53
direction: reverse               # Physical LEDs go 53→37
on_cooldown: chase 2             # Second segment in circular array

[lumen_group right_strip]
driver: proxy
gpio_pin: 18
index_start: 1
index_end: 18
direction: standard              # Physical LEDs go 1→18 (left to right)
on_cooldown: chase 3             # Third segment in circular array

# Result: Seamless predator/prey chase animation that flows smoothly
# across all three strips with collision detection and role swapping
```

---

## Requirements

- Raspberry Pi (any model)
- Moonraker installed
- Python 3.7+
- For GPIO LEDs: WS2812B/NeoPixel strips
- For Klipper driver: LEDs defined in printer.cfg

---

## Uninstall

```bash
cd ~/lumen
chmod +x uninstall.sh
./uninstall.sh
```

The uninstaller will:
1. Stop and remove ws281x-proxy service
2. Remove Moonraker component symlinks
3. Optionally remove lumen.cfg (asks first)
4. Automatically remove moonraker.conf sections (creates backup)
5. Optionally restore pigpiod service
6. Optionally remove ~/lumen directory (asks first)
7. Optionally restart Moonraker

---

## Performance

### Effect-Aware Adaptive FPS (v1.4.4)
LUMEN intelligently adjusts update rates based on effect complexity to optimize CPU and bandwidth:

- **Static effects** (`solid`, `off`): 5 FPS maximum - no animation, minimal updates needed
- **Slow effects** (`pulse`, `heartbeat`, `thermal`, `progress`): 20 FPS maximum - smooth gradual changes
- **Fast effects** (`disco`, `rainbow`, `fire`, `comet`, `chase`, `kitt`): Full driver speed (30-40 FPS)

This adaptive scaling reduces unnecessary HTTP requests for static/slow effects, freeing CPU/bandwidth for fast animations.

### Driver Performance
- **GPIO/Proxy Driver**: 30-40 FPS on fast animations, bypasses Klipper G-code queue
- **Klipper Driver**: 0.1-5s update rate (slower during prints due to G-code queue)
- **CPU Usage**: <1% on Raspberry Pi 4
- **Memory**: ~50MB

---

## License

MIT License - See [LICENSE](LICENSE) file

---

## Credits

Inspired by [Aurora Lights](https://github.com/MakesBadDecisions/Aurora)

Built for real-time performance and smooth animations without macro limitations.

---

**Made with insomnia and determination to never type `AURORA_WAKE` again.**
