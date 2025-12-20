"""
LUMEN Effects - Animated effect functions

Effect functions take state and time, return colors.
"""

import math
import random
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .colors import RGB, get_color

# Heartbeat effect timing constants (percentages of cycle)
HEARTBEAT_FIRST_PULSE_DURATION = 0.15    # First pulse rise (15% of cycle)
HEARTBEAT_DIP_DURATION = 0.05            # Dip between pulses (5% of cycle)
HEARTBEAT_SECOND_PULSE_DURATION = 0.05   # Second pulse (5% of cycle)
HEARTBEAT_FADE_DURATION = 0.10           # Fade after second pulse (10% of cycle)
HEARTBEAT_SECOND_PULSE_INTENSITY = 0.5   # Second pulse is 50% of first


@dataclass
class EffectState:
    """Tracks the current effect state for a group."""
    effect: str = "off"
    color: RGB = (0.0, 0.0, 0.0)
    base_color: RGB = (0.0, 0.0, 0.0)
    start_time: float = 0.0
    last_update: float = 0.0
    # Effect parameters
    speed: float = 1.0
    min_brightness: float = 0.2
    max_brightness: float = 1.0
    # Disco-specific
    min_sparkle: int = 1
    max_sparkle: int = 6
    # Thermal/Progress fill effects
    start_color: RGB = (0.5, 0.5, 0.5)  # steel
    end_color: RGB = (0.0, 1.0, 0.0)    # green
    gradient_curve: float = 1.0          # 1.0=linear, >1=sharp at end, <1=sharp at start
    # Thermal-specific
    temp_source: str = "extruder"        # extruder | bed | chamber
    # Direction for fill effects ('standard' or 'reverse')
    direction: str = "standard"


def effect_pulse(state: EffectState, now: float) -> RGB:
    """
    Pulse/breathing effect - smooth sine wave brightness modulation.

    Creates a gentle breathing pattern by varying LED brightness using a sine wave.
    The brightness oscillates between min_brightness and max_brightness at the
    specified speed (cycles per second).

    Args:
        state: Effect state containing base_color, speed, min/max_brightness
        now: Current time in seconds

    Returns:
        RGB tuple with modulated brightness
    """
    elapsed = now - state.start_time
    phase = (math.sin(elapsed * state.speed * 2 * math.pi) + 1) / 2
    brightness = state.min_brightness + phase * (state.max_brightness - state.min_brightness)

    r, g, b = state.base_color
    return (r * brightness, g * brightness, b * brightness)


def effect_heartbeat(state: EffectState, now: float) -> RGB:
    """
    Heartbeat effect - double-pulse pattern mimicking a real heartbeat.

    Creates a realistic heartbeat pattern with two quick pulses followed by a
    longer rest period. The pattern consists of:
    - First pulse (15% of cycle): rise to max brightness
    - Brief dip (5%): drop to 50% intensity
    - Second pulse (5%): rise back to max
    - Fade out (10%): gradual return to min brightness
    - Rest (remaining 65%): stays at min brightness

    Args:
        state: Effect state containing base_color, speed, min/max_brightness
        now: Current time in seconds

    Returns:
        RGB tuple with heartbeat-modulated brightness
    """
    elapsed = now - state.start_time
    cycle_time = 1.0 / state.speed
    phase = (elapsed % cycle_time) / cycle_time

    if phase < HEARTBEAT_FIRST_PULSE_DURATION:
        # First pulse rising
        t = phase / HEARTBEAT_FIRST_PULSE_DURATION
        brightness = state.min_brightness + t * (state.max_brightness - state.min_brightness)
    elif phase < HEARTBEAT_FIRST_PULSE_DURATION + HEARTBEAT_DIP_DURATION:
        # Dip between pulses
        t = (phase - HEARTBEAT_FIRST_PULSE_DURATION) / HEARTBEAT_DIP_DURATION
        brightness = state.max_brightness - t * (state.max_brightness - state.min_brightness) * HEARTBEAT_SECOND_PULSE_INTENSITY
    elif phase < HEARTBEAT_FIRST_PULSE_DURATION + HEARTBEAT_DIP_DURATION + HEARTBEAT_SECOND_PULSE_DURATION:
        # Second pulse rising
        t = (phase - HEARTBEAT_FIRST_PULSE_DURATION - HEARTBEAT_DIP_DURATION) / HEARTBEAT_SECOND_PULSE_DURATION
        brightness = state.min_brightness + HEARTBEAT_SECOND_PULSE_INTENSITY + t * (state.max_brightness - state.min_brightness) * HEARTBEAT_SECOND_PULSE_INTENSITY
    elif phase < HEARTBEAT_FIRST_PULSE_DURATION + HEARTBEAT_DIP_DURATION + HEARTBEAT_SECOND_PULSE_DURATION + HEARTBEAT_FADE_DURATION:
        # Fade out after second pulse
        t = (phase - HEARTBEAT_FIRST_PULSE_DURATION - HEARTBEAT_DIP_DURATION - HEARTBEAT_SECOND_PULSE_DURATION) / HEARTBEAT_FADE_DURATION
        brightness = state.max_brightness - t * (state.max_brightness - state.min_brightness)
    else:
        # Rest period
        brightness = state.min_brightness

    r, g, b = state.base_color
    return (r * brightness, g * brightness, b * brightness)


