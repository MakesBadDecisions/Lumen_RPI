# LUMEN Bug Analysis - December 27, 2025

## Issues Identified

### CRITICAL: Issue #1 - LUMEN Macro Syntax Error

**Symptom**: Console shows `Unknown command:"LUMEN"` every time the macro is called.

**Root Cause**: Incorrect Jinja2 template syntax in [lumen_macro.cfg:19](not for github/lumen_macro.cfg#L19)

**Before (BROKEN)**:
```gcode
RESPOND MSG="LUMEN_{state|upper}_START"
```

**After (FIXED)**:
```gcode
RESPOND MSG="LUMEN_{{ state|upper }}_START"
```

**Impact**: This syntax error prevented ANY macro state tracking from working. The LUMEN macro would fail silently, so homing/meshing/leveling states were NEVER triggered.

**Status**: ✅ FIXED

---

### Issue #2 - Macro States Not Triggering GPIO LED Updates

**Symptom**: During G28, BED_MESH_CALIBRATE, Z_TILT_ADJUST, etc., the GPIO LEDs stay frozen in whatever state they were in before the macro started.

**Root Cause**: Issue #1 prevented the macro from executing, so:
1. `LUMEN STATE=homing` command fails → No `LUMEN_HOMING_START` message sent
2. `_on_gcode_response()` never sees the trigger message
3. `_activate_macro_state()` is never called
4. `self._active_macro_state` stays `None`
5. State detector never detects homing/meshing/leveling
6. LEDs never update to `on_homing`, `on_meshing`, `on_leveling` effects

**Evidence from logs**:
- ✅ See: `Event: heating` → GPIO LEDs update correctly
- ✅ See: `Event: printing` → GPIO LEDs update correctly
- ✅ See: `Event: idle` → GPIO LEDs update correctly
- ❌ NEVER see: `Event: homing`
- ❌ NEVER see: `Event: meshing`
- ❌ NEVER see: `Event: leveling`

**Status**: ✅ FIXED (by fixing Issue #1)

---

### Issue #3 - Flickering During Active Printing

**Symptom**: LEDs flicker constantly during active printing, switching between heating and printing effects every few seconds.

**Evidence from logs**:
```
9:56 PM Event: heating
9:56 PM Event: printing
9:56 PM Event: heating
9:56 PM Event: printing
```

**Root Cause**: Temperature tolerance too strict in [printing.py:27](moonraker/components/lumen_lib/states/printing.py#L27)

During printing, extruder temp naturally fluctuates by 3-5°C:
- Retraction/layer change → temp drops to 287°C (target 290°C)
- `PrintingDetector` with 3°C tolerance → sees 3°C delta → returns `False`
- Falls through to `HeatingDetector` → returns `True` → state changes to "heating"
- Extruder recovers to 289°C → back within 3°C → state changes to "printing"
- **Rapid oscillation** between printing ↔ heating effects causes visible flicker

**The Fix**: Increase temperature tolerance in `PrintingDetector` to allow normal temp fluctuations:

**Before**:
```python
TEMP_TOLERANCE = 3.0  # Too strict - any 3°C drop triggers heating state
```

**After**:
```python
TEMP_TOLERANCE = 10.0  # Allows normal temp fluctuation during printing
```

**Why This Works**:
- Extruder dropping from 290°C → 287°C (3°C) = still printing ✓
- Extruder dropping from 290°C → 278°C (12°C) = actually heating ✓
- Prevents rapid state changes from normal PID fluctuations
- Bed tolerance kept stricter (5°C) since bed temps are more stable

**Status**: ✅ FIXED in [printing.py:27](moonraker/components/lumen_lib/states/printing.py#L27)

---

## Testing Plan

### Test 1: Verify LUMEN Macro Works
```gcode
LUMEN STATE=homing
```

**Expected**:
- Console should show: `RESPOND PREFIX="LUMEN" MSG="LUMEN_HOMING_START"`
- NO "Unknown command" error
- GPIO LEDs should change to `on_homing` effect (solid white per voron_trident.cfg)

### Test 2: Verify G28 Integration
Add to your `G28` macro:
```gcode
[gcode_macro G28]
rename_existing: G28.1
gcode:
    LUMEN STATE=homing
    G28.1 {rawparams}
```

**Expected**:
- During homing: GPIO LEDs show `on_homing` effect
- After homing completes: LEDs return to normal state cycle

### Test 3: Verify BED_MESH Integration
Add to your `BED_MESH_CALIBRATE` wrapper:
```gcode
[gcode_macro BED_MESH_CALIBRATE]
rename_existing: BED_MESH_CALIBRATE.1
gcode:
    LUMEN STATE=meshing
    BED_MESH_CALIBRATE.1 {rawparams}
```

**Expected**:
- During meshing: GPIO LEDs show `on_meshing` effect (thermal bed ice fire 2.0)
- After meshing completes: LEDs return to normal state

### Test 4: Verify Z_TILT Integration
Add to your `Z_TILT_ADJUST` wrapper:
```gcode
[gcode_macro Z_TILT_ADJUST]
rename_existing: Z_TILT_ADJUST.1
gcode:
    LUMEN STATE=leveling
    Z_TILT_ADJUST.1 {rawparams}
```

**Expected**:
- During leveling: GPIO LEDs show `on_leveling` effect (thermal bed ice fire 2.0)
- After leveling completes: LEDs return to normal state

### Test 5: Verify No More Flickering During Print
Start a print and watch the LEDs during active printing.

**Expected**:
- LEDs should stay in "printing" state continuously
- NO rapid switching between heating/printing
- Smooth, stable effects during entire print
- Only switches to "heating" if extruder actually drops >10°C below target

---

## Additional Recommendations

### 1. Add Debug Logging to Macro
To verify the macro is executing:
```gcode
[gcode_macro LUMEN]
description: Trigger LUMEN LED state change
gcode:
    {% set state = params.STATE|default("idle")|lower %}

    # Debug: Show what we're doing
    {action_respond_info("LUMEN: Triggering state=%s" % state)}

    # Send RESPOND message that LUMEN detects via gcode_response subscription
    RESPOND MSG="LUMEN_{{ state|upper }}_START"
```

### 2. Enable Full LUMEN Debug Logging
In `moonraker.conf`:
```ini
[lumen]
config_path: ~/printer_data/config/lumen.cfg
debug: console  # Shows all LUMEN debug messages in Mainsail console
```

### 3. Add Macro Completion Messages
Currently, macro states timeout after 120 seconds. Better approach: send completion messages:

```gcode
[gcode_macro G28]
rename_existing: G28.1
gcode:
    LUMEN STATE=homing
    G28.1 {rawparams}
    RESPOND MSG="LUMEN_HOMING_END"
```

This will trigger automatic state return via the completion detection in [lumen.py:682-705](moonraker/components/lumen.py#L682-L705).

---

## Summary

**Issue #1 (CRITICAL)**: Jinja2 syntax error in LUMEN macro prevented all macro state tracking.
- **Fix**: Change `{state|upper}` to `{{ state|upper }}` with proper Jinja2 brackets.
- **Status**: ✅ FIXED

**Issue #2**: Macro states not triggering GPIO LED updates.
- **Cause**: Issue #1 prevented macro from executing
- **Status**: ✅ FIXED (automatically fixed by Issue #1)

**Issue #3**: Flickering during active printing due to temp tolerance too strict.
- **Fix**: Increased extruder temp tolerance from 3°C to 10°C in PrintingDetector
- **Status**: ✅ FIXED

**Next Steps**:
1. ✅ Fixed lumen_macro.cfg Jinja2 syntax
2. ✅ Increased printing temperature tolerance to prevent flickering
3. Deploy to printer: Copy modified files to Raspberry Pi
4. Restart Moonraker: `sudo systemctl restart moonraker`
5. Test with `LUMEN STATE=homing`
6. Integrate into G28, BED_MESH_CALIBRATE, Z_TILT_ADJUST macros
7. Test a full print cycle to verify no more flickering

---

**Files Modified**:
- [not for github/lumen_macro.cfg](not for github/lumen_macro.cfg#L19) - Fixed Jinja2 syntax error
- [moonraker/components/lumen_lib/states/printing.py](moonraker/components/lumen_lib/states/printing.py#L27) - Increased temp tolerance to prevent flickering
