"""
LUMEN Colors - Color definitions and utilities

40+ named colors for LED effects.
"""

from typing import Dict, List, Tuple

# Type alias for RGB color (0.0-1.0 per channel)
RGB = Tuple[float, float, float]

COLORS: Dict[str, RGB] = {
    # Basic Colors
    "red":          (1.0, 0.0, 0.0),
    "green":        (0.0, 1.0, 0.0),
    "blue":         (0.0, 0.0, 1.0),
    "white":        (1.0, 1.0, 1.0),
    "black":        (0.0, 0.0, 0.0),
    "off":          (0.0, 0.0, 0.0),
    
    # Warm Colors
    "orange":       (1.0, 0.5, 0.0),
    "yellow":       (1.0, 1.0, 0.0),
    "gold":         (1.0, 0.75, 0.0),
    "amber":        (1.0, 0.6, 0.0),
    "coral":        (1.0, 0.5, 0.3),
    "salmon":       (1.0, 0.6, 0.5),
    "warm_white":   (1.0, 0.8, 0.6),
    "hot_orange":   (1.0, 0.35, 0.0),
    
    # Cool Colors
    "cyan":         (0.0, 1.0, 1.0),
    "teal":         (0.0, 0.8, 0.7),
    "aqua":         (0.0, 1.0, 0.8),
    "sky":          (0.4, 0.7, 1.0),
    "ice":          (0.7, 0.9, 1.0),
    "cool_white":   (0.9, 0.95, 1.0),
    "cold_blue":    (0.3, 0.5, 1.0),
    
    # Purple/Pink Family
    "purple":       (0.5, 0.0, 1.0),
    "magenta":      (1.0, 0.0, 1.0),
    "pink":         (1.0, 0.4, 0.7),
    "hot_pink":     (1.0, 0.2, 0.6),
    "violet":       (0.6, 0.0, 0.8),
    "lavender":     (0.7, 0.5, 1.0),
    "plum":         (0.6, 0.2, 0.6),
    
    # Green Family
    "lime":         (0.5, 1.0, 0.0),
    "mint":         (0.4, 1.0, 0.6),
    "emerald":      (0.0, 0.8, 0.4),
    "forest":       (0.0, 0.5, 0.2),
    
    # Special
    "fire":         (1.0, 0.3, 0.0),
    "lava":         (1.0, 0.2, 0.0),
    "sunset":       (1.0, 0.4, 0.2),
    "sunrise":      (1.0, 0.6, 0.4),
    "ocean":        (0.0, 0.4, 0.8),
    "steel":        (0.5, 0.5, 0.6),
    "copper":       (0.8, 0.5, 0.2),
    "bronze":       (0.7, 0.5, 0.2),
    "rose":         (1.0, 0.3, 0.4),
    "peach":        (1.0, 0.7, 0.5),
    "cream":        (1.0, 0.95, 0.8),
    "electric":     (0.2, 0.8, 1.0),
    "neon_green":   (0.4, 1.0, 0.2),
    "blood":        (0.6, 0.0, 0.0),
    "royal":        (0.3, 0.0, 0.8),
    "cobalt":       (0.0, 0.3, 0.9),
    "dimwhite":     (0.3, 0.3, 0.3),
    
    # Neon/Vibrant
    "neon_pink":    (1.0, 0.1, 0.5),
    "neon_blue":    (0.1, 0.5, 1.0),
    "neon_orange":  (1.0, 0.4, 0.0),
    "neon_yellow":  (1.0, 1.0, 0.2),
    "neon_purple":  (0.7, 0.0, 1.0),
    
    # Pastels
    "baby_blue":    (0.6, 0.8, 1.0),
    "baby_pink":    (1.0, 0.7, 0.8),
    "seafoam":      (0.5, 1.0, 0.8),
    "lilac":        (0.8, 0.6, 1.0),
    "buttercup":    (1.0, 0.9, 0.5),
    
    # Earth Tones
    "sand":         (0.9, 0.8, 0.6),
    "clay":         (0.8, 0.5, 0.4),
    "moss":         (0.4, 0.6, 0.3),
    "bark":         (0.4, 0.3, 0.2),
    "stone":        (0.6, 0.6, 0.6),
    
    # Gaming/RGB
    "vaporwave":    (1.0, 0.3, 0.8),
    "cyberpunk":    (1.0, 0.0, 0.6),
    "matrix":       (0.0, 1.0, 0.3),
    "portal_blue":  (0.0, 0.6, 1.0),
    "portal_orange": (1.0, 0.5, 0.0),
}


def get_color(name: str) -> RGB:
    """Look up color by name (case-insensitive)."""
    return COLORS.get(name.lower(), (0.0, 0.0, 0.0))


def list_colors() -> List[str]:
    """Return list of all available color names."""
    return sorted(COLORS.keys())