def effect_disco(
    state: EffectState,
    now: float,
    led_count: int
) -> Tuple[List[Optional[RGB]], bool]:
    """
    Disco/sparkle effect - random rainbow colors on randomly selected LEDs.

    Creates a dynamic party effect by randomly selecting a subset of LEDs and
    assigning them random HSV-generated colors. The number of lit LEDs varies
    between min_sparkle and max_sparkle each update.

    Args:
        state: Effect state containing speed, min/max_sparkle, max_brightness
        now: Current time in seconds
        led_count: Total number of LEDs in the strip

    Returns:
        Tuple of (color_list, should_update)
        - color_list: List of RGB tuples or None for each LED
        - should_update: True if enough time has passed for next frame
    """
    time_since_update = now - state.last_update
    interval = 1.0 / state.speed

    if time_since_update < interval:
        return [], False

    # Use microsecond precision for random seed to avoid pattern repetition
    # at slow update rates (< 1 Hz)
    random.seed(int(now * 1000000))
    
    min_lit = min(state.min_sparkle, led_count)
    max_lit = min(state.max_sparkle, led_count)
    num_lit = random.randint(min_lit, max_lit)
    
    all_indices = list(range(led_count))
    random.shuffle(all_indices)
    lit_indices = set(all_indices[:num_lit])
    
    colors: List[Optional[RGB]] = []
    for i in range(led_count):
        if i in lit_indices:
            hue = random.random()
            h = hue * 6
            c = state.max_brightness
            x = c * (1 - abs(h % 2 - 1))
            
            if h < 1:
                r, g, b = c, x, 0
            elif h < 2:
                r, g, b = x, c, 0
            elif h < 3:
                r, g, b = 0, c, x
            elif h < 4:
                r, g, b = 0, x, c
            elif h < 5:
                r, g, b = x, 0, c
            else:
                r, g, b = c, 0, x
            colors.append((r, g, b))
        else:
            colors.append(None)
    
    return colors, True


def _lerp_color(color1: RGB, color2: RGB, t: float) -> RGB:
    """Linear interpolate between two colors. t=0 returns color1, t=1 returns color2."""
    r = color1[0] + (color2[0] - color1[0]) * t
    g = color1[1] + (color2[1] - color1[1]) * t
    b = color1[2] + (color2[2] - color1[2]) * t
    return (r, g, b)


