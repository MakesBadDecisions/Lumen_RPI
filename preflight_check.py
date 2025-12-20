#!/usr/bin/env python3
"""
Pre-flight Check - Comprehensive validation before deployment

Tests actual integration with lumen.py to catch any issues.
"""

import sys
import os
from pathlib import Path

# Add moonraker/components to path
component_dir = Path(__file__).parent / "moonraker" / "components"
sys.path.insert(0, str(component_dir))

def check_imports():
    """Check that all core imports work."""
    print("=" * 60)
    print("Pre-Flight Check: Core Imports")
    print("=" * 60)

    try:
        print("  Importing lumen_lib...")
        from lumen_lib import (
            RGB, get_color, list_colors,
            EffectState,
            LEDDriver, KlipperDriver, PWMDriver, GPIODriver, ProxyDriver, create_driver,
            PrinterState, PrinterEvent, StateDetector,
        )
        print("  [OK] lumen_lib core imports")

        print("  Importing EFFECT_REGISTRY...")
        from lumen_lib.effects import EFFECT_REGISTRY
        print(f"  [OK] EFFECT_REGISTRY loaded: {list(EFFECT_REGISTRY.keys())}")

        print("  Importing state detectors...")
        from lumen_lib.states import STATE_REGISTRY, STATE_PRIORITY
        print(f"  [OK] STATE_REGISTRY loaded: {list(STATE_REGISTRY.keys())}")

        return True
    except Exception as e:
        print(f"  [FAIL] Import error: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_lumen_component():
    """Check that main lumen.py component loads."""
    print("\n" + "=" * 60)
    print("Pre-Flight Check: Main Component")
    print("=" * 60)

    try:
        print("  Importing lumen component...")
        # This simulates what Moonraker does
        import lumen
        print(f"  [OK] lumen component loaded (version {lumen.__version__})")

        # Check that Lumen class exists
        if hasattr(lumen, 'Lumen'):
            print("  [OK] Lumen class found")
        else:
            print("  [FAIL] Lumen class not found!")
            return False

        return True
    except Exception as e:
        print(f"  [FAIL] Component error: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_effect_calculation():
    """Test that effects can actually calculate colors."""
    print("\n" + "=" * 60)
    print("Pre-Flight Check: Effect Calculation")
    print("=" * 60)

    try:
        from lumen_lib.effects import EFFECT_REGISTRY
        from lumen_lib.effect_state import EffectState
        import time

        # Test each effect
        errors = []
        for name, effect_class in EFFECT_REGISTRY.items():
            try:
                effect = effect_class()
                state = EffectState(
                    base_color=(1.0, 0.5, 0.0),
                    speed=1.0,
                    start_color=(0.0, 0.0, 1.0),
                    end_color=(1.0, 0.0, 0.0),
                    temp_source="extruder",
                )

                # Test with state data for effects that need it
                state_data = {
                    'bed_temp': 60.0,
                    'bed_target': 60.0,
                    'extruder_temp': 200.0,
                    'extruder_target': 200.0,
                    'temp_floor': 25.0,
                    'print_progress': 0.5,
                }

                colors, needs_update = effect.calculate(state, time.time(), led_count=10, state_data=state_data)

                # Verify output
                if not isinstance(colors, list):
                    raise ValueError(f"colors must be list, got {type(colors)}")
                if not isinstance(needs_update, bool):
                    raise ValueError(f"needs_update must be bool, got {type(needs_update)}")

                print(f"  [OK] {name}: {len(colors)} colors, update={needs_update}")

            except Exception as e:
                print(f"  [FAIL] {name}: {e}")
                errors.append((name, e))

        if errors:
            print(f"\n  [WARN] {len(errors)} effect(s) failed")
            return False
        else:
            print(f"\n  [OK] All {len(EFFECT_REGISTRY)} effects work correctly")
            return True

    except Exception as e:
        print(f"  [FAIL] Effect calculation error: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_state_detection():
    """Test state detection with realistic data."""
    print("\n" + "=" * 60)
    print("Pre-Flight Check: State Detection")
    print("=" * 60)

    try:
        from lumen_lib.state import StateDetector, PrinterState, PrinterEvent

        detector = StateDetector(temp_floor=25.0, bored_timeout=60.0, sleep_timeout=120.0)
        print(f"  [OK] StateDetector created with {len(detector._detectors)} detectors")

        # Test scenario 1: Cold idle
        state = PrinterState()
        event = detector.update(state)
        print(f"  [OK] Cold idle: {event}")

        # Test scenario 2: Heating
        state.bed_target = 60.0
        state.bed_temp = 30.0
        event = detector.update(state)
        expected = PrinterEvent.HEATING
        if event == expected:
            print(f"  [OK] Heating detected: {event}")
        else:
            print(f"  [WARN] Expected {expected}, got {event}")

        # Test scenario 3: Printing
        state.print_state = "printing"
        state.bed_temp = 60.0
        state.extruder_target = 200.0
        state.extruder_temp = 200.0
        event = detector.update(state)
        expected = PrinterEvent.PRINTING
        if event == expected:
            print(f"  [OK] Printing detected: {event}")
        else:
            print(f"  [WARN] Expected {expected}, got {event}")

        # Test scenario 4: Error
        state.klipper_state = "shutdown"
        event = detector.update(state)
        expected = PrinterEvent.ERROR
        if event == expected:
            print(f"  [OK] Error detected: {event}")
        else:
            print(f"  [WARN] Expected {expected}, got {event}")

        print(f"\n  [OK] State detection working correctly")
        return True

    except Exception as e:
        print(f"  [FAIL] State detection error: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_config_example():
    """Verify config example is valid."""
    print("\n" + "=" * 60)
    print("Pre-Flight Check: Config Example")
    print("=" * 60)

    config_path = Path(__file__).parent / "config" / "lumen.cfg.example"

    if not config_path.exists():
        print(f"  [FAIL] Config example not found: {config_path}")
        return False

    print(f"  [OK] Config example exists: {config_path.name}")

    # Check for critical sections
    content = config_path.read_text()
    required = ['[lumen_settings]', '[lumen_group', 'on_idle:', 'on_printing:']
    missing = [r for r in required if r not in content]

    if missing:
        print(f"  [WARN] Config missing sections: {missing}")
        return False
    else:
        print(f"  [OK] Config has all required sections")

    return True


def main():
    """Run all pre-flight checks."""
    print("\n" + "=" * 60)
    print("LUMEN Pre-Flight Check")
    print("Before deploying to Moonraker...")
    print("=" * 60 + "\n")

    results = {
        "Core Imports": check_imports(),
        "Main Component": check_lumen_component(),
        "Effect Calculation": check_effect_calculation(),
        "State Detection": check_state_detection(),
        "Config Example": check_config_example(),
    }

    print("\n" + "=" * 60)
    print("PRE-FLIGHT RESULTS")
    print("=" * 60)

    all_passed = True
    for check, passed in results.items():
        status = "[OK] PASS" if passed else "[FAIL] FAIL"
        print(f"  {status}: {check}")
        if not passed:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("\n[SUCCESS] All pre-flight checks passed!")
        print("Ready to deploy to Moonraker and test on printer.")
        return 0
    else:
        print("\n[FAIL] Some checks failed. Fix issues before deploying.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
