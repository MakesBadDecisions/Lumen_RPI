#!/usr/bin/env python3
"""
Test import of lumen_lib package.
Run this on the Pi to diagnose import issues:
    cd ~/lumen/moonraker/components
    python3 test_import.py
"""

import sys
from pathlib import Path

# Add component dir to path (mimics what lumen.py does)
component_dir = Path(__file__).parent / "moonraker" / "components"
if str(component_dir) not in sys.path:
    sys.path.insert(0, str(component_dir))

print(f"Python: {sys.version}")
print(f"Component dir: {component_dir}")
print(f"sys.path[0]: {sys.path[0]}")
print()

# Test each module
modules = [
    ("lumen_lib", "package"),
    ("lumen_lib.colors", "COLORS, get_color"),
    ("lumen_lib.effects", "EffectState, effect_pulse"),
    ("lumen_lib.drivers", "LEDDriver, KlipperDriver"),
    ("lumen_lib.state", "PrinterState, PrinterEvent"),
]

for module, desc in modules:
    try:
        __import__(module)
        print(f"✓ {module} - OK ({desc})")
    except Exception as e:
        print(f"✗ {module} - FAILED: {e}")

print()
print("Testing full import chain...")
try:
    from lumen_lib import (
        RGB, get_color, list_colors,
        EffectState, effect_pulse, effect_heartbeat, effect_disco,
        LEDDriver, KlipperDriver, PWMDriver, create_driver,
        PrinterState, PrinterEvent, StateDetector,
    )
    print("✓ All imports successful!")
    print(f"  Colors available: {len(list_colors())}")
    print(f"  Sample color 'red': {get_color('red')}")
except Exception as e:
    print(f"✗ Import failed: {e}")
    import traceback
    traceback.print_exc()
