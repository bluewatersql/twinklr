"""Default parameters for curve intensity parameterization.

This module contains global constants for intensity parameters used throughout
the curve system. These are defined separately to avoid circular imports.
"""

# Global default intensity parameters for curve generation
# These are the neutral/baseline values when no intensity adjustment is applied
DEFAULT_CURVE_INTENSITY_PARAMS = {
    "amplitude": 1.0,  # Full amplitude (no scaling)
    "frequency": 1.0,  # Base frequency (no multiplier)
    "center_offset": 0.5,  # Centered (no shift) - used by handlers, not curve functions
}

# Common curve-specific defaults grouped by curve family
# NOTE: center_offset is NOT included in curve params - it's applied at handler level
DEFAULT_WAVE_PARAMS = {
    "cycles": 1.0,
    "phase": 0.0,
    "amplitude": 1.0,
    "frequency": 1.0,
}

DEFAULT_MOVEMENT_PARAMS = {
    "cycles": 1.0,
    "amplitude": 1.0,
    "frequency": 1.0,
}

DEFAULT_PARAMETRIC_PARAMS = {
    "amplitude": 1.0,
    "frequency": 1.0,
}