def effect_fill(
    state: EffectState,
    fill_percent: float,
    led_count: int
) -> List[Optional[RGB]]:
    """
    Progressive fill effect with color gradient - core logic for thermal/progress effects.

    Creates a progress bar effect where LEDs light up sequentially with a smooth
    color gradient from start_color to end_color. Supports partial LED illumination
    for smooth visual transitions and configurable gradient curves.

    The gradient curve parameter allows non-linear color transitions:
    - curve = 1.0: Linear gradient
    - curve > 1.0: Color shift concentrated at the end (slower start, faster finish)
    - curve < 1.0: Color shift concentrated at the start (faster start, slower finish)

    Args:
        state: Effect state containing:
            - start_color: RGB color at 0% fill
            - end_color: RGB color at 100% fill
            - gradient_curve: Power function exponent for gradient shape
            - direction: 'standard' (1→N) or 'reverse' (N→1)
        fill_percent: Fill level from 0.0 (empty) to 1.0 (full)
        led_count: Total number of LEDs in the strip

    Returns:
        List of RGB tuples or None for each LED position
        The list is reversed if direction='reverse'
    """
    fill_percent = max(0.0, min(1.0, fill_percent))
    
    # How many LEDs should be lit (can be fractional for partial LED)
    lit_count = fill_percent * led_count
    
    colors: List[Optional[RGB]] = []
    
    for i in range(led_count):
        led_pos = i + 1  # 1-indexed position
        
        if led_pos <= lit_count:
            # This LED is fully lit
            # Calculate gradient position (where in the gradient is this LED?)
            if led_count <= 1:
                gradient_t = 1.0
            else:
                gradient_t = i / (led_count - 1)
            
            # Apply curve: t^curve makes gradient sharper at end when curve > 1
            curved_t = pow(gradient_t, state.gradient_curve)
            
            color = _lerp_color(state.start_color, state.end_color, curved_t)
            colors.append(color)
        
        elif led_pos - 1 < lit_count:
            # This LED is partially lit (the "leading edge")
            # Show the color but dimmed based on how much it's lit
            partial = lit_count - (led_pos - 1)  # 0.0-1.0 how much of this LED
            
            if led_count <= 1:
                gradient_t = 1.0
            else:
                gradient_t = i / (led_count - 1)
            
            curved_t = pow(gradient_t, state.gradient_curve)
            base_color = _lerp_color(state.start_color, state.end_color, curved_t)
            
            # Dim the color based on partial fill
            color = (base_color[0] * partial, base_color[1] * partial, base_color[2] * partial)
            colors.append(color)
        
        else:
            # This LED is off
            colors.append(None)
    
    # Reverse colors if direction is 'reverse'
    if hasattr(state, 'direction') and getattr(state, 'direction', 'standard') == 'reverse':
        colors = list(reversed(colors))
    return colors


def effect_thermal(
    state: EffectState,
    current_temp: float,
    target_temp: float,
    temp_floor: float,
    led_count: int
) -> List[Optional[RGB]]:
    """
    Temperature-based progressive fill effect - visualizes heating/cooling progress.

    Creates a visual temperature indicator that fills as temperature rises from
    ambient (temp_floor) to target. The fill percentage represents:
        (current_temp - temp_floor) / (target_temp - temp_floor)

    Common use cases:
    - Bed heating: ice (blue) → lava (red-orange)
    - Extruder heating: steel (gray) → fire (orange-red)
    - Cooldown: lava (red) → ice (blue) with reversed direction

    Args:
        state: Effect state containing:
            - start_color: Color at temp_floor (e.g., 'ice' for cold)
            - end_color: Color at target_temp (e.g., 'lava' for hot)
            - gradient_curve: Non-linear gradient shape
            - temp_source: 'extruder', 'bed', or 'chamber'
            - direction: LED fill direction
        current_temp: Current temperature in °C
        target_temp: Target temperature in °C (0 = heater off)
        temp_floor: Ambient temperature baseline in °C
        led_count: Number of LEDs in the strip

    Returns:
        List of RGB tuples for each LED
        Returns solid start_color if target <= 0 (heater off)
    """
    # If no target set, show solid start_color (waiting for heater)
    if target_temp <= 0:
        return [state.start_color] * led_count
    
    # If target is at or below floor, show start color
    if target_temp <= temp_floor:
        return [state.start_color] * led_count
    
    # Calculate fill percentage
    temp_range = target_temp - temp_floor
    temp_above_floor = current_temp - temp_floor
    fill_percent = temp_above_floor / temp_range
    
    return effect_fill(state, fill_percent, led_count)


def effect_progress(
    state: EffectState,
    progress: float,
    led_count: int
) -> List[Optional[RGB]]:
    """
    Print progress bar effect - visual indication of print completion percentage.

    Creates a classic progress bar that fills from 0% to 100% as the print advances.
    Uses the same gradient fill logic as thermal effect but driven by print progress
    instead of temperature.

    Common use cases:
    - Print progress: Start color (0%) → End color (100%)
    - Typical colors: steel → matrix (gray to green)
    - Alternative: ice → fire (cold to hot, thematic for "heating up to finish")

    Args:
        state: Effect state containing:
            - start_color: Color at 0% progress
            - end_color: Color at 100% progress
            - gradient_curve: Non-linear gradient shape
            - direction: LED fill direction
        progress: Print completion from 0.0 (start) to 1.0 (complete)
        led_count: Number of LEDs in the strip

    Returns:
        List of RGB tuples for each LED
    """
    return effect_fill(state, progress, led_count)
